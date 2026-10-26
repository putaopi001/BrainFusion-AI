"""Fit one versioned, RESEARCH_ONLY UPENN clinical Cox artifact.

The endpoint rule intentionally reuses the previously audited S1 researcher
definition. It does not validate the official endpoint and does not persist
patient-level rows or predictions. Outputs are restricted to the research
runtime and an existing output directory is never overwritten.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedKFold

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.research.survival import (  # noqa: E402
    EndpointContract, concordance_index, cox_ph, validate_endpoint,
)

EXPECTED_CSV_SHA256 = "fd5749ae5a8d77e599e02264d961d94107752f0244e34bf0bc711a75fe0e2ec5"
SEED = 20261026
L2 = 0.1
FEATURE_NAMES = ["age_years", "gender_M", "IDH1_mutated", "IDH1_NOS_NEC",
                 "GTR_over90pct_Y", "GTR_unknown"]
ENDPOINT_RULE = (
    "Researcher-defined S1 from official UPENN clinical v1.2: baseline _11 only; "
    "Deceased with positive Survival_from_surgery_days_UPDATED is event; Alive or "
    "Lost to Follow-up with positive Survival_Censor is censored; three uncertain-date "
    "deaths excluded. Censor time is assumed days in first-surgery context; official "
    "Survival_Censor unit/origin/last-contact derivation remains undocumented."
)
LIMITATIONS = [
    "RESEARCH_ONLY: the official OS endpoint is not validated; the censor-field meaning, unit, origin and derivation are unresolved.",
    "The event/censor rule is a researcher-defined assumption, not an official field dictionary.",
    "Internal five-fold patient-level cross-validation only; no independent external validation or clinical utility assessment.",
    "The final all-cohort fit is a deployable software artifact for controlled research testing, not a clinically validated model.",
    "Survival probabilities are mathematical outputs from the researcher-defined endpoint and are not suitable for patient care.",
    "No patient-level prediction requests or scores are stored; the API accepts only explicit SYNTHETIC_TEST scope.",
]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_number(value):
    try:
        number = float(str(value).strip())
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def load_cohort(path: Path) -> tuple[list[dict], dict]:
    if file_sha256(path) != EXPECTED_CSV_SHA256:
        raise ValueError("Clinical CSV SHA-256 does not match the audited official v1.2 input.")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        headers = reader.fieldnames or []
    required = {"ID", "Gender", "Age_at_scan_years", "Survival_from_surgery_days_UPDATED",
                "Survival_Status", "Survival_Censor", "IDH1", "GTR_over90percent"}
    if len(rows) != 671 or not required.issubset(headers):
        raise ValueError("Official v1.2 input does not match the audited 671-row clinical contract.")
    ids = [str(row.get("ID", "")).strip() for row in rows]
    if len(set(ids)) != len(ids) or any(not key.endswith(("_11", "_21")) for key in ids):
        raise ValueError("Duplicate or unsupported scan IDs in the official clinical CSV.")

    baseline = [row for row in rows if row["ID"].strip().endswith("_11")]
    if len(baseline) != 611:
        raise ValueError("Baseline _11 scan count differs from the audited cohort contract.")
    candidates, excluded = [], {}
    for row in baseline:
        status = row["Survival_Status"].strip()
        event_time = parse_number(row.get("Survival_from_surgery_days_UPDATED"))
        censor_time = parse_number(row.get("Survival_Censor"))
        if status == "Deceased" and event_time is not None and event_time > 0:
            duration, event = event_time, 1
        elif status in {"Alive", "Lost to Follow-up"} and censor_time is not None and censor_time > 0:
            duration, event = censor_time, 0
        else:
            excluded[status] = excluded.get(status, 0) + 1
            continue
        candidates.append({**row, "duration": float(duration), "event": int(event),
                           "patient_id": row["ID"].strip()[:-3]})
    if (len(candidates) != 608 or sum(row["event"] for row in candidates) != 585
            or len(candidates) - sum(row["event"] for row in candidates) != 23
            or len({row["patient_id"] for row in candidates}) != 608
            or excluded.get("Deceased - uncertain date of death") != 3):
        raise ValueError("Researcher-defined S1 counts differ from the previously audited 608/585/23 cohort.")
    return candidates, {"baseline_n": len(baseline), "candidate_n": len(candidates),
                        "events": 585, "censored": 23, "excluded": excluded}


def encode(row: dict) -> list[float]:
    age = parse_number(row.get("Age_at_scan_years"))
    if age is None or not 0 < age <= 120:
        raise ValueError("A candidate row has an invalid age; refusing to fit.")
    gender = str(row.get("Gender", "")).strip()
    if gender not in {"F", "M"}:
        raise ValueError("A candidate row has an unsupported gender category.")
    idh = str(row.get("IDH1", "")).strip()
    if idh not in {"Wildtype", "Mutated", "NOS/NEC"}:
        raise ValueError("A candidate row has an IDH1 category outside the audited model contract.")
    gtr = str(row.get("GTR_over90percent", "")).strip()
    if gtr not in {"Y", "N"}:
        gtr = "UNKNOWN"
    return [
        float(age), float(gender == "M"), float(idh == "Mutated"),
        float(idh == "NOS/NEC"),
        float(gtr == "Y"), float(gtr == "UNKNOWN"),
    ]


def contract(rows: list[dict]) -> dict:
    prepared = [{"patient_id": row["patient_id"], "duration": row["duration"],
                 "event": str(row["event"]), "origin": ENDPOINT_RULE} for row in rows]
    endpoint = EndpointContract("OS", "patient_id", "duration", "event", "origin",
                                ENDPOINT_RULE, "days", "1", "0", True)
    audit = validate_endpoint(prepared, endpoint)
    if not audit["eligible"]:
        raise ValueError("Research endpoint contract failed: " + ", ".join(audit["issues"]))
    return audit


def fit_fold(train_rows: list[dict], train_x: np.ndarray, test_x: np.ndarray,
             test_rows: list[dict]) -> tuple[float, dict]:
    audit = contract(train_rows)
    scales_all = np.std(train_x, axis=0)
    keep = np.flatnonzero(scales_all > np.finfo(float).eps)
    if not len(keep):
        raise ValueError("All training-fold clinical features are constant.")
    kept_names = [FEATURE_NAMES[int(index)] for index in keep]
    train_fit = train_x[:, keep]
    test_fit = test_x[:, keep]
    fit = cox_ph(audit, train_fit, kept_names, l2=L2)
    if not fit.get("converged"):
        raise ValueError("Cox optimizer did not converge: " + fit.get("optimizer_message", "unknown"))
    mean = np.mean(train_fit, axis=0)
    scale = np.std(train_fit, axis=0)
    if not np.isfinite(scale).all() or np.any(scale <= np.finfo(float).eps):
        raise ValueError("Training-fold feature scale is degenerate.")
    beta_std = np.asarray([fit["coefficients"][name] for name in kept_names]) * scale
    risk = ((test_fit - mean) / scale) @ beta_std
    times = np.asarray([row["duration"] for row in test_rows], dtype=float)
    events = np.asarray([row["event"] for row in test_rows], dtype=int)
    return concordance_index(times, events, risk), {**fit,
        "fold_feature_names": kept_names,
        "dropped_constant_features": [name for index, name in enumerate(FEATURE_NAMES) if index not in keep]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clinical", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    allowed_root = Path("E:/BrainFusion-Runtime/research-edition").resolve()
    if not output.is_relative_to(allowed_root):
        raise ValueError("Model artifacts may only be written under the controlled research runtime.")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite existing research model artifacts: {output}")
    output.mkdir(parents=True, exist_ok=True)

    rows, cohort = load_cohort(args.clinical.resolve())
    x = np.asarray([encode(row) for row in rows], dtype=float)
    y = np.asarray([row["event"] for row in rows], dtype=int)
    durations = np.asarray([row["duration"] for row in rows], dtype=float)
    patients = [row["patient_id"] for row in rows]
    if len(set(patients)) != len(patients):
        raise ValueError("Repeated patient rows detected; one baseline row per patient is required.")

    folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    cv_results = []
    for fold_number, (train_idx, test_idx) in enumerate(folds.split(x, y), start=1):
        train_rows = [rows[int(i)] for i in train_idx]
        test_rows = [rows[int(i)] for i in test_idx]
        score, fit = fit_fold(train_rows, x[train_idx], x[test_idx], test_rows)
        cv_results.append({"fold": fold_number, "train_n": len(train_idx), "test_n": len(test_idx),
                           "test_events": int(y[test_idx].sum()), "test_c_index": score,
                           "cox_converged": fit["converged"],
                           "fold_feature_names": fit["fold_feature_names"],
                           "dropped_constant_features": fit["dropped_constant_features"]})
    fold_scores = np.asarray([row["test_c_index"] for row in cv_results], dtype=float)

    full_contract = contract(rows)
    full_scales = np.std(x, axis=0)
    full_keep = np.flatnonzero(full_scales > np.finfo(float).eps)
    if len(full_keep) != len(FEATURE_NAMES):
        raise ValueError("At least one prespecified clinical feature is globally constant in the final cohort.")
    final_fit = cox_ph(full_contract, x, FEATURE_NAMES, l2=L2)
    if not final_fit.get("converged"):
        raise ValueError("Final full-cohort Cox optimizer did not converge.")
    means, scales = np.mean(x, axis=0), np.std(x, axis=0)
    if not np.isfinite(scales).all() or np.any(scales <= np.finfo(float).eps):
        raise ValueError("Final feature scaling is invalid.")
    beta_std = np.asarray([final_fit["coefficients"][name] for name in FEATURE_NAMES]) * scales
    linear_predictor = ((x - means) / scales) @ beta_std
    if not np.isfinite(linear_predictor).all() or np.max(np.abs(linear_predictor)) > 50:
        raise ValueError("Final Cox linear predictors are not numerically supported.")

    event_times = np.unique(durations[y == 1])
    increments = []
    for time in event_times:
        event_count = int(np.sum((durations == time) & (y == 1)))
        risk_sum = float(np.exp(linear_predictor[durations >= time]).sum())
        if event_count <= 0 or not math.isfinite(risk_sum) or risk_sum <= 0:
            raise ValueError("Breslow baseline hazard calculation failed.")
        increments.append(event_count / risk_sum)
    cumulative_hazard = np.cumsum(np.asarray(increments, dtype=float))
    baseline_survival = np.exp(-cumulative_hazard)
    if (not np.isfinite(cumulative_hazard).all() or not np.isfinite(baseline_survival).all()
            or np.any(np.diff(baseline_survival) > 1e-12)
            or np.any((baseline_survival < 0) | (baseline_survival > 1))):
        raise ValueError("Estimated baseline survival is invalid or non-monotone.")

    # Aggregate category counts only. No IDs, raw rows, or predictions enter the artifact.
    category_counts = {
        "gender": {key: sum(str(row.get("Gender", "")).strip() == key for row in rows) for key in ("F", "M")},
        "IDH1": {key: sum((str(row.get("IDH1", "")).strip() if str(row.get("IDH1", "")).strip() in {"Wildtype", "Mutated", "NOS/NEC"} else "UNKNOWN") == key for row in rows) for key in ("Wildtype", "Mutated", "NOS/NEC", "UNKNOWN")},
        "GTR_over90percent": {key: sum((str(row.get("GTR_over90percent", "")).strip() if str(row.get("GTR_over90percent", "")).strip() in {"Y", "N"} else "UNKNOWN") == key for row in rows) for key in ("N", "Y", "UNKNOWN")},
    }
    age_values = [parse_number(row.get("Age_at_scan_years")) for row in rows]
    model = {
        "artifact_schema_version": 1,
        "model_id": "upenn-clinical-cox-research",
        "model_version": "1.0.1-research-only",
        "model_type": "CoxPH",
        "research_only": True,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "endpoint": {
            "name": "OS", "status": "RESEARCHER_DEFINED_ENDPOINT_WITH_LIMITATIONS",
            "official_endpoint_validated": False, "time_unit": "days",
            "time_origin": "assumed first surgery context; censor origin is not officially documented",
            "rule": ENDPOINT_RULE,
        },
        "features": {
            "names": FEATURE_NAMES,
            "means": means.tolist(), "scales": scales.tolist(),
            "coefficients_standardized": beta_std.tolist(),
            "encoding": {
                "inputs": ["age_years", "gender", "IDH1", "GTR_over90percent"],
                "age_unit": "years",
                "gender_reference": "F; gender_M=1 for M",
                "IDH1_reference": "Wildtype; explicit Mutated and NOS/NEC indicators; UNKNOWN unsupported because absent from training cohort",
                "GTR_reference": "N; explicit Y and UNKNOWN indicator columns",
                "unknown_handling": "GTR unknown represented explicitly; IDH1 unknown rejected because no such training cases; no outcome-informed encoding or imputation",
            },
            "training_ranges": {"age_years": [float(min(age_values)), float(max(age_values))]},
            "training_category_counts": category_counts,
        },
        "baseline": {"method": "Breslow cumulative baseline hazard at standardized x=0",
                     "times_days": event_times.tolist(),
                     "cumulative_hazard": cumulative_hazard.tolist(),
                     "survival": baseline_survival.tolist()},
        "training": {
            "n": len(rows), "events": int(y.sum()), "censored": int((y == 0).sum()),
            "baseline_records": cohort["baseline_n"], "uncertain_deaths_excluded": cohort["excluded"],
            "patient_unit": "normalized patient; one baseline _11 row per patient",
            "covariate_missingness": "age/gender complete in candidate rows; unknown IDH/resection encoded explicitly",
            "endpoint_candidate_rule": "S1 from audited source; see endpoint.rule",
            "input_sha256": file_sha256(args.clinical.resolve()),
            "script_sha256": file_sha256(Path(__file__).resolve()),
            "source_commit": "a1c1fe33497c6f93512b00804f8fe4cee714fd0b",
            "seed": SEED, "l2_penalty": L2, "tie_method": "Breslow",
        },
        "validation": {
            "status": "INTERNAL_PATIENT_LEVEL_CROSS_VALIDATION_ONLY",
            "method": "StratifiedKFold, 5 folds; one baseline row per patient",
            "seed": SEED, "folds": cv_results,
            "mean_fold_harrell_c_index": float(np.mean(fold_scores)),
            "sd_fold_harrell_c_index": float(np.std(fold_scores, ddof=1)),
            "external_validation": False, "clinical_validation": False,
            "training_fitted_preprocessing": "fixed category coding; numeric feature scaling fitted within each training fold; final model parameters fitted on all candidate rows",
            "one_year_classification": "NOT_RUN",
        },
        "optimizer": {"converged": bool(final_fit["converged"]), "message": final_fit["optimizer_message"]},
        "diagnostics": {
            "scope": "full_cohort exploratory trend screen only; not a formal proportional-hazards test",
            "proportional_hazards_screening": final_fit["proportional_hazards_screening"],
        },
        "limitations": LIMITATIONS,
    }
    artifact_path = output / "cox-model.json"
    manifest_path = output / "model-manifest.json"
    if artifact_path.exists() or manifest_path.exists():
        raise FileExistsError("Refusing to overwrite an existing model artifact.")
    artifact_path.write_text(json.dumps(model, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    manifest = {
        "artifact_schema_version": 1, "model_id": model["model_id"],
        "model_version": model["model_version"], "model_type": model["model_type"],
        "research_only": True, "artifact_file": artifact_path.name,
        "artifact_sha256": file_sha256(artifact_path),
        "source_commit": model["training"]["source_commit"],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"model_id": model["model_id"], "model_version": model["model_version"],
                      "n": len(rows), "events": int(y.sum()), "censored": int((y == 0).sum()),
                      "mean_fold_c_index": model["validation"]["mean_fold_harrell_c_index"],
                      "sd_fold_c_index": model["validation"]["sd_fold_harrell_c_index"],
                      "final_converged": model["optimizer"]["converged"],
                      "artifact_sha256": manifest["artifact_sha256"],
                      "artifact_dir": str(output)}, indent=2))


if __name__ == "__main__":
    main()
