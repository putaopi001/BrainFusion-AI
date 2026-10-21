import numpy as np


def topsis_weights(criteria, benefit=(True, True, False)):
    """Rows are models/clients; columns are validation AUC, balanced accuracy, Brier."""
    values = np.asarray(criteria, dtype=float)
    if values.ndim != 2 or not len(values) or values.shape[1] != len(benefit) or not np.isfinite(values).all():
        raise ValueError('TOPSIS requires a finite nonempty criteria matrix')
    if ((values < 0) | (values > 1)).any():
        raise ValueError('Validation criteria must be between zero and one')
    norms = np.linalg.norm(values, axis=0)
    normalized = values / np.where(norms > 0, norms, 1) / values.shape[1]
    high = np.where(benefit, normalized.max(axis=0), normalized.min(axis=0))
    low = np.where(benefit, normalized.min(axis=0), normalized.max(axis=0))
    best_distance = np.linalg.norm(normalized - high, axis=1)
    worst_distance = np.linalg.norm(normalized - low, axis=1)
    closeness = np.divide(worst_distance, best_distance + worst_distance,
                          out=np.zeros(len(values)), where=best_distance + worst_distance > 1e-12)
    weights = closeness / closeness.sum() if closeness.sum() > 1e-12 else np.full(len(values), 1 / len(values))
    return weights


def fuse(probabilities, weights):
    probabilities, weights = np.asarray(probabilities, dtype=float), np.asarray(weights, dtype=float)
    if probabilities.ndim != 2 or probabilities.shape[1] != len(weights) or not np.isfinite(probabilities).all():
        raise ValueError('Branch probabilities must align with weights')
    if ((probabilities < 0) | (probabilities > 1)).any() or not np.isfinite(weights).all() or (weights < 0).any() or not np.isclose(weights.sum(), 1):
        raise ValueError('Invalid probabilities or fusion weights')
    return probabilities @ weights
