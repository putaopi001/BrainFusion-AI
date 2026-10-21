import copy
import json
import numpy as np
import pytest

from app.research.patient_statistics import (METRICS, additive_logistic_explanation, apply_temperature,
    binary_summary, bootstrap_metrics, fit_temperature, load_temperature, paired_difference,
    reliability_bins, stratified_patient_indices)


def test_hand_auc_ties_confusion_brier_sensitivity_specificity():
    result = binary_summary([0, 0, 1, 1], [.1, .5, .5, .9])
    assert result['metrics']['auc'] == .875
    assert result['metrics']['balanced_accuracy'] == .75
    assert result['metrics']['sensitivity'] == 1 and result['metrics']['specificity'] == .5
    assert result['metrics']['brier'] == pytest.approx((.01 + .25 + .25 + .01) / 4)
    assert result['confusion'] == dict(tp=2, fn=0, tn=1, fp=1)


def test_all_bin_edges_and_empty_bins_keep_every_patient():
    bins = reliability_bins([0, 0, 1, 1, 1, 1], [0, .2, .4, .6, .8, 1])
    assert [row['count'] for row in bins] == [1, 1, 1, 1, 2]
    assert bins[-1]['upper_inclusive']
    empty = reliability_bins([1], [.9])
    assert len(empty) == 5 and empty[0]['mean_probability'] is None and sum(b['count'] for b in empty) == 1
    assert binary_summary([], [])['metrics']['auc'] is None


def test_patient_strata_and_pairing_zero_difference_are_preserved():
    y = np.array([0, 1, 0, 1])
    indices = stratified_patient_indices(y, samples=31, seed=9)
    assert indices.shape == (31, 4)
    assert np.all(y[indices].sum(axis=1) == 2)
    a = bootstrap_metrics(y, [.2, .8, .4, .6], ['a', 'b', 'c', 'd'], indices)
    difference = paired_difference(a, a)
    for key in METRICS:
        assert difference['point_difference_left_minus_right'][key] == 0
        assert difference['intervals'][key]['lower'] == difference['intervals'][key]['upper'] == 0
        assert difference['intervals'][key]['degenerate']
    altered = bootstrap_metrics(y, [.2, .8, .4, .6], ['a', 'b', 'c', 'd'], indices[::-1])
    with pytest.raises(ValueError, match='identical'):paired_difference(a, altered)


def test_missing_class_and_undefined_resamples_are_not_fabricated():
    y = [1, 1, 1]
    result = bootstrap_metrics(y, [.5, .6, .7], ['a', 'b', 'c'], stratified_patient_indices(y, samples=9, seed=2))
    assert result['point']['metrics']['auc'] is None
    assert result['intervals']['auc']['valid_resamples'] == 0
    assert result['intervals']['auc']['undefined_resamples'] == 9
    assert result['intervals']['specificity']['lower'] is None
    assert result['intervals']['brier']['valid_resamples'] == 9
    json.dumps({k:v for k,v in result.items() if k!='samples'}, allow_nan=False)


def test_differences_use_paired_draws_instead_of_subtracting_interval_limits():
    y = [0, 0, 1, 1]
    indices = np.array([[0, 1, 2, 3], [0, 0, 2, 2], [1, 1, 3, 3]])
    a = bootstrap_metrics(y, [.1, .2, .6, .9], ['a','b','c','d'], indices)
    b = bootstrap_metrics(y, [.3, .4, .5, .7], ['a','b','c','d'], indices)
    result = paired_difference(a, b)
    j = METRICS.index('brier')
    expected = np.quantile(a['samples'][:,j]-b['samples'][:,j], [.025,.975])
    np.testing.assert_allclose([result['intervals']['brier']['lower'], result['intervals']['brier']['upper']],expected)


def test_temperature_fits_validation_only_positive_preserves_threshold_and_roundtrips():
    state = fit_temperature([.3,.7,.4,.6], [0,1,0,1], validation_ids=['v1','v2','v3','v4'], excluded_ids=['train','test'])
    assert state['status']=='fitted' and state['temperature']>0
    assert state['validation_nll_after']<state['validation_nll_before']
    assert load_temperature(json.loads(json.dumps(state)))==state
    p=np.array([.1,.5,.8]);calibrated,_=apply_temperature(state,p)
    np.testing.assert_array_equal(calibrated>=.5,p>=.5)
    changed=copy.deepcopy(state);changed['temperature']=2
    with pytest.raises(ValueError):load_temperature(changed)
    with pytest.raises(ValueError, match='overlap'):
        fit_temperature([.2,.8],[0,1],validation_ids=['v1','v2'],excluded_ids=['v1'])


def test_temperature_identity_fallbacks_are_explicit():
    state=fit_temperature([.2,.8],[1,1],validation_ids=['a','b'],excluded_ids=[])
    assert state['temperature']==1 and state['status']=='identity_fallback'
    state=fit_temperature([.5,.5],[0,1],validation_ids=['a','b'],excluded_ids=[])
    assert state['reason']=='zero_logits_identity'


def test_exact_additive_model_accounting_and_saturation():
    result=additive_logistic_explanation([2,-1],[.4,.2,-.3],['x','z'])
    assert result['logit_contributions']==[.8,-.2]
    assert result['raw_logit']==pytest.approx(.3)
    assert result['probability']==pytest.approx(1/(1+np.exp(-.3)))
    saturated=additive_logistic_explanation([100],[1,0],['x'])
    assert saturated['raw_logit']==100 and saturated['used_logit']==35 and saturated['logit_clipped']
    assert 'not causality' in result['interpretation']


@pytest.mark.parametrize('p', [[np.nan,.2],[np.inf,.2],[-.1,.2],[1.1,.2]])
def test_invalid_probabilities_reject_instead_of_dropping_patients(p):
    with pytest.raises(ValueError):binary_summary([0,1],p)


def test_patient_duplicates_wrong_indices_and_invalid_labels_rejected():
    with pytest.raises(ValueError):bootstrap_metrics([0,1],[.2,.8],['same','same'],np.array([[0,1]]))
    with pytest.raises(ValueError):bootstrap_metrics([0,1],[.2,.8],['a','b'],np.array([[0,2]]))
    with pytest.raises(ValueError):binary_summary([0,2],[.2,.8])
    with pytest.raises(ValueError):stratified_patient_indices([0,1],samples=True)


def test_temperature_numerical_saturation_is_reported():
    state=fit_temperature([.3,.7,.4,.6],[0,1,0,1],validation_ids=['a','b','c','d'],excluded_ids=[])
    calibrated,audit=apply_temperature(state,[0,1])
    assert audit['application_clipped_probabilities']==2
    assert audit['numerically_saturated_probabilities']==int(((calibrated==0)|(calibrated==1)).sum())
    assert np.isfinite(calibrated).all()
