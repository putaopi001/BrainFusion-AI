"""Exploratory patient-level diagnostics frozen in R4_STATISTICS_PROTOCOL.md."""
import hashlib
import json

import numpy as np
from scipy.optimize import minimize_scalar

METRICS = ('auc', 'balanced_accuracy', 'brier', 'sensitivity', 'specificity', 'ece')
EPSILON = 1e-6
LOG_BOUNDS = (-3., 3.)


def _ids(values, *, empty=False):
    if not isinstance(values, (list, tuple)) or (not values and not empty) or any(not isinstance(p, str) or not p.strip() for p in values) or len(set(values)) != len(values):
        raise ValueError('Patient IDs must be unique strings in an ordered list')
    return list(values)


def _binary(labels, probabilities, *, empty=False):
    y, p = np.asarray(labels, dtype=float), np.asarray(probabilities, dtype=float)
    if y.ndim != 1 or p.shape != y.shape or (not len(y) and not empty) or not np.isfinite(y).all() or not np.isin(y, [0, 1]).all() or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError('Require aligned raw binary labels and finite [0,1] probabilities; failures cannot be silently dropped')
    return y, p


def _draw_metrics(y, p, indices):
    b, n = indices.shape
    if not n:
        return np.full((b, len(METRICS)), np.nan)
    target, prediction = y[indices], p[indices]
    positive, negative = target == 1, target == 0
    n_positive, n_negative = positive.sum(axis=1), negative.sum(axis=1)
    def ratio(num, den):
        return np.divide(num, den, out=np.full(b, np.nan), where=den > 0)
    sensitivity = ratio(((prediction >= .5) & positive).sum(axis=1), n_positive)
    specificity = ratio(((prediction < .5) & negative).sum(axis=1), n_negative)
    difference = prediction[:, :, None] - prediction[:, None, :]
    paired = positive[:, :, None] & negative[:, None, :]
    favorable = (((difference > 0) + .5 * (difference == 0)) * paired).sum(axis=(1, 2))
    auc = ratio(favorable, n_positive * n_negative)
    brier = np.mean((prediction - target) ** 2, axis=1)
    ece = np.zeros(b)
    bins = np.minimum((prediction * 5).astype(int), 4)
    for bin_index in range(5):
        present = bins == bin_index
        # count/n * |mean(p)-mean(y)| equals |sum(p-y)|/n for each nonempty bin.
        ece += np.abs(np.where(present, prediction - target, 0).sum(axis=1)) / n
    return np.column_stack([auc, (sensitivity + specificity) / 2, brier, sensitivity, specificity, ece])


def binary_summary(labels, probabilities):
    y, p = _binary(labels, probabilities, empty=True)
    values = _draw_metrics(y, p, np.arange(len(y))[None, :])[0]
    return {'patients': len(y), 'positive': int((y == 1).sum()), 'negative': int((y == 0).sum()),
            'metrics': {key: float(v) if np.isfinite(v) else None for key, v in zip(METRICS, values)},
            'confusion': {'tp': int(((y == 1) & (p >= .5)).sum()), 'fn': int(((y == 1) & (p < .5)).sum()),
                          'tn': int(((y == 0) & (p < .5)).sum()), 'fp': int(((y == 0) & (p >= .5)).sum())}}


def reliability_bins(labels, probabilities):
    y, p = _binary(labels, probabilities, empty=True)
    assignments = np.minimum((p * 5).astype(int), 4)
    rows = []
    for i in range(5):
        chosen = assignments == i
        rows.append({'lower': i / 5, 'upper': (i + 1) / 5, 'upper_inclusive': i == 4,
                     'count': int(chosen.sum()), 'mean_probability': float(p[chosen].mean()) if chosen.any() else None,
                     'observed_target_one_fraction': float(y[chosen].mean()) if chosen.any() else None})
    return rows


def stratified_patient_indices(labels, *, samples=2000, seed=20261016):
    y, _ = _binary(labels, np.full(len(labels), .5))
    if isinstance(samples, bool) or not isinstance(samples, (int, np.integer)) or not 1 <= samples <= 10000 or isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or seed < 0:
        raise ValueError('Invalid bounded bootstrap sample count or seed')
    rng = np.random.default_rng(seed)
    chunks = []
    for value in (0, 1):
        group = np.flatnonzero(y == value)
        if len(group):
            chunks.append(rng.choice(group, size=(samples, len(group)), replace=True))
    return np.column_stack(chunks).astype(np.int64)


def interval(samples):
    values = np.asarray(samples, dtype=float)
    if values.ndim != 1 or not len(values) or np.isinf(values).any():
        raise ValueError('Interval samples must be a nonempty vector without infinity')
    valid = values[np.isfinite(values)]
    return {'lower': float(np.quantile(valid, .025, method='linear')) if len(valid) else None,
            'upper': float(np.quantile(valid, .975, method='linear')) if len(valid) else None,
            'valid_resamples': len(valid), 'undefined_resamples': len(values) - len(valid),
            'degenerate': bool(np.ptp(valid) <= 1e-12) if len(valid) else None,
            'method': 'stratified_patient_percentile_95', 'conditional_on_fitted_models_and_observed_class_counts': True}


def bootstrap_metrics(labels, probabilities, patient_ids, indices):
    y, p = _binary(labels, probabilities)
    ids = _ids(patient_ids)
    raw = np.asarray(indices)
    if len(ids) != len(y) or raw.ndim != 2 or raw.shape[1] != len(y) or not len(raw) or not np.issubdtype(raw.dtype, np.integer) or ((raw < 0) | (raw >= len(y))).any():
        raise ValueError('Bootstrap indices and patient identities must align')
    indices = np.asarray(raw, dtype=np.int64)
    samples = _draw_metrics(y, p, indices)
    return {'patient_ids_sha256': hashlib.sha256(json.dumps(ids, separators=(',', ':')).encode()).hexdigest(),
            'labels_sha256': hashlib.sha256(y.tobytes()).hexdigest(),
            'indices_sha256': hashlib.sha256(str(indices.shape).encode() + indices.tobytes()).hexdigest(),
            'point': binary_summary(y, p), 'intervals': {key: interval(samples[:, j]) for j, key in enumerate(METRICS)},
            'samples': samples}


def paired_difference(left, right):
    for key in ('patient_ids_sha256', 'labels_sha256', 'indices_sha256'):
        if left[key] != right[key]:
            raise ValueError('Paired intervals require identical patient order, labels and resampling indices')
    if left['samples'].shape != right['samples'].shape:
        raise ValueError('Paired bootstrap shapes differ')
    points = {}
    for key in METRICS:
        a, b = left['point']['metrics'][key], right['point']['metrics'][key]
        points[key] = None if a is None or b is None else a - b
    difference = left['samples'] - right['samples']
    return {'point_difference_left_minus_right': points,
            'intervals': {key: interval(difference[:, j]) for j, key in enumerate(METRICS)},
            'paired_patients': left['point']['patients'], 'indices_sha256': left['indices_sha256'],
            'interpretation': 'descriptive paired conditional intervals; no superiority/equivalence test'}


def fit_temperature(probabilities, labels, *, validation_ids, excluded_ids):
    y, p = _binary(labels, probabilities)
    ids, excluded = _ids(validation_ids), _ids(excluded_ids, empty=True)
    if len(ids) != len(y) or set(ids) & set(excluded):
        raise ValueError('Calibration validation IDs overlap excluded training/evaluation roles or do not align')
    clipped = np.clip(p, EPSILON, 1 - EPSILON)
    logits = np.log(clipped / (1 - clipped))
    def loss(log_temperature):
        z = logits / np.exp(log_temperature)
        return float(np.mean(np.logaddexp(0, z) - y * z))
    before, log_temperature, reason, status = loss(0), 0., None, 'fitted'
    if len(np.unique(y)) < 2:
        reason, status = 'single_class_validation_identity', 'identity_fallback'
    elif np.max(np.abs(logits)) <= 1e-12:
        reason, status = 'zero_logits_identity', 'identity_fallback'
    else:
        result = minimize_scalar(loss, bounds=LOG_BOUNDS, method='bounded', options={'xatol': 1e-8, 'maxiter': 200})
        if not result.success or not np.isfinite(result.fun) or result.fun >= before - 1e-12:
            reason, status = 'optimizer_failed_or_no_validation_improvement', 'identity_fallback'
        else:
            log_temperature = float(result.x)
    return {'protocol': 'positive_temperature_v1', 'fit_role': 'validation', 'validation_ids': ids, 'excluded_ids': excluded,
            'validation_probabilities': p.tolist(), 'validation_labels': y.astype(int).tolist(),
            'temperature': float(np.exp(log_temperature)), 'log_temperature': log_temperature,
            'status': status, 'reason': reason, 'validation_nll_before': before, 'validation_nll_after': loss(log_temperature),
            'fit_clipped_probabilities': int((clipped != p).sum()),
            'boundary_hit': bool(min(abs(log_temperature - v) for v in LOG_BOUNDS) < 1e-5),
            'epsilon': EPSILON, 'log_bounds': list(LOG_BOUNDS)}


def load_temperature(state):
    if not isinstance(state, dict):
        raise ValueError('Temperature state must be an object')
    try:
        expected = fit_temperature(state['validation_probabilities'], state['validation_labels'],
                                   validation_ids=state['validation_ids'], excluded_ids=state['excluded_ids'])
        if json.dumps(expected, sort_keys=True, allow_nan=False) != json.dumps(state, sort_keys=True, allow_nan=False):
            raise ValueError('Temperature state differs from its validation inputs or frozen protocol')
    except (KeyError, TypeError) as exc:
        raise ValueError('Invalid temperature state') from exc
    return expected


def apply_temperature(state, probabilities):
    frozen = load_temperature(state)
    p = np.asarray(probabilities, dtype=float)
    _binary(np.zeros(len(p)), p)
    clipped = np.clip(p, EPSILON, 1 - EPSILON)
    logits = np.log(clipped / (1 - clipped)) / frozen['temperature']
    calibrated = 1 / (1 + np.exp(-logits))
    return calibrated, {'application_clipped_probabilities': int((p != clipped).sum()),
                        'numerically_saturated_probabilities': int(((calibrated == 0) | (calibrated == 1)).sum()),
                        'temperature': frozen['temperature']}


def additive_logistic_explanation(features, parameters, feature_names):
    x, w = np.asarray(features, dtype=float), np.asarray(parameters, dtype=float)
    if x.ndim != 1 or w.shape != (len(x) + 1,) or len(feature_names) != len(x) or len(set(feature_names)) != len(feature_names) or not np.isfinite(x).all() or not np.isfinite(w).all():
        raise ValueError('Require finite transformed features, aligned homogeneous logistic parameters and unique names')
    contributions = x * w[:-1]
    raw = float(contributions.sum() + w[-1])
    used = float(np.clip(raw, -35, 35))
    return {'feature_names': list(feature_names), 'transformed_values': x.tolist(), 'coefficients': w[:-1].tolist(),
            'logit_contributions': contributions.tolist(), 'intercept': float(w[-1]), 'raw_logit': raw,
            'used_logit': used, 'logit_clipped': bool(raw != used), 'probability': float(1 / (1 + np.exp(-used))),
            'top_absolute_contribution_indices': np.argsort(-np.abs(contributions), kind='stable')[:5].tolist(),
            'baseline': 'zero in training-imputed standardized feature space; not a healthy or causal reference',
            'interpretation': 'exact per-model additive logit accounting; not causality or an explanation of seed-mean/calibrated probabilities'}
