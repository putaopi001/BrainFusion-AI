import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.compare_ucsf_reference_radiomics_fusion_v2 import cv_candidate, impute_fold, ipcw_brier
from scripts.download_ucsf_fusion_cohort_v2 import safe_error


def test_fold_imputation_uses_training_median_only():
    train = np.asarray([[1.0, np.nan], [3.0, 4.0], [5.0, 6.0]])
    test = np.asarray([[100.0, np.nan]])
    imputed_train, imputed_test = impute_fold(train, test)
    assert imputed_train[0, 1] == 5.0
    assert imputed_test[0, 1] == 5.0
    assert imputed_test[0, 0] == 100.0
    assert np.isfinite(imputed_train).all()
    assert np.isfinite(imputed_test).all()


def test_synthetic_patient_level_ridge_cv_returns_monotone_oof_survival():
    rng = np.random.default_rng(20261027)
    n = 120
    clinical = np.column_stack([rng.normal(60, 9, n), rng.integers(0, 2, n)])
    radiomics = rng.normal(size=(n, 4))
    linear = (clinical[:, 0] - 60) / 10 * 0.25 + clinical[:, 1] * 0.2
    event_time = rng.exponential(350 / np.exp(linear))
    censor_time = rng.exponential(900, n)
    times = np.minimum(event_time, censor_time)
    events = (event_time <= censor_time).astype(int)
    result = cv_candidate(clinical, radiomics, times, events, "clinical_age_sex_ridge")
    assert len(result["folds"]) == 5
    assert np.isfinite(result["_oof_risk"]).all()
    assert np.isfinite(result["_oof_survival"]).all()
    assert np.all((result["_oof_survival"] >= 0) & (result["_oof_survival"] <= 1))
    assert np.all(result["_oof_survival"][:, 1:] <= result["_oof_survival"][:, :-1] + 1e-12)
    assert set(result["_oof_fold"]) == {1, 2, 3, 4, 5}


def test_ipcw_brier_uses_full_test_cohort_denominator():
    train_t = np.asarray([2.0, 5.0, 8.0, 12.0])
    train_e = np.ones(4, dtype=int)
    test_t = np.asarray([5.0, 15.0, 3.0])
    test_e = np.asarray([1, 1, 0])
    predicted = np.asarray([0.8, 0.7, 0.5])
    score, observed = ipcw_brier(train_t, train_e, test_t, test_e, predicted, 10.0)
    assert observed == 2
    assert np.isclose(score, (0.8**2 + (1 - 0.7)**2) / 3)


def test_synthetic_radiomics_and_fusion_candidates_share_valid_cv_contract():
    rng = np.random.default_rng(48)
    n = 200
    clinical = np.column_stack([rng.normal(60, 9, n), rng.integers(0, 2, n)])
    radiomics = rng.normal(size=(n, 4))
    linear = (clinical[:, 0] - 60) / 10 * 0.08 + radiomics[:, 0] * 0.05
    event_time = rng.exponential(1000 / np.exp(linear))
    censor_time = rng.exponential(500, n)
    times = np.minimum(event_time, censor_time)
    events = (event_time <= censor_time).astype(int)
    for name in ("radiomics_ridge", "radiomics_elastic_net", "clinical_radiomics_ridge", "clinical_radiomics_elastic_net"):
        result = cv_candidate(clinical, radiomics, times, events, name)
        assert len(result["folds"]) == 5
        assert np.isfinite(result["pooled_oof_c_index"])
        assert np.isfinite(result["_oof_survival"]).all()


def test_download_error_summary_never_persists_signed_url_query():
    from requests.exceptions import SSLError

    signed = "https://cdn.example/file?Policy=private-policy&Signature=private-signature"
    summary = safe_error(SSLError(f"TLS EOF with URL: {signed}"))
    assert "SSLError" in summary
    assert "private-policy" not in summary
    assert "private-signature" not in summary
    assert "cdn.example" not in summary
