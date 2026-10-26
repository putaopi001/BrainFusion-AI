"""Train the fixed, research-only UCSF-PDGM clinical Cox baseline.

The script accepts only the TCIA clinical CSV and emits aggregate model
artifacts. It never writes patient IDs, predictions, or row-level outputs.
No hyperparameter search is performed: the ridge penalty and CV protocol are
fixed in the model contract so the result is reproducible.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
from scipy.optimize import minimize
from sklearn.model_selection import StratifiedKFold

MODEL_ID = "ucsf-pdgm-clinical-cox-research"
MODEL_VERSION = "1.0.0"
DATASET_ID = "UCSF-PDGM"
DATASET_VERSION = "TCIA Version 5 (2025-05-30)"
ENDPOINT_STATUS = "OFFICIAL_DATASET_ENDPOINT_DOCUMENTED"
RIDGE_ALPHA = 0.01
CV_FOLDS = 5
RANDOM_SEED = 20261026
FEATURE_NAMES = ["age_at_mri_years", "sex_M"]


class TrainingError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_gbm_cohort(csv_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    required = {"ID", "Sex", "Age at MRI", "Final pathologic diagnosis (WHO 2021)",
                "1-dead 0-alive", "OS"}
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise TrainingError("Official clinical CSV is missing required UCSF-PDGM v5 columns.")
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as error:
        raise TrainingError("Could not read the official UCSF-PDGM clinical CSV.") from error
    baseline = [row for row in rows if not re.search(r"_FU(?:\d|$)", row["ID"] or "")]
    gbm = [row for row in baseline if (row["Final pathologic diagnosis (WHO 2021)"].strip()
                                       == "Glioblastoma, IDH-wildtype")]
    seen: set[str] = set()
    X, times, events = [], [], []
    exclusions = {"missing_or_invalid_os": 0, "missing_or_invalid_age": 0,
                  "unsupported_sex": 0, "invalid_event_status": 0}
    for row in gbm:
        # Baseline ID is the patient unit. Follow-up exams have already been excluded.
        patient_key = (row["ID"] or "").strip()
        if not patient_key or patient_key in seen:
            raise TrainingError("Duplicate or empty baseline patient ID; refusing patient-level leakage.")
        seen.add(patient_key)
        try:
            age = float(row["Age at MRI"])
            if not math.isfinite(age) or age < 18 or age > 120:
                exclusions["missing_or_invalid_age"] += 1
                continue
        except (TypeError, ValueError):
            exclusions["missing_or_invalid_age"] += 1
            continue
        sex = (row["Sex"] or "").strip()
        if sex not in ("M", "F"):
            exclusions["unsupported_sex"] += 1
            continue
        try:
            duration = float(row["OS"])
            if not math.isfinite(duration) or duration <= 0:
                exclusions["missing_or_invalid_os"] += 1
                continue
        except (TypeError, ValueError):
            exclusions["missing_or_invalid_os"] += 1
            continue
        status = (row["1-dead 0-alive"] or "").strip()
        if status not in ("0", "1"):
            exclusions["invalid_event_status"] += 1
            continue
        X.append([age, float(sex == "M")])
        times.append(duration)
        events.append(int(status == "1"))
    if len(X) < 50 or sum(events) < 20 or len(set(events)) != 2:
        raise TrainingError("The validated GBM cohort is too small or lacks events/censors.")
    stats = {
        "csv_records": len(rows), "baseline_records": len(baseline),
        "followup_records_excluded": len(rows) - len(baseline),
        "gbm_diagnosis_records": len(gbm), "training_n": len(X),
        "events": int(sum(events)), "censored": int(len(events) - sum(events)),
        "exclusions": exclusions,
        "cohort_definition": "Baseline rows with final WHO-2021 diagnosis exactly Glioblastoma, IDH-wildtype; one row per patient.",
        "feature_timepoint": "Preoperative MRI; age at MRI and sex only. MRI age is not asserted to equal age at initial diagnosis.",
    }
    return np.asarray(X, dtype=float), np.asarray(times, dtype=float), np.asarray(events, dtype=int), stats


def _standardize_fit(X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    means = X.mean(axis=0)
    scales = X.std(axis=0, ddof=0)
    scales = np.where(scales > 1e-12, scales, 1.0)
    return (X - means) / scales, means, scales


def _efron_loss_grad(beta: np.ndarray, X: np.ndarray, times: np.ndarray,
                     events: np.ndarray, alpha: float) -> tuple[float, np.ndarray]:
    eta = np.clip(X @ beta, -30, 30)
    risk_score = np.exp(eta)
    log_likelihood = 0.0
    gradient = np.zeros_like(beta)
    for time in np.unique(times[events == 1]):
        deaths = (times == time) & (events == 1)
        at_risk = times >= time
        d = int(deaths.sum())
        death_eta = float(eta[deaths].sum())
        death_score = float(risk_score[deaths].sum())
        death_x = (risk_score[deaths, None] * X[deaths]).sum(axis=0)
        risk0 = float(risk_score[at_risk].sum())
        risk1 = (risk_score[at_risk, None] * X[at_risk]).sum(axis=0)
        log_likelihood += death_eta
        gradient += X[deaths].sum(axis=0)
        for tie_index in range(d):
            fraction = tie_index / d
            denominator = risk0 - fraction * death_score
            numerator = risk1 - fraction * death_x
            if denominator <= 0 or not math.isfinite(denominator):
                raise TrainingError("Cox risk set became numerically invalid.")
            log_likelihood -= math.log(denominator)
            gradient -= numerator / denominator
    event_count = max(1, int(events.sum()))
    loss = -log_likelihood / event_count + 0.5 * alpha * float(beta @ beta)
    grad = -gradient / event_count + alpha * beta
    return loss, grad


def fit_cox(X: np.ndarray, times: np.ndarray, events: np.ndarray,
            alpha: float = RIDGE_ALPHA) -> dict:
    Z, means, scales = _standardize_fit(X)
    result = minimize(lambda b: _efron_loss_grad(b, Z, times, events, alpha),
                      np.zeros(Z.shape[1]), jac=True, method="L-BFGS-B",
                      options={"maxiter": 1000, "ftol": 1e-12, "gtol": 1e-8})
    if not result.success or not np.isfinite(result.x).all():
        raise TrainingError("Regularized Cox fit did not converge.")
    beta = result.x
    eta = np.clip(Z @ beta, -30, 30)
    risk = np.exp(eta)
    baseline_times, cumulative_hazard = [], []
    running_hazard = 0.0
    for time in np.unique(times[events == 1]):
        at_risk = times >= time
        deaths = (times == time) & (events == 1)
        running_hazard += float(deaths.sum()) / float(risk[at_risk].sum())
        baseline_times.append(float(time))
        cumulative_hazard.append(running_hazard)
    if not baseline_times:
        raise TrainingError("Cox fit has no observed event times.")
    return {"means": means, "scales": scales, "beta": beta,
            "times": np.asarray(baseline_times), "cumulative_hazard": np.asarray(cumulative_hazard),
            "survival": np.exp(-np.asarray(cumulative_hazard)), "optimizer_iterations": int(result.nit)}


def linear_risk(model: dict, X: np.ndarray) -> np.ndarray:
    Z = (X - model["means"]) / model["scales"]
    return np.exp(np.clip(Z @ model["beta"], -30, 30))


def survival_at(model: dict, X: np.ndarray, horizon: float) -> np.ndarray:
    index = np.searchsorted(model["times"], horizon, side="right") - 1
    h0 = float(model["cumulative_hazard"][index]) if index >= 0 else 0.0
    return np.exp(-h0 * linear_risk(model, X))


def harrell_c_index(times: np.ndarray, events: np.ndarray, risk: np.ndarray) -> float:
    concordant = comparable = 0.0
    for i in range(len(times)):
        if events[i] != 1:
            continue
        later = times > times[i]
        for j in np.flatnonzero(later):
            comparable += 1
            if risk[i] > risk[j]:
                concordant += 1
            elif risk[i] == risk[j]:
                concordant += 0.5
    return concordant / comparable if comparable else float("nan")


def censor_survival(train_times: np.ndarray, train_events: np.ndarray, query_time: float,
                    left_limit: bool = False) -> float:
    """KM estimate for censoring distribution; death is censoring for G(t)."""
    survival = 1.0
    for time in np.unique(train_times):
        if time > query_time or (left_limit and time >= query_time):
            break
        at_risk = int((train_times >= time).sum())
        censored = int(((train_times == time) & (train_events == 0)).sum())
        if at_risk:
            survival *= 1.0 - censored / at_risk
    return survival


def ipcw_brier(train_times: np.ndarray, train_events: np.ndarray, test_times: np.ndarray,
               test_events: np.ndarray, predicted_survival: np.ndarray, horizon: float) -> float:
    terms, weights = [], []
    g_h = censor_survival(train_times, train_events, horizon)
    for duration, event, prediction in zip(test_times, test_events, predicted_survival):
        if duration <= horizon and event == 1:
            g = censor_survival(train_times, train_events, float(duration), left_limit=True)
            if g > 1e-8:
                terms.append(float(prediction) ** 2); weights.append(1.0 / g)
        elif duration > horizon:
            if g_h > 1e-8:
                terms.append((1.0 - float(prediction)) ** 2); weights.append(1.0 / g_h)
        # A censoring time before the horizon carries no known status at t.
    return float(np.average(terms, weights=weights)) if weights else float("nan")


def cross_validate(X: np.ndarray, times: np.ndarray, events: np.ndarray) -> dict:
    splitter = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_SEED)
    oof_risk = np.full(len(times), np.nan)
    horizons = [365.0, 730.0, 1095.0]
    oof_survival = {h: np.full(len(times), np.nan) for h in horizons}
    fold_c, fold_brier = [], {h: [] for h in horizons}
    for train_idx, test_idx in splitter.split(X, events):
        model = fit_cox(X[train_idx], times[train_idx], events[train_idx])
        risk = linear_risk(model, X[test_idx])
        oof_risk[test_idx] = risk
        fold_c.append(harrell_c_index(times[test_idx], events[test_idx], risk))
        for horizon in horizons:
            if horizon <= model["times"][-1]:
                prediction = survival_at(model, X[test_idx], horizon)
                oof_survival[horizon][test_idx] = prediction
                score = ipcw_brier(times[train_idx], events[train_idx], times[test_idx],
                                   events[test_idx], prediction, horizon)
                if math.isfinite(score):
                    fold_brier[horizon].append(score)
    pooled_c = harrell_c_index(times, events, oof_risk)
    brier = {}
    for horizon in horizons:
        predictions = oof_survival[horizon]
        valid = np.isfinite(predictions)
        if valid.any():
            # Fold-specific censoring estimates are used in each fold below;
            # report the mean fold IPCW estimate, never a test-fitted estimate.
            brier[str(int(horizon))] = {
                "mean_fold_ipcw_brier": float(np.mean(fold_brier[horizon])) if fold_brier[horizon] else None,
                "fold_scores": [float(v) for v in fold_brier[horizon]],
                "scored_folds": len(fold_brier[horizon]),
            }
        else:
            brier[str(int(horizon))] = {"mean_fold_ipcw_brier": None, "fold_scores": [], "scored_folds": 0}
    return {"protocol": "5-fold stratified patient-level CV; all UCSF rows are reduced to baseline patient records before splitting.",
            "random_seed": RANDOM_SEED, "folds": CV_FOLDS, "ridge_alpha_fixed": RIDGE_ALPHA,
            "mean_fold_harrell_c_index": float(np.mean(fold_c)),
            "fold_harrell_c_index": [float(v) for v in fold_c],
            "pooled_oof_harrell_c_index": float(pooled_c),
            "ipcw_brier_at_days": brier,
            "validation_scope": "Internal cross-validation only; no external validation; no tuning on held-out folds."}


def build_artifact(csv_path: Path) -> tuple[dict, dict]:
    X, times, events, cohort = load_gbm_cohort(csv_path)
    validation = cross_validate(X, times, events)
    fitted = fit_cox(X, times, events)
    model = {
        "artifact_schema_version": 1,
        "model_id": MODEL_ID,
        "model_version": MODEL_VERSION,
        "model_type": "CoxPH",
        "research_only": True,
        "dataset": {"id": DATASET_ID, "version": DATASET_VERSION,
                    "official_source": "https://www.cancerimagingarchive.net/collection/ucsf-pdgm/",
                    "clinical_csv": "UCSF-PDGM-metadata_v5.csv",
                    "clinical_csv_sha256": sha256_file(csv_path),
                    "license": "CC BY 4.0",
                    "cohort": "WHO-2021 final diagnosis Glioblastoma, IDH-wildtype"},
        "endpoint": {"status": ENDPOINT_STATUS, "official_endpoint_validated": True,
                     "time_unit": "days", "origin": "initial diagnosis",
                     "event_definition": "1-dead 0-alive == 1 at last clinical follow-up",
                     "censor_definition": "1-dead 0-alive == 0; right-censored at official OS follow-up time",
                     "source_definition": "TCIA UCSF-PDGM v5 metadata glossary: OS is days from initial diagnosis to last clinical follow-up; vital status is at last clinical follow-up."},
        "features": {"names": FEATURE_NAMES,
                     "means": fitted["means"].tolist(), "scales": fitted["scales"].tolist(),
                     "coefficients_standardized": fitted["beta"].tolist(),
                     "training_ranges": {"age_years": [float(X[:, 0].min()), float(X[:, 0].max())]},
                     "input_schema": {"inputs": ["age_years", "sex"],
                                      "sex_categories": ["F", "M"],
                                      "encoding": {"sex_M": "1 for M, 0 for F"}},
                     "preprocessing": "Age and binary sex standardized using training-fold means and population SD; no imputation required in eligible GBM cohort."},
        "training": {"n": cohort["training_n"], "events": cohort["events"], "censored": cohort["censored"],
                     "cohort_definition": cohort["cohort_definition"],
                     "feature_timepoint": cohort["feature_timepoint"],
                     "ridge_alpha": RIDGE_ALPHA, "optimizer": "SciPy L-BFGS-B, Efron tied-event partial likelihood",
                     "optimizer_iterations_final_fit": fitted["optimizer_iterations"]},
        "validation": validation,
        "baseline": {"times_days": fitted["times"].tolist(),
                     "cumulative_hazard": fitted["cumulative_hazard"].tolist(),
                     "survival": fitted["survival"].tolist(),
                     "estimator": "Breslow baseline cumulative hazard from full eligible baseline cohort"},
        "limitations": [
            "Research-only model trained on one public, single-center UCSF-PDGM cohort; not a clinical decision tool.",
            "Official endpoint semantics follow the TCIA v5 glossary; the OS field records time from initial diagnosis to last clinical follow-up and vital status at last follow-up.",
            "Prediction covariates are age at preoperative MRI and sex only. The exact MRI-to-diagnosis interval is not encoded.",
            "Cohort is restricted to final WHO-2021 Glioblastoma, IDH-wildtype; this is not performance for all diffuse gliomas.",
            "Cross-validation is internal, patient-level and not independent external validation; no patient-level predictions are persisted.",
            "No treatment, resection, MGMT or imaging features are included; this is a sparse clinical baseline.",
        ],
    }
    summary = {"dataset_id": DATASET_ID, "dataset_version": DATASET_VERSION,
               "clinical_csv_sha256": model["dataset"]["clinical_csv_sha256"],
               "cohort": cohort, "validation": validation,
               "model_id": MODEL_ID, "model_version": MODEL_VERSION,
               "endpoint_status": ENDPOINT_STATUS,
               "training_time_utc": datetime.now(timezone.utc).isoformat(),
               "patient_level_outputs_saved": False}
    return model, summary


def write_model(model: dict, summary: dict, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / "cox-model.json"
    manifest_path = output_dir / "model-manifest.json"
    summary_path = output_dir / "training-summary.json"
    artifact_bytes = (json.dumps(model, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    artifact_tmp = artifact_path.with_suffix(".json.tmp")
    artifact_tmp.write_bytes(artifact_bytes)
    os.replace(artifact_tmp, artifact_path)
    artifact_hash = sha256_file(artifact_path)
    manifest = {"artifact_schema_version": 1, "model_id": MODEL_ID,
                "model_version": MODEL_VERSION, "model_type": "CoxPH",
                "research_only": True, "artifact_file": artifact_path.name,
                "artifact_sha256": artifact_hash,
                "dataset_id": DATASET_ID, "dataset_version": DATASET_VERSION,
                "clinical_csv_sha256": model["dataset"]["clinical_csv_sha256"]}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"artifact_sha256": artifact_hash,
            "manifest_sha256": sha256_file(manifest_path),
            "summary_sha256": sha256_file(summary_path)}


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clinical-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    if not args.clinical_csv.is_file():
        parser.error("Official UCSF-PDGM clinical CSV does not exist.")
    model, summary = build_artifact(args.clinical_csv)
    hashes = write_model(model, summary, args.output_dir)
    print(json.dumps({"status": "trained", "model_id": MODEL_ID, "model_version": MODEL_VERSION,
                      "training": model["training"], "validation": model["validation"], **hashes},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except TrainingError as error:
        print(f"TRAINING_BLOCKED: {error}", file=sys.stderr)
        raise SystemExit(2)
