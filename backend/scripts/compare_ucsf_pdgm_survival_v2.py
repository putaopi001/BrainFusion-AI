"""Compare fixed, prespecified UCSF-PDGM clinical Cox candidates on one patient-level CV.

All candidate features are available at the preoperative diagnostic MRI landmark
or are deterministic transforms of age. All outputs are aggregate except the
local-only OOF file, written to a protected runtime directory without patient IDs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.model_selection import StratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import train_ucsf_pdgm_cox as base

MODEL_ID = base.MODEL_ID
MODEL_VERSION = "2.0.0"
EXPECTED_CSV_SHA256 = "afc1c23a0eb0597b56e603741e72f2308b4860281187cd3808e05b7a0116fd78"
SEED = 20261027
FOLDS = 5
HORIZONS = (365.0, 730.0, 1095.0)
IBS_GRID = tuple(float(x) for x in range(180, 1096, 90))
BOOTSTRAPS = 1000
RIDGE_ALPHA = 0.01
ELASTIC_ALPHA = 0.01
ELASTIC_L1_RATIO = 0.5


class V2Error(ValueError):
    pass


def json_safe(value):
    """Map non-finite numeric results to JSON null without hiding their absence."""
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.floating, float)):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_cohort(csv_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    required = {"ID", "Sex", "Age at MRI", "Final pathologic diagnosis (WHO 2021)",
                "1-dead 0-alive", "OS", "Biopsy prior to imaging"}
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise V2Error("Official UCSF-PDGM v5 source is missing the audited field contract.")
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as error:
        raise V2Error("Could not read the pinned UCSF-PDGM v5 CSV.") from error
    if sha256_file(csv_path) != EXPECTED_CSV_SHA256:
        raise V2Error("Clinical CSV SHA-256 does not match the reviewed v5 source.")
    ids = [str(row.get("ID") or "").strip() for row in rows]
    if any(not value for value in ids) or len(set(ids)) != len(ids):
        raise V2Error("Empty or duplicate UCSF scan ID; refusing ambiguous patient splitting.")
    baseline = [row for row in rows if not re.search(r"_FU(?:\d|$)", row["ID"] or "")]
    gbm = [row for row in baseline if row["Final pathologic diagnosis (WHO 2021)"].strip()
           == "Glioblastoma, IDH-wildtype"]
    seen_patient = set()
    X, durations, events, tokens, biopsy = [], [], [], [], []
    excluded = {"invalid_age": 0, "unsupported_sex": 0, "invalid_os": 0,
                "invalid_status": 0, "unsupported_biopsy_value": 0}
    for row in gbm:
        patient_id = row["ID"].strip()
        patient_key = re.sub(r"_FU(?:\d.*|$)", "", patient_id)
        if patient_key in seen_patient:
            raise V2Error("Repeated patient records remain after baseline-only selection.")
        seen_patient.add(patient_key)
        try:
            age = float(row["Age at MRI"])
            duration = float(row["OS"])
        except (TypeError, ValueError):
            excluded["invalid_os"] += 1
            continue
        if not math.isfinite(age) or not 18 <= age <= 120:
            excluded["invalid_age"] += 1
            continue
        if row["Sex"].strip() not in {"F", "M"}:
            excluded["unsupported_sex"] += 1
            continue
        if not math.isfinite(duration) or duration <= 0:
            excluded["invalid_os"] += 1
            continue
        try:
            event_value = int(row["1-dead 0-alive"].strip())
        except (TypeError, ValueError):
            excluded["invalid_status"] += 1
            continue
        if event_value not in {0, 1}:
            excluded["invalid_status"] += 1
            continue
        biopsy_value = row["Biopsy prior to imaging"].strip()
        if biopsy_value not in {"Yes", "No"}:
            excluded["unsupported_biopsy_value"] += 1
            continue
        X.append([age, float(row["Sex"].strip() == "M"), float(biopsy_value == "Yes")])
        durations.append(duration)
        events.append(event_value)
        # Deliberately not emitted: IDs are used only transiently for one-row-per-patient checks.
        tokens.append(hashlib.sha256(patient_id.encode("utf-8")).hexdigest())
        biopsy.append(biopsy_value)
    x = np.asarray(X, dtype=float)
    t = np.asarray(durations, dtype=float)
    e = np.asarray(events, dtype=int)
    if len(x) < 100 or e.sum() < 50 or len(set(e.tolist())) != 2:
        raise V2Error("The eligible UCSF GBM cohort is insufficient for the fixed 5-fold protocol.")
    if len(set(tokens)) != len(tokens):
        raise V2Error("Patient key collision or duplicate patient in eligible baseline cohort.")
    summary = {
        "source_sha256": sha256_file(csv_path), "source_rows": len(rows),
        "baseline_rows": len(baseline), "followup_rows_excluded": len(rows) - len(baseline),
        "baseline_gbm_rows": len(gbm), "eligible_n": len(x), "events": int(e.sum()),
        "censored": int(len(e) - e.sum()), "exclusions": excluded,
        "all_patient_ids_unique": True, "one_baseline_row_per_patient": True,
        "biopsy_prior_to_imaging": {"yes": biopsy.count("Yes"), "no": biopsy.count("No")},
        "cohort": "TCIA UCSF-PDGM v5 baseline rows; final WHO-2021 Glioblastoma, IDH-wildtype.",
        "endpoint": "OS days from initial diagnosis to last clinical follow-up; event 1-dead 0-alive=1; censor=0, per TCIA v5 glossary.",
        "prediction_landmark": "Preoperative diagnostic MRI; covariates age at MRI, sex, and whether biopsy occurred before MRI.",
        "excluded_features": {
            "WHO CNS Grade": "constant within selected GBM cohort",
            "final diagnosis and IDH": "constant within selected cohort",
            "MGMT": "assay timing relative to the diagnosis time origin is not recorded",
            "EOR": "postoperative and unavailable at the MRI landmark",
            "radiomics": "no verified UCSF patient-level radiomics table is present in the reviewed local assets",
        },
        "ids_in_output": False,
    }
    # IDs are retained only in the in-memory tuple for local OOF alignment.
    summary["_transient_tokens"] = tokens
    return x, t, e, summary


def design_matrix(raw: np.ndarray, age_center: float, variant: str) -> np.ndarray:
    if variant == "age_sex_ridge":
        return raw[:, :2].copy()
    if variant == "age_sex_biopsy_ridge":
        return raw[:, :3].copy()
    if variant in {"age_sex_biopsy_elastic_net", "age_sex_quadratic_ridge"}:
        centered_age = (raw[:, 0] - age_center) / 10.0
        if variant == "age_sex_biopsy_elastic_net":
            return np.column_stack([raw[:, :3], centered_age ** 2])
        return np.column_stack([raw[:, :2], centered_age ** 2])
    raise V2Error(f"Unknown model candidate: {variant}")


def fit_elastic_net_cox(X: np.ndarray, times: np.ndarray, events: np.ndarray,
                        alpha: float = ELASTIC_ALPHA, l1_ratio: float = ELASTIC_L1_RATIO) -> dict:
    """FISTA with backtracking for standardized Efron Cox elastic-net loss."""
    Z, means, scales = base._standardize_fit(X)
    l1_penalty = alpha * l1_ratio
    l2_alpha = alpha * (1.0 - l1_ratio)

    def smooth(beta):
        return base._efron_loss_grad(beta, Z, times, events, l2_alpha)

    def objective(beta):
        value, _ = smooth(beta)
        return value + l1_penalty * float(np.abs(beta).sum())

    beta = np.zeros(Z.shape[1], dtype=float)
    extrapolated = beta.copy()
    momentum = 1.0
    lipschitz = 1.0
    converged = False
    for iteration in range(1, 20001):
        smooth_value, gradient = smooth(extrapolated)
        while True:
            candidate = np.sign(extrapolated - gradient / lipschitz) * np.maximum(
                np.abs(extrapolated - gradient / lipschitz) - l1_penalty / lipschitz, 0.0)
            delta = candidate - extrapolated
            candidate_smooth, _ = smooth(candidate)
            bound = smooth_value + float(gradient @ delta) + 0.5 * lipschitz * float(delta @ delta)
            if candidate_smooth <= bound + 1e-12:
                break
            lipschitz *= 2.0
            if lipschitz > 1e12:
                raise V2Error("Elastic-net Cox line search failed to find a stable step.")
        next_momentum = (1.0 + math.sqrt(1.0 + 4.0 * momentum * momentum)) / 2.0
        next_extrapolated = candidate + ((momentum - 1.0) / next_momentum) * (candidate - beta)
        if np.linalg.norm(candidate - beta) <= 1e-9 * (1.0 + np.linalg.norm(beta)):
            beta, converged = candidate, True
            break
        beta, extrapolated, momentum = candidate, next_extrapolated, next_momentum
    if not converged or not np.isfinite(beta).all():
        raise V2Error("Elastic-net Cox did not converge within the fixed iteration limit.")
    fitted = {"means": means, "scales": scales, "beta": beta,
              "optimizer_iterations": iteration, "objective": objective(beta),
              "times": None, "cumulative_hazard": None, "survival": None}
    # Breslow baseline hazard, evaluated with the same final standardized coefficients.
    eta = np.clip(Z @ beta, -30, 30)
    risk = np.exp(eta)
    base_times, cum_hazard, running = [], [], 0.0
    for time in np.unique(times[events == 1]):
        at_risk = times >= time
        deaths = (times == time) & (events == 1)
        running += float(deaths.sum()) / float(risk[at_risk].sum())
        base_times.append(float(time)); cum_hazard.append(running)
    fitted["times"] = np.asarray(base_times)
    fitted["cumulative_hazard"] = np.asarray(cum_hazard)
    fitted["survival"] = np.exp(-np.asarray(cum_hazard))
    return fitted


def fit_candidate(X: np.ndarray, times: np.ndarray, events: np.ndarray, variant: str) -> dict:
    if variant == "age_sex_biopsy_elastic_net":
        return fit_elastic_net_cox(X, times, events)
    return base.fit_cox(X, times, events, alpha=RIDGE_ALPHA)


def risk_and_survival(fitted: dict, X_train: np.ndarray, X_test: np.ndarray,
                      horizons: tuple[float, ...]) -> tuple[np.ndarray, np.ndarray]:
    Xz = (X_test - fitted["means"]) / fitted["scales"]
    risk = np.exp(np.clip(Xz @ fitted["beta"], -30, 30))
    probabilities = np.column_stack([base.survival_at(fitted, X_test, horizon) for horizon in horizons])
    return risk, probabilities


def brier_contributions(train_t, train_e, test_t, test_e, prediction, horizon):
    values, weights = np.zeros(len(test_t), dtype=float), np.zeros(len(test_t), dtype=float)
    g_h = base.censor_survival(train_t, train_e, horizon)
    for i, (duration, event, estimate) in enumerate(zip(test_t, test_e, prediction)):
        if duration <= horizon and event == 1:
            g = base.censor_survival(train_t, train_e, float(duration), left_limit=True)
            if g > 1e-8:
                values[i] = float(estimate) ** 2; weights[i] = 1.0 / g
        elif duration > horizon and g_h > 1e-8:
            values[i] = (1.0 - float(estimate)) ** 2; weights[i] = 1.0 / g_h
    return values, weights


def calibration_pair(train_t, train_e, test_t, test_e, predicted, horizon):
    # IPCW event-free proportion versus mean predicted survival; a descriptive
    # calibration-in-the-large statistic, not a calibration slope.
    observed, weights = [], []
    g_h = base.censor_survival(train_t, train_e, horizon)
    for duration, event in zip(test_t, test_e):
        if duration <= horizon and event == 1:
            g = base.censor_survival(train_t, train_e, float(duration), left_limit=True)
            if g > 1e-8:
                observed.append(0.0); weights.append(1.0 / g)
        elif duration > horizon and g_h > 1e-8:
            observed.append(1.0); weights.append(1.0 / g_h)
    return (float(np.mean(predicted)),
            float(np.average(observed, weights=weights)) if weights else float("nan"),
            len(weights))


def run_candidate(raw, times, events, tokens, variant):
    splitter = StratifiedKFold(n_splits=FOLDS, shuffle=True, random_state=SEED)
    n = len(times)
    oof_risk = np.full(n, np.nan)
    oof_survival = np.full((n, len(HORIZONS)), np.nan)
    oof_fold = np.full(n, -1, dtype=int)
    fold_results = []
    per_horizon_values = [np.zeros(n) for _ in HORIZONS]
    per_horizon_weights = [np.zeros(n) for _ in HORIZONS]
    calibration = {str(int(h)): [] for h in HORIZONS}
    for fold, (train_idx, test_idx) in enumerate(splitter.split(np.zeros(n), events), start=1):
        if set(np.asarray(tokens)[train_idx]) & set(np.asarray(tokens)[test_idx]):
            raise V2Error("A patient token crossed an outer fold boundary.")
        center = float(raw[train_idx, 0].mean())
        x_train = design_matrix(raw[train_idx], center, variant)
        x_test = design_matrix(raw[test_idx], center, variant)
        fitted = fit_candidate(x_train, times[train_idx], events[train_idx], variant)
        risk, predictions = risk_and_survival(fitted, x_train, x_test, HORIZONS)
        oof_risk[test_idx] = risk
        oof_survival[test_idx] = predictions
        oof_fold[test_idx] = fold
        c_index = base.harrell_c_index(times[test_idx], events[test_idx], risk)
        fold_brier, fold_cal = {}, {}
        for col, horizon in enumerate(HORIZONS):
            values, weights = brier_contributions(times[train_idx], events[train_idx],
                                                   times[test_idx], events[test_idx],
                                                   predictions[:, col], horizon)
            per_horizon_values[col][test_idx] = values
            per_horizon_weights[col][test_idx] = weights
            score = float(np.average(values, weights=weights)) if weights.sum() else float("nan")
            pred_mean, observed, n_scored = calibration_pair(
                times[train_idx], events[train_idx], times[test_idx], events[test_idx],
                predictions[:, col], horizon)
            fold_brier[str(int(horizon))] = score
            fold_cal[str(int(horizon))] = {"mean_predicted_survival": pred_mean,
                                            "ipcw_observed_survival": observed,
                                            "calibration_gap": pred_mean - observed,
                                            "n_observed_at_horizon": n_scored}
            calibration[str(int(horizon))].append(fold_cal[str(int(horizon))])
        fold_ibs = float("nan")
        ibs_scores = []
        for horizon in IBS_GRID:
            if horizon >= np.max(times[train_idx][events[train_idx] == 1]):
                continue
            _, p = risk_and_survival(fitted, x_train, x_test, (horizon,))
            values, weights = brier_contributions(times[train_idx], events[train_idx],
                                                   times[test_idx], events[test_idx], p[:, 0], horizon)
            if weights.sum():
                ibs_scores.append((horizon, float(np.average(values, weights=weights))))
        if len(ibs_scores) >= 2:
            fold_ibs = float(np.trapezoid([v for _, v in ibs_scores], [t for t, _ in ibs_scores]) /
                             (ibs_scores[-1][0] - ibs_scores[0][0]))
        fold_results.append({"fold": fold, "n_train": int(len(train_idx)), "n_test": int(len(test_idx)),
                             "events_test": int(events[test_idx].sum()), "c_index": float(c_index),
                             "ipcw_brier": fold_brier, "ibs": fold_ibs})
    if np.isnan(oof_risk).any() or np.isnan(oof_survival).any() or (oof_fold < 1).any():
        raise V2Error("Outer cross-validation did not produce one OOF prediction for every eligible patient.")
    pooled_c = base.harrell_c_index(times, events, oof_risk)
    brier_summary = {}
    for col, horizon in enumerate(HORIZONS):
        weights, values = per_horizon_weights[col], per_horizon_values[col]
        brier_summary[str(int(horizon))] = {
            "mean_fold_ipcw_brier": float(np.mean([f["ipcw_brier"][str(int(horizon))] for f in fold_results])),
            "pooled_oof_ipcw_brier": float(np.sum(values * weights) / weights.sum()) if weights.sum() else None,
            "fold_scores": [f["ipcw_brier"][str(int(horizon))] for f in fold_results],
            "calibration_in_the_large": {
                "mean_predicted_survival": float(np.mean([v["mean_predicted_survival"] for v in calibration[str(int(horizon))]])),
                "mean_ipcw_observed_survival": float(np.nanmean([v["ipcw_observed_survival"] for v in calibration[str(int(horizon))]])),
                "fold_gaps": [v["calibration_gap"] for v in calibration[str(int(horizon))]],
                "interpretation": "Descriptive fold-level calibration-in-the-large; no calibration slope estimated."}}
    ibs_folds = [item["ibs"] for item in fold_results if math.isfinite(item["ibs"])]
    return {"candidate": variant, "folds": fold_results,
            "mean_fold_harrell_c_index": float(np.mean([item["c_index"] for item in fold_results])),
            "sd_fold_harrell_c_index": float(np.std([item["c_index"] for item in fold_results], ddof=1)),
            "pooled_oof_harrell_c_index": float(pooled_c),
            "ipcw_brier_at_days": brier_summary,
            "mean_fold_ibs": float(np.mean(ibs_folds)) if ibs_folds else None,
            "fold_ibs": [item["ibs"] for item in fold_results],
            "oof_risk": oof_risk, "oof_survival": oof_survival, "oof_fold": oof_fold,
            "brier_values": per_horizon_values, "brier_weights": per_horizon_weights,
            "validation_scope": "Internal patient-level 5-fold CV only; never external validation."}


def fast_harrell_c_index(times, events, risk):
    times = np.asarray(times, dtype=float)
    events = np.asarray(events, dtype=int)
    risk = np.asarray(risk, dtype=float)
    comparable = (events[:, None] == 1) & (times[:, None] < times[None, :])
    count = int(comparable.sum())
    if not count:
        return float("nan")
    score = (risk[:, None] > risk[None, :]).astype(float)
    score += 0.5 * (risk[:, None] == risk[None, :])
    return float(score[comparable].sum() / count)


def bootstrap_c_index(times, events, risk, seed=SEED):
    rng = np.random.default_rng(seed)
    values = []
    n = len(times)
    for _ in range(BOOTSTRAPS):
        indices = rng.integers(0, n, n)
        value = fast_harrell_c_index(times[indices], events[indices], risk[indices])
        if math.isfinite(value):
            values.append(value)
    if len(values) < BOOTSTRAPS * 0.8:
        return None
    return [float(x) for x in np.quantile(values, [0.025, 0.975])]


def bootstrap_delta(times, events, candidate_risk, baseline_risk, seed=SEED + 1):
    rng = np.random.default_rng(seed)
    n = len(times)
    values = []
    for _ in range(BOOTSTRAPS):
        indices = rng.integers(0, n, n)
        c = fast_harrell_c_index(times[indices], events[indices], candidate_risk[indices])
        b = fast_harrell_c_index(times[indices], events[indices], baseline_risk[indices])
        if math.isfinite(c) and math.isfinite(b):
            values.append(c - b)
    return [float(x) for x in np.quantile(values, [0.025, 0.975])] if len(values) >= BOOTSTRAPS * 0.8 else None


def paired_brier_delta(candidate, baseline, col):
    cv, cw = candidate["brier_values"][col], candidate["brier_weights"][col]
    bv, bw = baseline["brier_values"][col], baseline["brier_weights"][col]
    common = (cw > 0) & (bw > 0)
    if not common.any():
        return None
    # Identical folds and censoring estimates make these weights equal. Check rather than assume.
    if not np.allclose(cw[common], bw[common], rtol=0, atol=1e-12):
        raise V2Error("Paired Brier comparison did not use identical evaluable patients/weights.")
    w = cw[common]
    return float(np.average(cv[common] - bv[common], weights=w))


def choose_model(results: dict[str, dict], times, events) -> tuple[str, dict]:
    baseline = results["age_sex_ridge"]
    baseline_ci = bootstrap_c_index(times, events, baseline["oof_risk"])
    comparisons = []
    for name, result in results.items():
        if name == "age_sex_ridge":
            continue
        delta = result["pooled_oof_harrell_c_index"] - baseline["pooled_oof_harrell_c_index"]
        ci = bootstrap_delta(times, events, result["oof_risk"], baseline["oof_risk"])
        fold_wins = sum(a["c_index"] > b["c_index"] for a, b in zip(result["folds"], baseline["folds"]))
        brier_delta = {str(int(h)): paired_brier_delta(result, baseline, i)
                       for i, h in enumerate(HORIZONS)}
        stable = bool(ci and ci[0] > 0 and delta >= 0.01 and fold_wins >= 4 and
                      sum(value is not None and value <= 0.005 for value in brier_delta.values()) >= 2)
        comparisons.append({"candidate": name, "paired_oof_delta_c_index": float(delta),
                            "paired_bootstrap_95pct_ci": ci, "folds_with_higher_c_index": fold_wins,
                            "paired_oof_ipcw_brier_delta_candidate_minus_baseline": brier_delta,
                            "stable_improvement_rule_passed": stable})
    eligible = [item for item in comparisons if item["stable_improvement_rule_passed"]]
    selected = max(eligible, key=lambda item: results[item["candidate"]]["pooled_oof_harrell_c_index"])["candidate"] if eligible else "age_sex_ridge"
    return selected, {"baseline_pooled_oof_c_index_95pct_ci": baseline_ci,
                      "paired_comparisons": comparisons,
                      "selection_rule": "Select a non-baseline candidate only if paired OOF C-index delta >=0.01, paired percentile-bootstrap 95% CI lower bound >0, >=4/5 outer folds improve, and paired IPCW Brier is non-worse within 0.005 at >=2/3 horizons. Otherwise retain age+sex ridge baseline.",
                      "selection_note": "Bootstrap intervals are descriptive and do not account for dependence between overlapping CV training folds."}


def fit_final(raw, times, events, selected):
    center = float(raw[:, 0].mean())
    X = design_matrix(raw, center, selected)
    fitted = fit_candidate(X, times, events, selected)
    age_max = float(raw[:, 0].max())
    names = {
        "age_sex_ridge": ["age_at_mri_years", "sex_M"],
        "age_sex_biopsy_ridge": ["age_at_mri_years", "sex_M", "biopsy_prior_to_imaging_yes"],
        "age_sex_biopsy_elastic_net": ["age_at_mri_years", "sex_M", "biopsy_prior_to_imaging_yes", "age_quadratic"],
        "age_sex_quadratic_ridge": ["age_at_mri_years", "sex_M", "age_quadratic"],
    }[selected]
    schema = {"inputs": ["age_years", "sex"], "sex_categories": ["F", "M"],
              "encoding": {"sex_M": "1 for M, 0 for F"},
              "feature_timepoint": "Preoperative diagnostic MRI"}
    if selected in {"age_sex_biopsy_ridge", "age_sex_biopsy_elastic_net"}:
        schema["inputs"].append("biopsy_prior_to_imaging")
        schema["biopsy_categories"] = ["No", "Yes"]
        schema["encoding"]["biopsy_prior_to_imaging_yes"] = "1 for Yes, 0 for No"
    if "quadratic" in selected:
        schema["age_quadratic_transform"] = {"feature": "age_quadratic", "formula": "((age_years - age_center_years) / 10)^2", "age_center_years": center}
    model_type = "CoxPH"
    penalty = {"type": "ridge", "alpha": RIDGE_ALPHA}
    if selected == "age_sex_biopsy_elastic_net":
        penalty = {"type": "elastic_net", "alpha": ELASTIC_ALPHA, "l1_ratio": ELASTIC_L1_RATIO}
    elif selected == "age_sex_biopsy_ridge" or selected == "age_sex_quadratic_ridge":
        penalty = {"type": "ridge", "alpha": RIDGE_ALPHA}
    baseline = {"times_days": fitted["times"].tolist(),
                "cumulative_hazard": fitted["cumulative_hazard"].tolist(),
                "survival": fitted["survival"].tolist(),
                "estimator": "Breslow baseline cumulative hazard from selected full-cohort fit"}
    model = {
        "artifact_schema_version": 1, "model_id": MODEL_ID, "model_version": MODEL_VERSION,
        "model_type": "CoxPH", "algorithm": "Cox proportional hazards",
        "research_only": True, "selected_candidate": selected,
        "dataset": {"id": base.DATASET_ID, "version": base.DATASET_VERSION,
                    "official_source": "https://www.cancerimagingarchive.net/collection/ucsf-pdgm/",
                    "clinical_csv": "UCSF-PDGM-metadata_v5.csv", "clinical_csv_sha256": EXPECTED_CSV_SHA256,
                    "license": "CC BY 4.0", "cohort": "Baseline WHO-2021 final diagnosis Glioblastoma, IDH-wildtype"},
        "endpoint": {"status": base.ENDPOINT_STATUS, "official_endpoint_validated": True,
                     "time_unit": "days", "origin": "initial diagnosis",
                     "event_definition": "1-dead 0-alive == 1 at last clinical follow-up",
                     "censor_definition": "1-dead 0-alive == 0; right-censored at official OS follow-up time",
                     "source_definition": "TCIA UCSF-PDGM v5 metadata glossary"},
        "features": {"names": names, "means": fitted["means"].tolist(), "scales": fitted["scales"].tolist(),
                     "coefficients_standardized": fitted["beta"].tolist(),
                     "training_ranges": {"age_years": [float(raw[:, 0].min()), age_max]},
                     "input_schema": schema,
                     "preprocessing": "Feature transform center and standardization are fitted using only the training fold during CV; final parameters are fit on the complete eligible baseline cohort."},
        "training": {"n": int(len(times)), "events": int(events.sum()), "censored": int(len(times) - events.sum()),
                     "cohort_definition": "One baseline record per UCSF-PDGM v5 patient; final WHO-2021 GBM, IDH-wildtype; valid positive OS and documented vital status.",
                     "feature_timepoint": "Preoperative diagnostic MRI; diagnosis-to-MRI interval is not encoded.",
                     "penalty": penalty, "optimizer": "SciPy L-BFGS-B Efron Cox" if selected != "age_sex_biopsy_elastic_net" else "FISTA proximal gradient with backtracking; Efron Cox elastic-net"},
        "baseline": baseline,
        "validation": {"scope": "Internal patient-level 5-fold CV only", "external_validation": False,
                       "selection_results": "See protected runtime comparison result manifest."},
        "limitations": ["Research-only model from a single public center; not a clinical decision tool.",
                        "The OS clock starts at initial diagnosis while age is measured at MRI; the diagnosis-to-MRI interval is not encoded.",
                        "Only features documented at the preoperative MRI landmark are considered. EOR and molecular assay timing are omitted.",
                        "Five-fold internal CV is not external validation. Individual API predictions are never persisted; de-identified-by-omission OOF rows are kept only in the protected local runtime comparison directory, not in this model artifact or source control.",
                        "The API requires an explicit UCSF-PDGM v5 cohort declaration for RESEARCH_CASE; the declaration is researcher-attested, not automatically identity-verified."]}
    return model, fitted


def write_outputs(csv_path: Path, output_root: Path, cohort: dict, raw, times, events):
    if output_root.exists() and any(output_root.iterdir()):
        raise V2Error("Output directory is not empty; use a new versioned runtime directory.")
    output_root.mkdir(parents=True, exist_ok=True)
    tokens = cohort.pop("_transient_tokens")
    candidates = ["age_sex_ridge", "age_sex_biopsy_ridge", "age_sex_quadratic_ridge", "age_sex_biopsy_elastic_net"]
    results = {name: run_candidate(raw, times, events, tokens, name) for name in candidates}
    selected, comparison = choose_model(results, times, events)
    model, final_fit = fit_final(raw, times, events, selected)
    from app.services.survival_model import sha256_file as service_sha256
    from scripts.train_ucsf_pdgm_cox import write_model
    model_dir = output_root / "model-artifact"
    validation_for_selected = results[selected]
    model["validation"].update({
        "protocol": "Same stratified 5-fold patient-level outer split for every candidate; transforms and all fitted preprocessing learned inside each training fold.",
        "random_seed": SEED, "folds": FOLDS,
        "mean_fold_harrell_c_index": validation_for_selected["mean_fold_harrell_c_index"],
        "sd_fold_harrell_c_index": validation_for_selected["sd_fold_harrell_c_index"],
        "pooled_oof_harrell_c_index": validation_for_selected["pooled_oof_harrell_c_index"],
        "pooled_oof_harrell_c_index_95pct_bootstrap_ci": bootstrap_c_index(times, events, validation_for_selected["oof_risk"], seed=SEED + 2),
        "ipcw_brier_at_days": validation_for_selected["ipcw_brier_at_days"],
        "mean_fold_ibs": validation_for_selected["mean_fold_ibs"],
        "external_validation": False,
    })
    model = json_safe(model)
    comparison_file = output_root / "model-comparison.json"
    aggregate_candidates = {}
    for name, result in results.items():
        aggregate_candidates[name] = {key: value for key, value in result.items()
                                      if key not in {"oof_risk", "oof_survival", "oof_fold", "brier_values", "brier_weights"}}
        aggregate_candidates[name]["pooled_oof_c_index_95pct_bootstrap_ci"] = bootstrap_c_index(times, events, result["oof_risk"], seed=SEED + 3)
    paired = comparison["paired_comparisons"]
    for row in paired:
        row["pooled_oof_c_index"] = results[row["candidate"]]["pooled_oof_harrell_c_index"]
    table = [{"candidate": name, "model_type": "CoxPH" if "elastic_net" not in name else "ElasticNetCoxPH",
              "n": int(len(times)), "events": int(events.sum()), "censored": int(len(times)-events.sum()),
              "mean_fold_c_index": result["mean_fold_harrell_c_index"],
              "sd_fold_c_index": result["sd_fold_harrell_c_index"],
              "pooled_oof_c_index": result["pooled_oof_harrell_c_index"],
              "brier_365": result["ipcw_brier_at_days"]["365"]["mean_fold_ipcw_brier"],
              "brier_730": result["ipcw_brier_at_days"]["730"]["mean_fold_ipcw_brier"],
              "brier_1095": result["ipcw_brier_at_days"]["1095"]["mean_fold_ipcw_brier"],
              "mean_fold_ibs": result["mean_fold_ibs"],
              "selected": name == selected} for name, result in results.items()]
    comparison_csv = output_root / "model-comparison.csv"
    with comparison_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(table[0]))
        writer.writeheader(); writer.writerows(table)
    model["validation"]["candidate_comparison"] = {
        "table": table,
        "paired_comparisons": comparison["paired_comparisons"],
        "selection_rule": comparison["selection_rule"],
        "selected_candidate": selected,
        "selection_note": comparison["selection_note"],
    }
    hashes = write_model(model, {"model_id": MODEL_ID, "model_version": MODEL_VERSION,
                                 "dataset_id": base.DATASET_ID, "dataset_version": base.DATASET_VERSION,
                                 "clinical_csv_sha256": EXPECTED_CSV_SHA256,
                                 "training": model["training"], "validation": model["validation"],
                                 "patient_level_outputs_saved": False}, model_dir)
    # The shared V1 writer intentionally pins its own legacy version. Repair the
    # V2 manifest identity here so the service's manifest/artifact check agrees.
    manifest_path = model_dir / "model-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["model_version"] = MODEL_VERSION
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    hashes["manifest_sha256"] = service_sha256(manifest_path)
    payload = {"status": "EXPLORATORY_MODEL_COMPARISON_COMPLETE", "model_id": MODEL_ID,
               "model_version": MODEL_VERSION, "dataset_id": base.DATASET_ID,
               "dataset_version": base.DATASET_VERSION, "source_sha256": EXPECTED_CSV_SHA256,
               "cohort": cohort, "cv": {"folds": FOLDS, "seed": SEED,
                                        "patient_level": True, "shared_outer_split": True,
                                        "preprocessing_fit_within_training_fold": True},
               "candidate_table": table, "candidates": aggregate_candidates,
               "selection": {**comparison, "selected_model": selected,
                             "selection_reason": "Stable improvement rule passed." if selected != "age_sex_ridge" else "No candidate met the prespecified paired improvement rule; retain the age+sex ridge baseline."},
               "non_run_candidates": {"RSF": "NOT_RUN: scikit-survival (sksurv) is unavailable in approved environments; no dependency was installed.",
                                      "radiomics_fusion": "NOT_RUN: no locally verified UCSF patient-level radiomics crosswalk/table is available."},
               "artifact": {"directory": str(model_dir), **hashes},
               "privacy": "Oof predictions are in a local protected runtime file without identifiers; no patient-level artifact or output is included in source control."}
    payload = json_safe(payload)
    comparison_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    oof_path = output_root / "oof-predictions.csv"
    with oof_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["eligible_row_index", "outer_fold", "event", "time_days", "model", "oof_relative_risk", "survival_365d", "survival_730d", "survival_1095d"])
        final = results[selected]
        for index in range(len(times)):
            writer.writerow([index, int(final["oof_fold"][index]), int(events[index]), float(times[index]), selected,
                             float(final["oof_risk"][index]), *[float(value) for value in final["oof_survival"][index]]])
    (output_root / "cohort-summary.json").write_text(json.dumps(cohort, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_root / "run-contract.json").write_text(json.dumps({
        "script": "backend/scripts/compare_ucsf_pdgm_survival_v2.py",
        "script_sha256": sha256_file(Path(__file__).resolve()), "source_sha256": EXPECTED_CSV_SHA256,
        "seed": SEED, "folds": FOLDS, "candidate_order": candidates, "selected": selected,
        "python": sys.version, "numpy": np.__version__, "scipy": __import__("scipy").__version__,
        "scikit_learn": __import__("sklearn").__version__, "outer_oof_rows": int(len(times)),
        "oof_predictions_sha256": sha256_file(oof_path), "comparison_sha256": sha256_file(comparison_file),
        "comparison_csv_sha256": sha256_file(comparison_csv),
        "artifact_sha256": hashes["artifact_sha256"], "manifest_sha256": hashes["manifest_sha256"],
        "summary_sha256": hashes["summary_sha256"], "patient_ids_in_outputs": False,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clinical-csv", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.clinical_csv.is_file():
        parser.error("UCSF-PDGM v5 clinical CSV does not exist.")
    raw, times, events, cohort = load_cohort(args.clinical_csv)
    result = write_outputs(args.clinical_csv, args.output_root, cohort, raw, times, events)
    print(json.dumps({"status": result["status"], "training": result["artifact"],
                      "candidate_table": result["candidate_table"],
                      "selected": result["selection"]["selected_model"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except V2Error as error:
        print(f"UCSF_SURVIVAL_V2_BLOCKED: {error}", file=sys.stderr)
        raise SystemExit(2)
