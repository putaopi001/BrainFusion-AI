"""Descriptive R2 diagnostics frozen in docs/R2_ABLATION_PROTOCOL.md.

Validation perturbation plans never take evaluation labels or probabilities.
Missingness is synthetic and identity-based; nothing selects a deployment model.
"""
from collections import Counter

import numpy as np
from sklearn.metrics import balanced_accuracy_score, roc_auc_score

from .entropy_topsis import CRITERIA, TOL, fit_entropy_topsis, load_entropy_state

BRANCHES = ('clinical', 'reference_mask_radiomics')
SHIFTS = (.01, .05, .10)
SCENARIOS = ('complete', 'clinical_missing', 'radiomics_missing',
             'alternating_single_missing', 'one_all_missing', 'all_missing')
CLINICAL_GRID = tuple(i / 20 for i in range(21))


def _patients(patient_ids):
    if not isinstance(patient_ids, (list, tuple)) or not patient_ids:
        raise ValueError('Patient IDs must be a nonempty ordered list')
    if any(not isinstance(p, str) or not p.strip() for p in patient_ids) or len(set(patient_ids)) != len(patient_ids):
        raise ValueError('Patient IDs must be unique nonempty strings')
    return list(patient_ids)


def validation_sensitivity_plan(state):
    """Produce baseline, leave-one-criterion-out, and all frozen metric shifts."""
    base = load_entropy_state(state)
    if base['branch_ids'] != list(BRANCHES):
        raise ValueError('Sensitivity v1 requires the two registered branches in order')
    original = np.asarray(base['criteria'], dtype=float)
    choices = [('baseline', 'baseline', original.copy(), None)]
    for j, criterion in enumerate(CRITERIA):
        altered = original.copy()
        altered[:, j] = np.nan
        choices.append(('drop:' + criterion, 'criterion_drop', altered, {'criterion': criterion}))
    for i, branch in enumerate(BRANCHES):
        for j, criterion in enumerate(CRITERIA):
            for magnitude in SHIFTS:
                for sign in (-1, 1):
                    delta = sign * magnitude
                    altered = original.copy()
                    before = original[i, j]
                    altered[i, j] = np.clip(before + delta, 0, 1)
                    after = altered[i, j]
                    change = {'branch': branch, 'criterion': criterion, 'requested_delta': delta,
                              'actual_delta': None if np.isnan(before) else float(after - before),
                              'clipped': False if np.isnan(before) else bool(after != before + delta),
                              'source_missing': bool(np.isnan(before))}
                    choices.append((f'shift:{branch}:{criterion}:{delta:+.2f}', 'metric_shift', altered, change))
    variants = []
    for name, kind, matrix, change in choices:
        fitted = fit_entropy_topsis(matrix, branch_ids=base['branch_ids'],
                                    validation_patient_ids=base['validation_patient_ids'],
                                    excluded_patient_ids=base['excluded_patient_ids'])
        weights = np.asarray(fitted['branch_weights'])
        distance = np.abs(weights - np.asarray(base['branch_weights']))
        variants.append({'name': name, 'kind': kind, 'change': change, 'state': fitted,
                         'branch_weight_l1_from_baseline': float(distance.sum()),
                         'branch_weight_max_abs_from_baseline': float(distance.max()),
                         'top_branches': [branch for branch, weight in zip(BRANCHES, weights)
                                          if abs(weight - weights.max()) <= TOL]})
    return {'protocol': 'brainfusion_fusion_ablation_v1', 'fit_role': 'validation',
            'evaluation_data_used': False, 'variant_count': len(variants), 'variants': variants}


def missing_scenarios(patient_ids):
    """Return availability masks; depends only on IDs, not probabilities/labels."""
    ids = _patients(patient_ids)
    order = {p: i for i, p in enumerate(sorted(ids))}
    output = {}
    for name in SCENARIOS:
        present = np.ones((len(ids), 2), dtype=bool)
        if name == 'clinical_missing':
            present[:, 0] = False
        elif name == 'radiomics_missing':
            present[:, 1] = False
        elif name == 'alternating_single_missing':
            for row, patient in enumerate(ids):
                present[row, order[patient] % 2] = False
        elif name == 'one_all_missing':
            present[ids.index(min(ids))] = False
        elif name == 'all_missing':
            present[:] = False
        output[name] = present
    return output


def evaluate_available_fusion(probabilities, labels, patient_ids, weights, *, allowed_branches=(True, True)):
    """Audit every patient, including failures; metrics are conditional on success.

    Labels affect metrics only. A single-branch baseline cannot borrow the other
    modality; fusion with zero support falls back on allowed observed branches.
    """
    ids = _patients(patient_ids)
    values, target, weight = np.asarray(probabilities, dtype=float), np.asarray(labels, dtype=float), np.asarray(weights, dtype=float)
    if values.shape != (len(ids), 2) or target.shape != (len(ids),):
        raise ValueError('Probabilities and binary labels must align with patient IDs')
    if np.isinf(values).any() or ((values < 0) | (values > 1)).any():
        raise ValueError('Probabilities must be in [0,1], with NaN only for missing')
    if not np.isfinite(target).all() or not np.isin(target, [0, 1]).all():
        raise ValueError('Target must contain only raw binary values 0/1')
    if weight.shape != (2,) or not np.isfinite(weight).all() or (weight < 0).any() or not np.isclose(weight.sum(), 1, rtol=0, atol=TOL):
        raise ValueError('Frozen branch weights must be nonnegative and sum to one')
    if len(allowed_branches) != 2 or any(not isinstance(v, (bool, np.bool_)) for v in allowed_branches) or not any(allowed_branches):
        raise ValueError('Allowed branches must be two booleans with at least one allowed')
    allowed = np.asarray(allowed_branches, dtype=bool)
    rows, successful, predictions = [], [], []
    counters = Counter()
    for i, patient in enumerate(ids):
        observed = ~np.isnan(values[i])
        present = observed & allowed
        record = {'patient_id': patient, 'observed_branches': [b for b, v in zip(BRANCHES, observed) if v],
                  'allowed_branches': [b for b, v in zip(BRANCHES, allowed) if v],
                  'effective_weights': [0., 0.], 'probability': None, 'status': 'failed', 'reasons': []}
        if not present.any():
            record['reasons'].append('no_allowed_branch_available')
        else:
            effective = weight * present
            if (allowed & ~observed).any():
                record['reasons'].append('missing_branches_renormalized')
            if effective.sum() <= TOL:
                effective = present.astype(float)
                record['reasons'].append('zero_available_weight_uniform_available')
            effective /= effective.sum()
            probability = float(np.sum(np.where(present, values[i], 0) * effective))
            record.update(status='succeeded', effective_weights=effective.tolist(), probability=probability)
            successful.append(i)
            predictions.append(probability)
        counters.update(record['reasons'])
        rows.append(record)
    result_metrics = dict(auc=None, balanced_accuracy=None, brier=None)
    undefined = {}
    if successful:
        y, p = target[successful], np.asarray(predictions)
        result_metrics['brier'] = float(np.mean((y - p) ** 2))
        if len(np.unique(y)) == 2:
            result_metrics['auc'] = float(roc_auc_score(y, p))
            result_metrics['balanced_accuracy'] = float(balanced_accuracy_score(y, p >= .5))
        else:
            undefined.update(auc='single_class_successful_subset', balanced_accuracy='single_class_successful_subset')
    else:
        undefined = {name: 'no_successful_patients' for name in result_metrics}
    return {'total_patients': len(ids), 'successful_patients': len(successful),
            'failed_patients': len(ids) - len(successful), 'coverage': len(successful) / len(ids),
            'metrics_scope': 'successful_patients_only', 'metrics': result_metrics,
            'undefined_metrics': undefined, 'reason_counts': dict(counters), 'rows': rows}
