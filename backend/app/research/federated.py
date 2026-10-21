import numpy as np
from sklearn.metrics import roc_auc_score, balanced_accuracy_score, brier_score_loss
from .topsis import topsis_weights


def metrics(labels, probabilities):
    return {'auc': float(roc_auc_score(labels, probabilities)),
            'balanced_accuracy': float(balanced_accuracy_score(labels, probabilities >= .5)),
            'brier': float(brier_score_loss(labels, probabilities))}


def probability(features, parameters):
    return 1 / (1 + np.exp(-np.clip(features @ parameters, -35, 35)))


def local_update(features, labels, parameters, steps, learning_rate=.05, l2=.01, *, proximal_mu=0.0):
    """Optimize local logistic loss; FedProx anchors at this round's input model.

    The proximal term includes the intercept, while the existing L2 term does
    not. mu=0 preserves the historical FedAvg/centralized update.
    Source: https://arxiv.org/abs/1812.06127 (FedProx local objective).
    """
    if (isinstance(proximal_mu, (bool, np.bool_))
            or not isinstance(proximal_mu, (int, float, np.floating))
            or not np.isfinite(proximal_mu) or proximal_mu < 0):
        raise ValueError('proximal_mu must be a finite nonnegative number')
    round_model = parameters.copy()
    parameters = parameters.copy()
    for _ in range(steps):
        gradient = features.T @ (probability(features, parameters) - labels) / len(labels)
        gradient[:-1] += l2 * parameters[:-1]
        if proximal_mu:
            gradient += proximal_mu * (parameters - round_model)
        parameters -= learning_rate * gradient
    if not np.isfinite(parameters).all():
        raise ValueError('Nonfinite client parameters')
    return parameters


def aggregate(parameters, weights):
    parameters, weights = np.asarray(parameters), np.asarray(weights)
    if parameters.ndim != 2 or len(parameters) != len(weights) or not np.isfinite(parameters).all() or not np.isfinite(weights).all() or (weights < 0).any() or not np.isclose(weights.sum(), 1):
        raise ValueError('Invalid aggregation input')
    return parameters.T @ weights


def partitions(train, labels, seed):
    rng = np.random.default_rng(seed)
    groups = [[], [], []]
    for label in (0, 1):
        for group, chunk in zip(groups, np.array_split(rng.permutation(train[labels[train] == label]), 3)):
            group.extend(chunk.tolist())
    return {'iid': [np.asarray(g, dtype=int) for g in groups],
            'label_skew': list(np.array_split(train[np.argsort(labels[train], kind='stable')], 3))}


def simulate(features, labels, train, validation, test, ids, seed, rounds=3, local_steps=2):
    # This is a centralized-preprocessing simulation, not a privacy-preserving system.
    initial = np.zeros(features.shape[1])
    result = {'architecture': 'same logistic model with 22 transformed features and intercept',
              'rounds': rounds, 'local_steps': local_steps, 'learning_rate': .05, 'l2': .01,
              'preprocessing': 'fitted centrally on training cohort only',
              'topsis_validation': 'common held-out validation pool', 'methods': {}}
    fitted = {}
    central = local_update(features[train], labels[train], initial, rounds * local_steps)
    result['methods']['centralized'] = {'test': metrics(labels[test], probability(features[test], central))}
    fitted['centralized'] = central
    for name, groups in partitions(train, labels, seed).items():
        joined = np.concatenate(groups)
        if len(joined) != len(set(joined)) or set(joined) != set(train) or any(not len(g) for g in groups):
            raise ValueError('Client partitions must be disjoint and cover the training cohort')
        for method in ('fedavg', 'validation_topsis'):
            parameters, trace = initial.copy(), []
            for round_id in range(rounds):
                clients = [local_update(features[g], labels[g], parameters, local_steps) for g in groups]
                sample_weights = np.asarray([len(g) for g in groups], dtype=float)
                sample_weights /= sample_weights.sum()
                quality = [metrics(labels[validation], probability(features[validation], p)) for p in clients]
                weights = sample_weights if method == 'fedavg' else topsis_weights([[m[k] for k in ('auc', 'balanced_accuracy', 'brier')] for m in quality])
                parameters = aggregate(clients, weights)
                trace.append({'round': round_id + 1, 'weights': weights.tolist(), 'validation': quality})
            key = name + '_' + method
            fitted[key] = parameters
            result['methods'][key] = {'client_patient_ids': [[ids[i] for i in g] for g in groups],
                                      'client_sizes': [len(g) for g in groups],
                                      'client_positive_counts': [int(labels[g].sum()) for g in groups],
                                      'round_trace': trace, 'test': metrics(labels[test], probability(features[test], parameters))}
    return result, fitted
