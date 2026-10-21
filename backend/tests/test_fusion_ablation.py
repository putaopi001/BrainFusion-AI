import copy
import json

import numpy as np
import pytest

from app.research.entropy_topsis import apply_entropy_fusion, fit_entropy_topsis
from app.research.fusion_ablation import BRANCHES, evaluate_available_fusion, missing_scenarios, validation_sensitivity_plan


def state(matrix=None):
    return fit_entropy_topsis(matrix if matrix is not None else [[.9, .8, .1], [.7, .6, .3]],
                              branch_ids=list(BRANCHES), validation_patient_ids=['v1', 'v2'],
                              excluded_patient_ids=['train', 'eval'])


def test_hand_calculated_coverage_metrics_and_missing_weights():
    result = evaluate_available_fusion([[.2, .8], [np.nan, .7], [.4, np.nan], [np.nan, np.nan]],
                                      [0, 1, 0, 1], ['a', 'b', 'c', 'd'], [.25, .75])
    assert (result['total_patients'], result['successful_patients'], result['failed_patients']) == (4, 3, 1)
    assert result['coverage'] == .75
    np.testing.assert_allclose([row['probability'] for row in result['rows'][:3]], [.65, .7, .4])
    assert result['metrics']['auc'] == 1
    assert result['metrics']['balanced_accuracy'] == .75
    assert result['metrics']['brier'] == pytest.approx((.65 ** 2 + .3 ** 2 + .4 ** 2) / 3)
    assert result['rows'][3]['probability'] is None
    assert result['rows'][3]['status'] == 'failed'
    assert result['rows'][1]['effective_weights'] == [0, 1]


def test_single_branch_baseline_cannot_borrow_other_modality():
    values = [[np.nan, .9], [.2, np.nan]]
    single = evaluate_available_fusion(values, [1, 0], ['a', 'b'], [1, 0], allowed_branches=(True, False))
    fused = evaluate_available_fusion(values, [1, 0], ['a', 'b'], [1, 0])
    assert single['successful_patients'] == 1 and single['rows'][0]['status'] == 'failed'
    assert fused['successful_patients'] == 2 and fused['rows'][0]['probability'] == .9
    assert fused['rows'][0]['reasons'] == ['missing_branches_renormalized', 'zero_available_weight_uniform_available']


def test_all_failures_preserve_denominator_and_single_class_metrics_are_null():
    failed = evaluate_available_fusion([[np.nan, np.nan]] * 3, [0, 1, 1], ['a', 'b', 'c'], [.5, .5])
    assert failed['total_patients'] == failed['failed_patients'] == 3
    assert failed['metrics'] == {'auc': None, 'balanced_accuracy': None, 'brier': None}
    assert failed['coverage'] == 0
    single_class = evaluate_available_fusion([[.2, .4], [.8, .6]], [1, 1], ['a', 'b'], [.5, .5])
    assert single_class['metrics']['auc'] is None and single_class['metrics']['balanced_accuracy'] is None
    assert single_class['undefined_metrics']['auc'] == 'single_class_successful_subset'
    assert single_class['metrics']['brier'] == pytest.approx((.7 ** 2 + .3 ** 2) / 2)
    json.dumps(failed, allow_nan=False)


def test_missingness_is_identity_stable_under_patient_reordering():
    ids = ['b', 'a', 'c']
    original = missing_scenarios(ids)
    shuffled = missing_scenarios(ids[::-1])
    assert len(original) == 6
    for scenario, availability in original.items():
        np.testing.assert_array_equal(availability[::-1], shuffled[scenario])
    np.testing.assert_array_equal(original['alternating_single_missing'], [[True, False], [False, True], [False, True]])
    np.testing.assert_array_equal(original['one_all_missing'][1], [False, False])


def test_validation_plan_covers_all_frozen_changes_without_mutating_fit():
    fitted = state([[0, .5, 1], [1, .5, 0]])
    original = copy.deepcopy(fitted)
    plan = validation_sensitivity_plan(fitted)
    assert plan['variant_count'] == 40 and not plan['evaluation_data_used']
    assert len({v['name'] for v in plan['variants']}) == 40
    assert len([v for v in plan['variants'] if v['kind'] == 'metric_shift']) == 36
    assert len([v for v in plan['variants'] if v['kind'] == 'criterion_drop']) == 3
    assert any(v['change'] and v['change'].get('clipped') for v in plan['variants'])
    for variant in plan['variants']:
        assert variant['state']['validation_patient_ids'] == ['v1', 'v2']
        assert variant['state']['excluded_patient_ids'] == ['train', 'eval']
        assert sum(variant['state']['branch_weights']) == pytest.approx(1)
    assert fitted == original
    json.dumps(plan, allow_nan=False)


def test_diagnostics_predictions_never_depend_on_labels_and_match_entropy_application():
    fitted = state()
    probabilities = np.array([[.1, .8], [np.nan, .7], [.3, np.nan]])
    result = evaluate_available_fusion(probabilities, [0, 1, 0], ['a', 'b', 'c'], fitted['branch_weights'])
    reversed_labels = evaluate_available_fusion(probabilities, [1, 0, 1], ['a', 'b', 'c'], fitted['branch_weights'])
    assert result['rows'] == reversed_labels['rows']
    expected = apply_entropy_fusion(fitted, probabilities, branch_ids=list(BRANCHES))
    np.testing.assert_allclose([row['probability'] for row in result['rows']], expected['probabilities'])
    assert [row['effective_weights'] for row in result['rows']] == expected['effective_weights']
    assert [row['reasons'] for row in result['rows']] == expected['reasons']


@pytest.mark.parametrize('field,value', [('probabilities', [[np.inf, .5]]), ('probabilities', [[1.1, .5]]),
                                       ('labels', [2]), ('labels', [np.nan]), ('weights', [-.1, 1.1]),
                                       ('weights', [.2, .2]), ('weights', [np.nan, 1]),
                                       ('patient_ids', ['a', 'a']), ('allowed_branches', (False, False))])
def test_invalid_inputs_fail_without_creating_partial_predictions(field, value):
    arguments = dict(probabilities=[[.2, .7]], labels=[0], patient_ids=['a'], weights=[.5, .5])
    arguments[field] = value
    with pytest.raises(ValueError):
        evaluate_available_fusion(**arguments)
