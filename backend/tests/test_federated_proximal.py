"""FedProx numerical checks on synthetic logistic objectives, no patient data."""
import numpy as np
import pytest

from app.research.federated import local_update


def test_proximal_update_matches_independent_objective_finite_difference():
    features = np.array([[-1.0, 1.0], [0.25, 1.0], [2.0, 1.0]])
    labels = np.array([0.0, 1.0, 1.0])
    anchor = np.array([0.4, -0.6])
    initial = anchor.copy()
    mu, l2, rate, steps = 1.7, 0.03, 0.1, 4

    def objective(weights):
        logits = features @ weights
        return (np.mean(np.logaddexp(0, logits) - labels * logits)
                + l2 / 2 * np.sum(weights[:-1] ** 2)
                + mu / 2 * np.sum((weights - anchor) ** 2))

    expected = anchor.copy()
    for _ in range(steps):
        gradient = np.empty_like(expected)
        for index in range(len(expected)):
            delta = np.zeros_like(expected)
            delta[index] = 1e-6
            gradient[index] = (objective(expected + delta) - objective(expected - delta)) / 2e-6
        expected -= rate * gradient

    actual = local_update(features, labels, anchor, steps, rate, l2, proximal_mu=mu)
    np.testing.assert_allclose(actual, expected, rtol=1e-8, atol=1e-9)
    np.testing.assert_array_equal(anchor, initial)


def test_zero_mu_preserves_historical_update_and_first_step_has_no_shrinkage():
    features = np.array([[0.0, 1.0], [2.0, 1.0]])
    labels = np.array([0.0, 1.0])
    anchor = np.array([0.3, -0.8])
    legacy = local_update(features, labels, anchor, 5)
    np.testing.assert_array_equal(legacy, local_update(features, labels, anchor, 5, proximal_mu=0))
    # At a nonzero round model, the proximal gradient starts at zero; this
    # distinguishes a global-model anchor from extra weight decay toward zero.
    np.testing.assert_array_equal(local_update(features, labels, anchor, 1),
                                  local_update(features, labels, anchor, 1, proximal_mu=2.0))


@pytest.mark.parametrize('mu', [-1.0, float('nan'), float('inf'), True, np.bool_(False), '1', None])
def test_invalid_mu_is_rejected_before_updating(mu):
    parameters = np.array([0.2, -0.1])
    before = parameters.copy()
    with pytest.raises(ValueError, match='proximal_mu'):
        local_update(np.array([[1.0, 1.0]]), np.array([1.0]), parameters, 2, proximal_mu=mu)
    np.testing.assert_array_equal(parameters, before)
