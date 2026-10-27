"""Numerical guards for the fixed V2 model comparison utilities."""
import math

import numpy as np

from scripts import compare_ucsf_pdgm_survival_v2 as v2
from scripts import train_ucsf_pdgm_cox as base


def test_fast_harrell_matches_reference_implementation_with_tied_times():
    times = np.array([3, 3, 5, 7, 7, 9, 11, 13], dtype=float)
    events = np.array([1, 0, 1, 1, 0, 1, 0, 1], dtype=int)
    risk = np.array([0.8, 0.2, 0.4, 0.5, 0.3, 0.9, 0.1, 0.2])
    assert v2.fast_harrell_c_index(times, events, risk) == base.harrell_c_index(times, events, risk)


def test_json_safe_marks_undefined_metrics_as_null():
    result = v2.json_safe({"folds": [float("nan"), np.float64(0.5)], "missing": np.float64("inf")})
    assert result == {"folds": [None, 0.5], "missing": None}


def test_elastic_net_cox_converges_and_emits_finite_baseline():
    rng = np.random.default_rng(20261027)
    n = 100
    age = rng.normal(60, 12, n)
    sex = rng.integers(0, 2, n).astype(float)
    biopsy = rng.integers(0, 2, n).astype(float)
    latent = 0.25 * (age - 60) / 12 + 0.1 * sex - 0.08 * biopsy
    times = rng.exponential(scale=np.exp(-latent) * 650) + 10
    censoring = rng.exponential(scale=1100, size=n) + 20
    observed = np.minimum(times, censoring)
    events = (times <= censoring).astype(int)
    fitted = v2.fit_elastic_net_cox(np.column_stack([age, sex, biopsy]), observed, events)
    assert np.isfinite(fitted["beta"]).all()
    assert fitted["optimizer_iterations"] > 0
    assert np.isfinite(fitted["cumulative_hazard"]).all()
    assert np.all(np.diff(fitted["survival"]) <= 0)


def test_candidates_share_identical_patient_level_outer_folds():
    rng = np.random.default_rng(5)
    n = 100
    raw = np.column_stack([rng.uniform(25, 90, n), rng.integers(0, 2, n), rng.integers(0, 2, n)])
    times = rng.uniform(100, 2000, n)
    events = np.array([1] * 60 + [0] * 40)
    tokens = [f"synthetic-{i}" for i in range(n)]
    baseline = v2.run_candidate(raw, times, events, tokens, "age_sex_ridge")
    enhanced = v2.run_candidate(raw, times, events, tokens, "age_sex_biopsy_ridge")
    np.testing.assert_array_equal(baseline["oof_fold"], enhanced["oof_fold"])
    assert np.isfinite(baseline["oof_risk"]).all() and np.isfinite(enhanced["oof_risk"]).all()
