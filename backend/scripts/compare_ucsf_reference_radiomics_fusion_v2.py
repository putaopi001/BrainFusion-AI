"""Paired patient-level CV of clinical, radiomics, and fused UCSF Cox models.

The 20 radiomics columns are a fixed, externally defined BrainFusion panel;
no outcome-based feature selection or hyperparameter search is done here.
Patient-level input and OOF rows remain in the protected data directory.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import StratifiedKFold
import sklearn

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from scripts import compare_ucsf_pdgm_survival_v2 as survival
from scripts import train_ucsf_pdgm_cox as base

SEED = 20261027
FOLDS = 5
ALPHA = 0.01
L1_RATIO = 0.5
HORIZONS = (365.0, 730.0, 1095.0)
BOOTSTRAPS = 1000
EXPECTED_CLINICAL_SHA256 = "afc1c23a0eb0597b56e603741e72f2308b4860281187cd3808e05b7a0116fd78"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def ipcw_brier(train_t, train_e, test_t, test_e, prediction, horizon):
    """Standard IPCW Brier estimate: weighted squared error divided by test N."""
    losses, weights = [], []
    g_h = base.censor_survival(train_t, train_e, horizon)
    for duration, event, estimate in zip(test_t, test_e, prediction):
        if duration <= horizon and event == 1:
            g = base.censor_survival(train_t, train_e, float(duration), left_limit=True)
            if g > 1e-8:
                losses.append(float(estimate) ** 2); weights.append(1.0 / g)
            else:
                losses.append(0.0); weights.append(0.0)
        elif duration > horizon and g_h > 1e-8:
            losses.append((1.0 - float(estimate)) ** 2); weights.append(1.0 / g_h)
        else:
            # Censored before the horizon: status at horizon is unobserved.
            losses.append(0.0); weights.append(0.0)
    return float(np.sum(np.asarray(losses) * np.asarray(weights)) / len(test_t)), int(np.count_nonzero(weights))


def ipcw_calibration_pair(train_t, train_e, test_t, test_e, predicted, horizon):
    weighted_predicted, observed, weights = [], [], []
    g_h = base.censor_survival(train_t, train_e, horizon)
    for duration, event, estimate in zip(test_t, test_e, predicted):
        if duration <= horizon and event == 1:
            g = base.censor_survival(train_t, train_e, float(duration), left_limit=True)
            if g > 1e-8:
                weighted_predicted.append(float(estimate)); observed.append(0.0); weights.append(1.0 / g)
        elif duration > horizon and g_h > 1e-8:
            weighted_predicted.append(float(estimate)); observed.append(1.0); weights.append(1.0 / g_h)
    if not weights:
        return None, None, 0
    return (float(np.average(weighted_predicted, weights=weights)),
            float(np.average(observed, weights=weights)), len(weights))


def cv_candidate(clinical: np.ndarray, radiomics: np.ndarray, times: np.ndarray,
                 events: np.ndarray, model_name: str) -> dict:
    n = len(times)
    predictions = np.full((n, len(HORIZONS)), np.nan)
    risks = np.full(n, np.nan)
    folds = np.full(n, -1, dtype=int)
    fold_results = []
    fold_ibs = []
    splitter = StratifiedKFold(n_splits=FOLDS, shuffle=True, random_state=SEED)
    for fold, (tr, te) in enumerate(splitter.split(np.zeros(n), events), start=1):
        # One-row-per-patient dataset. The assertion prevents accidental duplicate IDs
        # from entering the evaluator in future revisions.
        if len(set(tr.tolist())) != len(tr) or set(tr) & set(te):
            raise ValueError("Patient split is not mutually exclusive")
        if model_name == "clinical_age_sex_ridge":
            xtr, xte = clinical[tr], clinical[te]
            fitted = base.fit_cox(xtr, times[tr], events[tr], alpha=ALPHA)
        elif model_name in {"radiomics_ridge", "radiomics_elastic_net"}:
            xtr, xte = impute_fold(radiomics[tr], radiomics[te])
            if model_name == "radiomics_ridge":
                fitted = base.fit_cox(xtr, times[tr], events[tr], alpha=ALPHA)
            else:
                fitted = survival.fit_elastic_net_cox(xtr, times[tr], events[tr], alpha=ALPHA, l1_ratio=L1_RATIO)
        elif model_name == "clinical_radiomics_ridge":
            rtr, rte = impute_fold(radiomics[tr], radiomics[te])
            xtr, xte = np.column_stack((clinical[tr], rtr)), np.column_stack((clinical[te], rte))
            fitted = base.fit_cox(xtr, times[tr], events[tr], alpha=ALPHA)
        elif model_name == "clinical_radiomics_elastic_net":
            rtr, rte = impute_fold(radiomics[tr], radiomics[te])
            xtr, xte = np.column_stack((clinical[tr], rtr)), np.column_stack((clinical[te], rte))
            fitted = survival.fit_elastic_net_cox(xtr, times[tr], events[tr], alpha=ALPHA, l1_ratio=L1_RATIO)
        else:
            raise ValueError(f"Unknown candidate: {model_name}")
        risk = base.linear_risk(fitted, xte)
        pred = np.column_stack([base.survival_at(fitted, xte, h) for h in HORIZONS])
        if not np.isfinite(risk).all() or not np.isfinite(pred).all() or np.any((pred < 0) | (pred > 1)):
            raise ValueError(f"Nonfinite/out-of-range model output in fold {fold}")
        if np.any(pred[:, 1:] > pred[:, :-1] + 1e-12):
            raise ValueError(f"Survival probability increased with time in fold {fold}")
        risks[te], predictions[te], folds[te] = risk, pred, fold
        fold_brier = {}
        fold_calibration = {}
        for j, horizon in enumerate(HORIZONS):
            score, n_scored = ipcw_brier(times[tr], events[tr], times[te], events[te], pred[:, j], horizon)
            fold_brier[str(int(horizon))] = score if n_scored else None
            p_mean, obs, scored = ipcw_calibration_pair(times[tr], events[tr], times[te], events[te], pred[:, j], horizon)
            fold_calibration[str(int(horizon))] = {"mean_predicted_survival": p_mean,
                                                   "ipcw_observed_survival": obs,
                                                   "calibration_gap": p_mean - obs if obs is not None and p_mean is not None else None,
                                                   "n_scored": scored}
        ibs_points = []
        for horizon in np.arange(180.0, 1096.0, 90.0):
            if horizon >= np.max(times[tr][events[tr] == 1]):
                continue
            at_h = np.column_stack([base.survival_at(fitted, xte, float(horizon))])[:, 0]
            score, n_scored = ipcw_brier(times[tr], events[tr], times[te], events[te], at_h, float(horizon))
            if n_scored:
                ibs_points.append((float(horizon), score))
        fold_ibs.append(float(np.trapezoid([v for _, v in ibs_points], [t for t, _ in ibs_points]) /
                              (ibs_points[-1][0] - ibs_points[0][0])) if len(ibs_points) >= 2 else None)
        fold_c = base.harrell_c_index(times[te], events[te], risk)
        fold_results.append({"fold": fold, "n_train": len(tr), "n_test": len(te),
                             "events_train": int(events[tr].sum()), "events_test": int(events[te].sum()),
                             "c_index": fold_c if math.isfinite(fold_c) else None,
                             "ipcw_brier": fold_brier, "calibration": fold_calibration,
                             "ibs_180_1095_days": fold_ibs[-1]})
    if np.any(folds < 1) or not np.isfinite(risks).all() or not np.isfinite(predictions).all():
        raise ValueError("Every patient must receive exactly one finite OOF prediction")
    c_index = survival.fast_harrell_c_index(times, events, risks)
    brier_summary = {}
    for h in HORIZONS:
        fold_scores = [x["ipcw_brier"][str(int(h))] for x in fold_results if x["ipcw_brier"][str(int(h))] is not None]
        brier_summary[str(int(h))] = {"mean_fold_ipcw_brier": float(np.mean(fold_scores)) if fold_scores else None,
                                     "sd_fold_ipcw_brier": float(np.std(fold_scores, ddof=1)) if len(fold_scores) > 1 else None,
                                     "fold_scores": [x["ipcw_brier"][str(int(h))] for x in fold_results],
                                     "calibration": [x["calibration"][str(int(h))] for x in fold_results]}
    return {"name": model_name, "folds": fold_results, "pooled_oof_c_index": float(c_index),
            "mean_fold_c_index": float(np.mean([x["c_index"] for x in fold_results if x["c_index"] is not None])),
            "sd_fold_c_index": float(np.std([x["c_index"] for x in fold_results if x["c_index"] is not None], ddof=1)),
            "mean_fold_ibs_180_1095_days": float(np.mean([x for x in fold_ibs if x is not None])) if any(x is not None for x in fold_ibs) else None,
            "fold_ibs": fold_ibs, "ipcw_brier": brier_summary, "_oof_risk": risks, "_oof_survival": predictions, "_oof_fold": folds}


def impute_fold(train: np.ndarray, test: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    medians = np.nanmedian(train, axis=0)
    if not np.isfinite(medians).all():
        raise ValueError("A retained feature has no finite value in a training fold")
    train_out, test_out = train.copy(), test.copy()
    train_missing, test_missing = ~np.isfinite(train_out), ~np.isfinite(test_out)
    train_out[train_missing] = np.take(medians, np.where(train_missing)[1])
    test_out[test_missing] = np.take(medians, np.where(test_missing)[1])
    return train_out, test_out


def paired_bootstrap_delta(times, events, candidate, baseline, seed=SEED + 1):
    rng = np.random.default_rng(seed)
    n = len(times)
    diffs = []
    for _ in range(BOOTSTRAPS):
        ix = rng.integers(0, n, n)
        a = survival.fast_harrell_c_index(times[ix], events[ix], candidate[ix])
        b = survival.fast_harrell_c_index(times[ix], events[ix], baseline[ix])
        if math.isfinite(a) and math.isfinite(b):
            diffs.append(a - b)
    return {"mean_delta_c_index": float(np.mean(diffs)), "percentile_95_ci": [float(x) for x in np.quantile(diffs, [0.025, .975])],
            "bootstrap_replicates": len(diffs), "seed": seed}


def bootstrap_c_index_ci(times, events, risk, seed):
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(BOOTSTRAPS):
        ix = rng.integers(0, len(times), len(times))
        score = survival.fast_harrell_c_index(times[ix], events[ix], risk[ix])
        if math.isfinite(score):
            values.append(score)
    return [float(x) for x in np.quantile(values, [0.025, 0.975])] if values else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--features", type=Path, required=True)
    ap.add_argument("--cohort-csv", type=Path, default=Path("E:/BrainFusion-Data/UCSF-PDGM/clinical/UCSF-PDGM-metadata_v5.csv"))
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    feature_csv = args.features.resolve(strict=True)
    cohort_csv = args.cohort_csv.resolve(strict=True)
    out = args.output.resolve()
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite existing analysis: {out}")
    if sha256(cohort_csv) != EXPECTED_CLINICAL_SHA256:
        raise ValueError("Official UCSF v5 clinical CSV SHA-256 does not match the reviewed fixed source")
    rows = list(csv.DictReader(feature_csv.open("r", encoding="utf-8-sig", newline="")))
    if not rows:
        raise ValueError("Feature table is empty")
    patient_ids = [r["patient_id"] for r in rows]
    if len(patient_ids) != len(set(patient_ids)):
        raise ValueError("Duplicate patient in matched radiomics table")
    clinical_ids = [r.get("clinical_id", "") for r in rows]
    if (any(not value or "_FU" in value for value in clinical_ids)
            or len(clinical_ids) != len(set(clinical_ids))):
        raise ValueError("Clinical crosswalk is not one-to-one baseline-only")
    feature_names = [x for x in rows[0] if x.startswith("2:") or x.startswith("3:")]
    if len(feature_names) != 20 or any(set(r) != set(rows[0]) for r in rows):
        raise ValueError("Feature schema is not the fixed 20-feature panel")
    contracts = {r.get("feature_contract_sha256") for r in rows}
    if len(contracts) != 1 or not next(iter(contracts)):
        raise ValueError("Matched features do not share one recorded feature contract")
    feature_contract_sha256 = next(iter(contracts))
    parsed = np.full((len(rows), len(feature_names)), np.nan)
    for i, row in enumerate(rows):
        for j, key in enumerate(feature_names):
            raw = row.get(key, "")
            if raw not in (None, "", "None", "nan", "NaN"):
                val = float(raw)
                if math.isfinite(val):
                    parsed[i, j] = val
    availability = np.isfinite(parsed).mean(axis=0)
    # Keep the prespecified feature panel fixed. Do not perform a full-cohort
    # variance or outcome-based filter; imputation is fit within each training fold.
    kept_names = feature_names

    # Verify endpoint against the pinned official v5 CSV row-by-row; local IDs remain private.
    cohort_rows = list(csv.DictReader(cohort_csv.open("r", encoding="utf-8-sig", newline="")))
    meta = {r["ID"].strip(): r for r in cohort_rows if r.get("ID") and "_FU" not in r["ID"]}
    clinical, times, events = [], [], []
    for i, row in enumerate(rows):
        source = meta.get(row["clinical_id"])
        if not source or source.get("ID", "").strip() != row["clinical_id"]:
            raise ValueError("Clinical ID does not join exactly to official v5 baseline metadata")
        if (int(float(source["OS"])) != int(row["os_days"]) or int(source["1-dead 0-alive"]) != int(row["event"])
                or source["Sex"] != row["sex"] or float(source["Age at MRI"]) != float(row["age_at_mri_years"])):
            raise ValueError("Feature table clinical endpoint or demographics disagree with pinned v5 source")
        clinical.append([float(row["age_at_mri_years"]), float(row["sex"] == "M")])
        times.append(float(row["os_days"]))
        events.append(int(row["event"]))
    clinical, times, events = np.asarray(clinical), np.asarray(times), np.asarray(events, dtype=int)
    if len(rows) < 100 or events.sum() < 50 or len(np.unique(events)) < 2:
        raise ValueError(f"Matched cohort too small for prespecified 5-fold comparison: N={len(rows)}, events={events.sum()}")
    if not (np.isfinite(times).all() and (times > 0).all() and np.isfinite(clinical).all()):
        raise ValueError("Invalid endpoint or clinical features")
    # Median imputation and standardization are fitted separately in each training fold.
    names = ["clinical_age_sex_ridge", "radiomics_ridge", "radiomics_elastic_net",
             "clinical_radiomics_ridge", "clinical_radiomics_elastic_net"]
    results, candidate_failures = [], {}
    for name in names:
        try:
            results.append(cv_candidate(clinical, parsed, times, events, name))
        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
            candidate_failures[name] = {"status": "FAILED", "error_type": type(exc).__name__, "reason": str(exc)[:500]}
    if not results or results[0]["name"] != "clinical_age_sex_ridge":
        raise RuntimeError(f"The matched clinical baseline did not fit: {candidate_failures.get(names[0])}")
    baseline = results[0]["_oof_risk"]
    paired = {result["name"]: paired_bootstrap_delta(times, events, result["_oof_risk"], baseline, SEED + i + 1)
              for i, result in enumerate(results[1:])}
    c_intervals = {result["name"]: bootstrap_c_index_ci(times, events, result["_oof_risk"], SEED + 101 + i)
                   for i, result in enumerate(results)}
    # Time-point support and Brier scores are provided per fold; explicitly report the censor-survival support.
    horizons_support = {}
    for h in HORIZONS:
        vals = [base.censor_survival(times[tr], events[tr], h) for tr, _ in StratifiedKFold(n_splits=FOLDS, shuffle=True, random_state=SEED).split(np.zeros(len(rows)), events)]
        horizons_support[str(int(h))] = {"minimum_training_censor_survival": float(min(vals)), "fold_values": vals,
                                           "warning": "IPCW scores are unstable/unavailable where censoring survival approaches zero."}
    # Write no patient IDs or OOF predictions to the aggregate results.
    clean = []
    for result in results:
        clean.append({k: v for k, v in result.items() if not k.startswith("_")})
    out.mkdir(parents=True)
    report = {"status": "EXPLORATORY_INTERNAL_PATIENT_LEVEL_CV",
              "dataset": "UCSF-PDGM v5 pinned mirror cohort; reference-mask BrainFusion features",
              "n": len(rows), "events": int(events.sum()), "censored": int(len(events)-events.sum()),
              "brats21_mapped_cases_in_model_cohort": sum(bool(r.get("brats21_id", "").strip()) for r in rows),
              "brats21_unmapped_cases_in_model_cohort": sum(not bool(r.get("brats21_id", "").strip()) for r in rows),
              "cohort_sha256_private_table": sha256(feature_csv), "official_clinical_csv_sha256": sha256(cohort_csv),
              "endpoint": "OS days from initial diagnosis to last clinical follow-up; event=1 dead, 0 alive/censored, per TCIA v5 glossary.",
              "prediction_landmark": "Diagnostic MRI; diagnosis-to-scan interval absent from reviewed fields.",
              "models": clean, "candidate_failures": candidate_failures,
              "oof_c_index_patient_bootstrap_95ci": c_intervals,
              "paired_oof_c_index_deltas_vs_matched_clinical": paired,
              "outer_validation": {"method": "StratifiedKFold on one row per patient", "folds": FOLDS, "seed": SEED,
                                   "identifiers_unique": True, "same_folds_for_all_models": True,
                                   "feature_median_imputation_fit_inside_training_fold": True,
                                   "feature_scaling_fit_inside_cox_training_fold": True,
                                   "hyperparameter_search": "None; fixed alpha=0.01, Elastic-Net l1_ratio=0.5"},
              "feature_panel": {"count_requested": len(feature_names), "count_used": len(kept_names), "names": kept_names,
                                "contract_sha256": feature_contract_sha256,
                                "per_feature_nonmissing_fraction": {name: float(value) for name, value in zip(feature_names, availability)},
                                "source": "Fixed selected-20 WAW IDH-derived BrainFusion panel; no survival-outcome selection",
                                "radiomics_feature_missing_cell_fraction": float(1.0-np.isfinite(parsed).mean()),
                                "patient_id_table_local_only": True},
              "ipcw_support": horizons_support,
              "software": {"python": platform.python_version(), "numpy": np.__version__, "scikit_learn": sklearn.__version__},
              "analysis_script_sha256": sha256(Path(__file__).resolve()),
              "limitations": ["This is exploratory internal CV on TCIA v5 OS; it is not an independently validated clinical model.",
                              "OS origin is initial diagnosis whereas age is measured at MRI; diagnosis-to-MRI time interval is unavailable.",
                              "The fixed feature panel originated in an unrelated WAW IDH task and is not UCSF-survival validated.",
                              "Public-reference features are used; no automated segmentation features or segmentation inference were generated in this analysis.",
                              "Known BraTS21 mapping overlap is disclosed in cohort metadata; no independent segmentation validation claim is made."]}
    path = out / "model-comparison-aggregate.json"
    path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    sums = out / "SHA256SUMS.txt"
    sums.write_text(f"{sha256(path)}  model-comparison-aggregate.json\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "n": report["n"], "events": report["events"],
                      "censored": report["censored"], "features_used": len(kept_names),
                      "candidate_failures": candidate_failures,
                      "models": [{"name": x["name"], "pooled_oof_c_index": x["pooled_oof_c_index"],
                                  "mean_fold_c_index": x["mean_fold_c_index"], "ibs": x.get("mean_fold_ibs")} for x in results]}, indent=2))


if __name__ == "__main__":
    main()
