import copy
import numpy as np
import pytest

from app.research.federated_full import METHODS, SETTINGS, assign_centers, evaluate_model, fit_condition, scores


def inputs():
    x = np.column_stack([np.arange(9) / 4 - 1, np.ones(9)])
    y = np.array([0, 1, 0, 1, 0, 1, 0, 1, 0])
    vx = np.array([[-.4, 1], [.7, 1], [0, 1]])
    return dict(train_features=x, train_labels=y, validation_features=vx, validation_labels=[0, 1, 0],
                train_ids=[f't{i}' for i in range(9)], validation_ids=['v0', 'v1', 'v2'],
                excluded_patient_ids=[f't{i}' for i in range(9)] + ['eval'], seed=17, scenario='label_skew')


def fit(settings=None, **changes):
    arguments = inputs(); arguments.update(changes)
    options = {**SETTINGS, 'rounds': 2, 'local_steps': 3}
    if settings: options.update(settings)
    return fit_condition(**arguments, settings=options)


def test_first_round_fedavg_matches_independent_pooled_gradient_and_budget():
    report, models, initial = fit({'rounds': 1, 'local_steps': 1, 'initial_scale': 0, 'l2': 0})
    x, y = inputs()['train_features'], inputs()['train_labels']
    expected = -.05 * (x.T @ (.5 - y) / len(y))
    np.testing.assert_allclose(models['centralized'], expected, rtol=0, atol=1e-15)
    np.testing.assert_allclose(models['fedavg'], expected, rtol=0, atol=1e-15)
    np.testing.assert_array_equal(models['fedavg'], models['fedprox'])
    for method in METHODS:
        assert report['methods'][method]['sample_gradient_evaluations'] == 9
        assert report['methods'][method]['initial_sha256'] == report['initial_sha256']
    assert report['methods']['fedavg']['parameter_payload_bytes'] == 3 * 2 * 2 * 8
    assert report['methods']['local_only']['parameter_payload_bytes'] == 0
    assert report['methods']['centralized']['parameter_payload_bytes'] == 0
    np.testing.assert_allclose(report['methods']['fedavg']['round_trace'][0]['aggregation_weights'], [1 / 3] * 3)


def test_mu_zero_full_simulation_matches_fedavg_and_local_only_stays_separate():
    report, models, _ = fit({'proximal_mu': 0})
    np.testing.assert_array_equal(models['fedavg'], models['fedprox'])
    assert models['local_only'].shape == (3, 2)
    assert not np.allclose(models['local_only'][0], models['local_only'][2])
    assert all(r['aggregation_weights'] is None for r in report['methods']['local_only']['round_trace'])
    assert [v for group in report['client_train_ids'] for v in group].__len__() == 9
    assert report['client_positive_counts'][0] == 0


def test_seed_shared_across_scenarios_and_inputs_not_mutated():
    data = inputs(); before = data['train_features'].copy()
    report, models, initial = fit()
    other, other_models, other_initial = fit(scenario='iid')
    np.testing.assert_array_equal(initial, other_initial)
    np.testing.assert_array_equal(models['centralized'], other_models['centralized'])
    np.testing.assert_array_equal(data['train_features'], before)
    assert report['methods']['fedavg']['sample_gradient_evaluations'] == 2 * 3 * 9
    assert other['methods']['local_only']['sample_gradient_evaluations'] == 2 * 3 * 9


def test_validation_single_class_is_explicit_and_topsis_retains_all_clients():
    report, models, _ = fit(validation_labels=[1, 1, 1])
    for method in ('validation_topsis', 'validation_entropy_topsis'):
        for row in report['methods'][method]['round_trace']:
            assert len(row['aggregation_weights']) == 3
            assert sum(row['aggregation_weights']) == pytest.approx(1)
            assert all(q['auc'] is None and q['balanced_accuracy'] is None for q in row['candidate_public_validation'])
    assert any('auc' in reason for reason in report['methods']['validation_topsis']['round_trace'][0]['weight_audit']['reasons'])


def test_local_evaluation_uses_identity_center_model_not_average():
    ids = ['eval0', 'eval1', 'eval2']
    models = np.array([[0., -2.], [0., 0.], [0., 2.]])
    result = evaluate_model(models, np.ones((3, 2)), [0, 1, 0], ids, 17)
    for row, center in zip(result['predictions'], assign_centers(ids, 17)):
        assert row['probability'] == pytest.approx(1 / (1 + np.exp(-models[center, 1])))
    np.testing.assert_array_equal(assign_centers(ids, 17)[::-1], assign_centers(ids[::-1], 17))
    assert len(result['centers']) == 3


def test_empty_single_class_centers_and_worst_defined_counts_are_retained():
    result = evaluate_model(np.zeros(2), np.array([[1., 1.]]), [1], ['only'], 17)
    assert sum(c['metrics']['total_patients'] for c in result['centers']) == 1
    assert sum(c['metrics']['total_patients'] == 0 for c in result['centers']) == 2
    assert result['worst_center']['auc'] == {'value': None, 'defined_centers': 0, 'undefined_centers': 3}
    assert result['pooled']['auc'] is None
    assert result['pooled']['brier'] == .25
    assert scores([], [])['undefined']['auc'] == 'empty_center'


@pytest.mark.parametrize('change', [dict(validation_ids=['t0', 'v1', 'v2']),
                                   dict(train_ids=['t0'] * 9), dict(excluded_patient_ids=['eval']),
                                   dict(scenario='unknown'), dict(seed=-1)])
def test_role_partition_seed_violations_rejected(change):
    with pytest.raises(ValueError): fit(**change)


@pytest.mark.parametrize('settings', [dict(rounds=True), dict(local_steps=0), dict(proximal_mu=-1),
                                     dict(learning_rate=float('nan')), dict(initial_scale=-1)])
def test_invalid_optimization_budget_rejected(settings):
    with pytest.raises(ValueError): fit(settings)


def test_repeated_client_rows_rejected_even_when_the_union_covers_train(monkeypatch):
    import app.research.federated_full as full
    malformed = [np.array([0, 0, 1, 2]), np.array([3, 4, 5]), np.array([6, 7, 8])]
    # Set membership alone looks correct, but one patient receives duplicate work.
    assert set(np.concatenate(malformed)) == set(range(9))
    monkeypatch.setattr(full, 'partitions', lambda *args: {'label_skew': malformed})
    with pytest.raises(ValueError, match='disjoint'):
        fit()
