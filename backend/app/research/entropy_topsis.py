"""Offline global entropy-TOPSIS, frozen in docs/R2_ENTROPY_PROTOCOL.md.

This module does not activate a model or mutate the legacy fusion API.
"""
import hashlib
import json

import numpy as np

PROTOCOL = 'brainfusion_entropy_topsis_v1'
CRITERIA = ('auc', 'balanced_accuracy', 'brier')
BENEFIT = (True, True, False)
TOL = 1e-12


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _ids(values, name, *, allow_empty=False):
    if not isinstance(values, (list, tuple)):
        raise ValueError(f'{name} must be an ordered list')
    result = list(values)
    if (not result and not allow_empty) or any(not isinstance(i, str) or not i.strip() for i in result):
        raise ValueError(f'{name} requires nonempty string IDs')
    if len(set(result)) != len(result):
        raise ValueError(f'{name} contains duplicate IDs')
    return result


def fit_entropy_topsis(criteria, *, branch_ids, validation_patient_ids, excluded_patient_ids=()):
    """Fit only declared shared validation metrics; callers must verify provenance.

    Missing metrics are NaN (JSON null). Excluded IDs include train/evaluation/demo.
    No prediction probabilities or evaluation labels are consumed by this function.
    """
    branches = _ids(branch_ids, 'branch_ids')
    patients = _ids(validation_patient_ids, 'validation_patient_ids')
    excluded = _ids(excluded_patient_ids, 'excluded_patient_ids', allow_empty=True)
    if set(patients) & set(excluded):
        raise ValueError('Validation patients overlap excluded train/evaluation/development patients')
    values = np.asarray(criteria, dtype=float)
    if values.shape != (len(branches), len(CRITERIA)):
        raise ValueError('Criteria must align with branch IDs and the three frozen criteria')
    if np.isinf(values).any() or ((values < 0) | (values > 1)).any():
        raise ValueError('Metrics must be in [0,1], with NaN only for missing metrics')
    m = len(branches)
    active, reasons = [], []
    for j, name in enumerate(CRITERIA):
        if np.isnan(values[:, j]).any():
            reasons.append(f'criterion_dropped:{name}:missing')
        elif np.ptp(values[:, j]) <= TOL:
            reasons.append(f'criterion_dropped:{name}:constant')
        else:
            active.append(j)
    entropy = [None] * 3
    criterion_weights = np.zeros(3)
    best_distance, worst_distance, closeness = np.zeros(m), np.zeros(m), np.zeros(m)
    branch_weights = np.full(m, 1 / m)
    if m == 1:
        reasons.append('single_branch')
    elif not active:
        reasons.append('no_informative_criteria_uniform_branches')
    else:
        quality = values[:, active].copy()
        for k, j in enumerate(active):
            if not BENEFIT[j]:
                quality[:, k] = 1 - quality[:, k]
        proportions = quality / quality.sum(axis=0)
        # Avoid evaluating log(0), rather than relying on a hidden NaN replacement.
        logarithms = np.zeros_like(proportions)
        np.log(proportions, out=logarithms, where=proportions > 0)
        h = np.clip(-(proportions * logarithms).sum(axis=0) / np.log(m), 0, 1)
        divergence = np.maximum(0, 1 - h)
        for k, j in enumerate(active):
            entropy[j] = float(h[k])
        if divergence.sum() <= TOL:
            criterion_weights[active] = 1 / len(active)
            reasons.append('entropy_degenerate_equal_criteria')
        else:
            criterion_weights[active] = divergence / divergence.sum()
        raw = values[:, active]
        norms = np.linalg.norm(raw, axis=0)
        weighted = raw / np.where(norms > 0, norms, 1) * criterion_weights[active]
        directions = np.asarray(BENEFIT)[active]
        ideal = np.where(directions, weighted.max(axis=0), weighted.min(axis=0))
        anti_ideal = np.where(directions, weighted.min(axis=0), weighted.max(axis=0))
        best_distance = np.linalg.norm(weighted - ideal, axis=1)
        worst_distance = np.linalg.norm(weighted - anti_ideal, axis=1)
        total_distance = best_distance + worst_distance
        closeness = np.divide(worst_distance, total_distance, out=np.zeros(m), where=total_distance > TOL)
        if closeness.sum() <= TOL:
            reasons.append('zero_topsis_distance_uniform_branches')
        else:
            branch_weights = closeness / closeness.sum()
    if criterion_weights.max() > .95:
        reasons.append('extreme_criterion_weight')
    if m > 1 and branch_weights.max() > .95:
        reasons.append('extreme_branch_weight')
    return {
        'schema': 1, 'protocol': PROTOCOL, 'criteria_names': list(CRITERIA), 'benefit': list(BENEFIT),
        'branch_ids': branches, 'fit_role': 'validation', 'validation_patient_ids': patients,
        'excluded_patient_ids': excluded,
        'validation_patient_ids_sha256': hashlib.sha256(_json(patients).encode()).hexdigest(),
        'criteria': [[None if np.isnan(v) else float(v) for v in row] for row in values],
        'active_criteria': [CRITERIA[j] for j in active], 'entropy': entropy,
        'criterion_weights': criterion_weights.tolist(), 'best_distance': best_distance.tolist(),
        'worst_distance': worst_distance.tolist(), 'closeness': closeness.tolist(),
        'branch_weights': branch_weights.tolist(), 'reasons': reasons,
    }


def load_entropy_state(payload):
    """Validate a JSON round trip by recomputing the entire fitted state.

    This is consistency validation, not proof of the declared data's authenticity.
    """
    if not isinstance(payload, dict):
        raise ValueError('Entropy state must be an object')
    try:
        expected = fit_entropy_topsis(payload['criteria'], branch_ids=payload['branch_ids'],
                                      validation_patient_ids=payload['validation_patient_ids'],
                                      excluded_patient_ids=payload['excluded_patient_ids'])
        if _json(expected) != _json(payload):
            raise ValueError('Entropy state differs from its frozen protocol or fit inputs')
    except (KeyError, TypeError, OverflowError) as exc:
        raise ValueError('Invalid entropy state') from exc
    return expected


def apply_entropy_fusion(state, probabilities, *, branch_ids):
    """Apply frozen global weights; missing probabilities must be explicit NaN.

    Returns per-row effective weights and fallback reasons, with no refitting.
    """
    frozen = load_entropy_state(state)
    if _ids(branch_ids, 'branch_ids') != frozen['branch_ids']:
        raise ValueError('Prediction branch order differs from the fitted order')
    values = np.asarray(probabilities, dtype=float)
    if values.ndim != 2 or not len(values) or values.shape[1] != len(branch_ids):
        raise ValueError('Probabilities must be nonempty patient by frozen branch matrix')
    if np.isinf(values).any() or ((values < 0) | (values > 1)).any():
        raise ValueError('Probabilities must be in [0,1], with NaN only for missing branches')
    available = ~np.isnan(values)
    empty = np.flatnonzero(~available.any(axis=1)).tolist()
    if empty:
        raise ValueError(f'All branches missing at patient rows {empty}; no predictions produced')
    global_weights = np.asarray(frozen['branch_weights'])
    effective = available * global_weights
    reasons = []
    for i, present in enumerate(available):
        row_reasons = []
        if not present.all():
            row_reasons.append('missing_branches_renormalized')
        if effective[i].sum() <= TOL:
            effective[i] = present.astype(float)
            row_reasons.append('zero_available_weight_uniform_available')
        effective[i] /= effective[i].sum()
        reasons.append(row_reasons)
    result = np.where(available, values, 0) * effective
    return {'probabilities': result.sum(axis=1).tolist(), 'effective_weights': effective.tolist(),
            'reasons': reasons, 'protocol': PROTOCOL, 'branch_ids': frozen['branch_ids']}
