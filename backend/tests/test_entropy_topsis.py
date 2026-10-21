import copy
import json
import math

import numpy as np
import pytest

from app.research.entropy_topsis import apply_entropy_fusion, fit_entropy_topsis, load_entropy_state
from app.research.topsis import topsis_weights


def fitted(criteria, branches=('clinical', 'radiomics')):
    return fit_entropy_topsis(criteria, branch_ids=list(branches), validation_patient_ids=['v1', 'v2'],
                              excluded_patient_ids=['train1', 'test1', 'demo1'])


def test_independent_hand_calculation_conflicting_criteria():
    state = fitted([[1, 0, 0], [0, 1, .5]])
    h = -(2 / 3 * math.log(2 / 3) + 1 / 3 * math.log(1 / 3)) / math.log(2)
    w = np.array([1, 1, 1 - h]) / (3 - h)
    a = math.sqrt(w[0] ** 2 + w[2] ** 2)
    expected = [a / (a + w[1]), w[1] / (a + w[1])]
    np.testing.assert_allclose(state['entropy'], [0, 0, h], atol=1e-14)
    np.testing.assert_allclose(state['criterion_weights'], w)
    np.testing.assert_allclose(state['branch_weights'], expected)
    assert state['branch_weights'][0] > .5


def test_dominance_preserves_zero_weights_and_records_extreme():
    state = fitted([[.9, .8, .1], [.7, .6, .3]])
    assert state['branch_weights'] == [1, 0]
    assert 'extreme_branch_weight' in state['reasons']
    np.testing.assert_array_equal(state['branch_weights'], topsis_weights([[.9, .8, .1], [.7, .6, .3]]))


def test_all_constant_including_zero_quality_is_uniform():
    state = fitted([[0, 0, 1]] * 3, ('a', 'b', 'c'))
    np.testing.assert_allclose(state['branch_weights'], [1 / 3] * 3)
    assert state['criterion_weights'] == [0, 0, 0]
    assert state['active_criteria'] == []
    assert 'no_informative_criteria_uniform_branches' in state['reasons']


def test_zero_entropy_is_maximum_information_and_equal_alternatives_tie():
    state = fitted([[1, 0, .2], [0, 1, .2]])
    assert state['entropy'] == [0, 0, None]
    assert state['criterion_weights'] == [.5, .5, 0]
    assert state['branch_weights'] == [.5, .5]


def test_missing_metric_drops_whole_column_without_imputation():
    state = fitted([[np.nan, .9, .2], [.8, .7, .2]])
    assert state['active_criteria'] == ['balanced_accuracy']
    assert state['criterion_weights'] == [0, 1, 0]
    assert 'criterion_dropped:auc:missing' in state['reasons']
    assert 'extreme_criterion_weight' in state['reasons']
    assert state['branch_weights'] == [1, 0]


def test_all_missing_and_single_branch_are_explicit_fallbacks():
    state = fitted([[np.nan] * 3] * 2)
    assert state['branch_weights'] == [.5, .5]
    state = fitted([[.8, .7, .2]], ('only',))
    assert state['branch_weights'] == [1]
    assert 'single_branch' in state['reasons']


def test_near_equal_entropy_and_distance_degeneracy_remain_finite():
    state = fitted([[.5, .5, .5], [.5 + 2e-12, .5, .5]])
    assert 'entropy_degenerate_equal_criteria' in state['reasons']
    assert np.isfinite(state['branch_weights']).all()
    tiny = fitted([[0, 0, 0], [2e-12, 2e-12, 2e-12]])
    assert np.isfinite(tiny['branch_weights']).all()


@pytest.mark.parametrize('matrix', [[[np.inf, .5, .2], [.8, .5, .2]],
                                  [[-.1, .5, .2], [.8, .5, .2]],
                                  [[1.01, .5, .2], [.8, .5, .2]], [[.8, .5], [.8, .5]], []])
def test_invalid_fit_metrics_rejected(matrix):
    with pytest.raises(ValueError):
        fitted(matrix)


def test_fit_identity_overlap_duplicates_and_empty_ids_rejected():
    for kw in [dict(branch_ids=['a', 'a'], validation_patient_ids=['v']),
               dict(branch_ids=['a', 'b'], validation_patient_ids=['v', 'v']),
               dict(branch_ids=['a', 'b'], validation_patient_ids=[]),
               dict(branch_ids=['a', 'b'], validation_patient_ids=['v'], excluded_patient_ids=['v']),
               dict(branch_ids=['a', 'b'], validation_patient_ids='v')]:
        with pytest.raises(ValueError):
            fit_entropy_topsis([[.8, .6, .2], [.6, .8, .3]], **kw)


def test_json_reload_and_state_mutation_are_checked():
    state = fitted([[np.nan, .8, .2], [.7, .6, .3]])
    assert load_entropy_state(json.loads(json.dumps(state, allow_nan=False))) == state
    for key, replacement in [('branch_weights', [.2, .8]), ('protocol', 'other'),
                             ('validation_patient_ids', ['different']), ('unknown', 1), ('fit_role', 'test')]:
        altered = copy.deepcopy(state)
        altered[key] = replacement
        with pytest.raises(ValueError):
            load_entropy_state(altered)


def test_apply_missing_zero_support_all_missing_and_order():
    state = fitted([[.9, .8, .1], [.7, .6, .3]])
    result = apply_entropy_fusion(state, [[np.nan, .7], [.2, np.nan], [.2, .9]], branch_ids=state['branch_ids'])
    assert result['probabilities'] == [.7, .2, .2]
    assert result['effective_weights'] == [[0, 1], [1, 0], [1, 0]]
    assert 'zero_available_weight_uniform_available' in result['reasons'][0]
    with pytest.raises(ValueError, match=r'rows \[1\]'):
        apply_entropy_fusion(state, [[.2, .9], [np.nan, np.nan]], branch_ids=state['branch_ids'])
    with pytest.raises(ValueError, match='order'):
        apply_entropy_fusion(state, [[.2, .9]], branch_ids=list(reversed(state['branch_ids'])))


@pytest.mark.parametrize('probabilities', [[[np.inf, .2]], [[-.1, .2]], [[1.1, .2]], [[.2]], []])
def test_invalid_application_probabilities_rejected(probabilities):
    state = fitted([[.8, .6, .2], [.6, .8, .3]])
    with pytest.raises(ValueError):
        apply_entropy_fusion(state, probabilities, branch_ids=state['branch_ids'])


def test_inference_row_order_batch_composition_and_input_immutability():
    state = fitted([[.8, .6, .2], [.6, .8, .3]])
    frozen = json.dumps(state, sort_keys=True)
    probabilities = np.array([[.2, .8], [.9, .1], [np.nan, .7]])
    original = probabilities.copy()
    full = apply_entropy_fusion(state, probabilities, branch_ids=state['branch_ids'])
    for i in range(3):
        single = apply_entropy_fusion(state, probabilities[i:i + 1], branch_ids=state['branch_ids'])
        assert single['probabilities'][0] == full['probabilities'][i]
        assert single['effective_weights'][0] == full['effective_weights'][i]
    backwards = apply_entropy_fusion(state, probabilities[::-1], branch_ids=state['branch_ids'])
    assert backwards['probabilities'] == full['probabilities'][::-1]
    np.testing.assert_array_equal(probabilities, original)
    assert json.dumps(state, sort_keys=True) == frozen


def test_branch_permutation_and_duplicate_alternatives_keep_identity():
    values = np.array([[.8, .6, .2], [.6, .8, .3], [.8, .6, .2]])
    state = fitted(values, ('a', 'b', 'c'))
    other = fitted(values[[1, 2, 0]], ('b', 'c', 'a'))
    np.testing.assert_allclose(other['branch_weights'], np.array(state['branch_weights'])[[1, 2, 0]])
    assert state['branch_weights'][0] == state['branch_weights'][2]


def test_zero_distance_tolerance_is_recorded_and_uniform():
    gap = 1.1e-12
    # Each column is variable, but the sum of weighted ideal distances is <1e-12.
    assert 1e-12 < gap
    assert (math.sqrt(2) + 1) * gap / (3 * math.sqrt(2) * .9) < 1e-12
    state = fitted([[.9, .9, .9], [.9 - gap, .9 - gap, .9 - gap]])
    assert len(state['active_criteria']) == 3
    assert 'entropy_degenerate_equal_criteria' in state['reasons']
    assert 'zero_topsis_distance_uniform_branches' in state['reasons']
    assert state['branch_weights'] == [.5, .5]
