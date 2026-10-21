"""Full, bounded CPU federated comparison under docs/R3_FULL_PROTOCOL.md.

Training accepts only training/public-validation inputs. Evaluation is separate.
This is a centralized-preprocessing simulation, without a privacy guarantee.
"""
import hashlib
import time

import numpy as np
from sklearn.metrics import balanced_accuracy_score, roc_auc_score

from .entropy_topsis import fit_entropy_topsis
from .federated import aggregate, local_update, partitions, probability
from .topsis import topsis_weights

METHODS = ('centralized', 'local_only', 'fedavg', 'fedprox', 'validation_topsis', 'validation_entropy_topsis')
SCENARIOS = ('iid', 'label_skew')
SETTINGS = dict(rounds=20, local_steps=5, learning_rate=.05, l2=.01, proximal_mu=.1, initial_scale=.01)


def _ids(values):
    if not isinstance(values, (list, tuple)) or any(not isinstance(v, str) or not v.strip() for v in values) or len(set(values)) != len(values):
        raise ValueError('Patient IDs must be unique strings in an ordered list')
    return list(values)


def _data(features, labels, ids, *, empty=False):
    ids = _ids(ids)
    x, y = np.asarray(features, dtype=float), np.asarray(labels, dtype=float)
    if x.ndim != 2 or x.shape[1] < 2 or x.shape[0] != len(ids) or y.shape != (len(ids),) or (not empty and not ids):
        raise ValueError('Features/labels/IDs must align with a nonempty feature matrix')
    if not np.isfinite(x).all() or not np.isfinite(y).all() or not np.isin(y, [0, 1]).all() or not np.all(x[:, -1] == 1):
        raise ValueError('Require finite features, raw binary labels, and a final intercept column of ones')
    return x, y, ids


def _settings(settings):
    if set(settings) != set(SETTINGS):
        raise ValueError('Incomplete or unknown simulation settings')
    for name, limit in [('rounds', 50), ('local_steps', 20)]:
        value = settings[name]
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)) or not 1 <= value <= limit:
            raise ValueError('Invalid bounded integer update budget')
    for name in ('learning_rate', 'l2', 'proximal_mu', 'initial_scale'):
        value = settings[name]
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.number)) or not np.isfinite(value) or value < 0 or (name == 'learning_rate' and value == 0):
            raise ValueError('Invalid finite optimization setting')


def scores(labels, predictions):
    y, p = np.asarray(labels, dtype=float), np.asarray(predictions, dtype=float)
    if y.ndim != 1 or p.shape != y.shape or not np.isfinite(y).all() or not np.isin(y, [0, 1]).all() or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError('Invalid evaluation labels or probabilities')
    result = dict(total_patients=len(y), successful_patients=len(y), failed_patients=0,
                  auc=None, balanced_accuracy=None, brier=None, undefined={})
    if not len(y):
        result['undefined'] = {key: 'empty_center' for key in ('auc', 'balanced_accuracy', 'brier')}
    else:
        result['brier'] = float(np.mean((y - p) ** 2))
        if len(np.unique(y)) < 2:
            result['undefined'] = {key: 'single_class' for key in ('auc', 'balanced_accuracy')}
        else:
            result['auc'] = float(roc_auc_score(y, p))
            result['balanced_accuracy'] = float(balanced_accuracy_score(y, p >= .5))
    return result


def assign_centers(patient_ids, seed):
    return np.asarray([int.from_bytes(hashlib.sha256(f'{seed}:{p}'.encode()).digest()[:8], 'big') % 3
                       for p in _ids(patient_ids)], dtype=int)


def _candidate_weights(method, quality, sizes, validation_ids, excluded_ids):
    if method in ('fedavg', 'fedprox'):
        return np.asarray(sizes, dtype=float) / sum(sizes), {'reasons': ['training_sample_size']}
    matrix = np.asarray([[row[key] if row[key] is not None else np.nan for key in ('auc', 'balanced_accuracy', 'brier')]
                         for row in quality], dtype=float)
    if method == 'validation_entropy_topsis':
        fitted = fit_entropy_topsis(matrix, branch_ids=[f'client_{i}' for i in range(3)],
                                    validation_patient_ids=validation_ids, excluded_patient_ids=excluded_ids)
        return np.asarray(fitted['branch_weights']), fitted
    active = np.isfinite(matrix).all(axis=0)
    reasons = [f'criterion_dropped:{key}:undefined' for key, enabled in zip(('auc', 'balanced_accuracy', 'brier'), active) if not enabled]
    if not active.any():
        return np.ones(3) / 3, {'reasons': reasons + ['no_usable_criteria_uniform']}
    weights = topsis_weights(matrix[:, active], benefit=tuple(np.asarray([True, True, False])[active]))
    if np.ptp(matrix[:, active], axis=0).max() <= 1e-12:
        reasons.append('constant_criteria_uniform')
    return weights, {'reasons': reasons}


def fit_condition(train_features, train_labels, validation_features, validation_labels, *, train_ids,
                  validation_ids, excluded_patient_ids, seed, scenario, settings=None):
    """Fit all six methods with a shared initialization; no evaluation data API."""
    options = dict(SETTINGS if settings is None else settings)
    _settings(options)
    x, y, train_ids = _data(train_features, train_labels, train_ids)
    vx, vy, validation_ids = _data(validation_features, validation_labels, validation_ids)
    excluded = _ids(excluded_patient_ids)
    if (len(x) < 3 or vx.shape[1] != x.shape[1] or scenario not in SCENARIOS
            or set(train_ids) & set(validation_ids) or set(validation_ids) & set(excluded)
            or not set(train_ids) <= set(excluded)):
        raise ValueError('Invalid roles, feature widths, scenario, or insufficient client training rows')
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or seed < 0:
        raise ValueError('Seed must be a nonnegative integer')
    groups = partitions(np.arange(len(x)), y, seed)[scenario]
    joined = np.concatenate(groups)
    if any(not len(g) for g in groups) or len(joined) != len(x) or len(set(joined)) != len(x) or set(joined) != set(range(len(x))):
        raise ValueError('Client groups must be nonempty, disjoint, and cover train only')
    sizes = [len(g) for g in groups]
    initial = np.random.default_rng(seed).normal(0, options['initial_scale'], x.shape[1])
    initial_sha = hashlib.sha256(initial.tobytes()).hexdigest()
    fitted, method_reports = {}, {}
    payload = int(initial.nbytes)
    for method in METHODS:
        started = time.perf_counter()
        parameters = np.tile(initial, (3, 1)) if method == 'local_only' else initial.copy()
        trace = []
        for round_id in range(options['rounds']):
            round_started = time.perf_counter()
            local_seconds = []
            if method == 'centralized':
                before = time.perf_counter()
                parameters = local_update(x, y, parameters, options['local_steps'], options['learning_rate'], options['l2'])
                local_seconds.append(time.perf_counter() - before)
                candidates = [parameters]
            else:
                candidates = []
                for i, group in enumerate(groups):
                    before = time.perf_counter()
                    anchor = parameters[i] if method == 'local_only' else parameters
                    mu = options['proximal_mu'] if method == 'fedprox' else 0
                    candidates.append(local_update(x[group], y[group], anchor, options['local_steps'],
                                                    options['learning_rate'], options['l2'], proximal_mu=mu))
                    local_seconds.append(time.perf_counter() - before)
            before = time.perf_counter()
            quality = [scores(vy, probability(vx, model)) for model in candidates]
            quality_seconds = time.perf_counter() - before
            before = time.perf_counter()
            weights, weight_audit = None, None
            if method == 'local_only':
                parameters = np.asarray(candidates)
            elif method != 'centralized':
                weights, weight_audit = _candidate_weights(method, quality, sizes, validation_ids, excluded)
                parameters = aggregate(candidates, weights)
            aggregate_seconds = time.perf_counter() - before
            federated = method not in ('centralized', 'local_only')
            trace.append({'round': round_id + 1, 'aggregation_weights': None if weights is None else weights.tolist(),
                          'weight_audit': weight_audit, 'candidate_public_validation': quality,
                          'client_update_seconds': local_seconds, 'quality_seconds': quality_seconds,
                          'aggregation_seconds': aggregate_seconds, 'round_seconds': time.perf_counter() - round_started,
                          'sample_gradient_evaluations': options['local_steps'] * len(x),
                          'optimizer_steps_across_update_groups': options['local_steps'] * len(candidates),
                          'parameter_payload_bytes': {'downlink_per_client': [payload] * 3 if federated else [0] * 3,
                                                      'uplink_per_client': [payload] * 3 if federated else [0] * 3}})
        fitted[method] = parameters
        method_reports[method] = {'initial_sha256': initial_sha, 'parameter_layout': 'three_independent_local_models' if method == 'local_only' else 'single_global_model',
                                  'sample_gradient_evaluations': options['rounds'] * options['local_steps'] * len(x),
                                  'optimizer_steps_across_update_groups': sum(t['optimizer_steps_across_update_groups'] for t in trace),
                                  'parameter_payload_bytes': sum(sum(t['parameter_payload_bytes']['downlink_per_client']) + sum(t['parameter_payload_bytes']['uplink_per_client']) for t in trace),
                                  'fit_seconds': time.perf_counter() - started, 'round_trace': trace}
    return {'seed': int(seed), 'scenario': scenario, 'settings': options, 'feature_columns_including_intercept': x.shape[1],
            'initial_sha256': initial_sha, 'client_train_ids': [[train_ids[i] for i in g] for g in groups],
            'client_sizes': sizes, 'client_positive_counts': [int(y[g].sum()) for g in groups],
            'public_validation_ids': validation_ids, 'methods': method_reports}, fitted, initial


def evaluate_model(parameters, features, labels, patient_ids, seed):
    x, y, ids = _data(features, labels, patient_ids, empty=True)
    parameters = np.asarray(parameters, dtype=float)
    if parameters.shape not in ((x.shape[1],), (3, x.shape[1])) or not np.isfinite(parameters).all():
        raise ValueError('Invalid homogeneous model parameters')
    centers = assign_centers(ids, seed)
    p = np.empty(len(ids), dtype=float)
    per_center = []
    for center in range(3):
        selected = centers == center
        model = parameters if parameters.ndim == 1 else parameters[center]
        p[selected] = probability(x[selected], model)
        per_center.append({'center': center, 'patient_ids': [ids[i] for i in np.flatnonzero(selected)],
                           'metrics': scores(y[selected], p[selected])})
    worst = {}
    for metric in ('auc', 'balanced_accuracy', 'brier'):
        defined = [c['metrics'][metric] for c in per_center if c['metrics'][metric] is not None]
        worst[metric] = {'value': (max(defined) if metric == 'brier' else min(defined)) if defined else None,
                         'defined_centers': len(defined), 'undefined_centers': 3 - len(defined)}
    return {'pooled': scores(y, p), 'centers': per_center, 'worst_center': worst,
            'predictions': [{'patient_id': patient, 'simulated_center': int(centers[i]), 'target': int(y[i]), 'probability': float(p[i])}
                            for i, patient in enumerate(ids)]}
