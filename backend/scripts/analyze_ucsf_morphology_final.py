"""Pre-specified UCSF reference-mask morphology comparison and feature QC.

Reads only existing verified 367-case feature/mask metadata and existing ten-case
mask sensitivity outputs. It performs no downloads, feature extraction, or inference.
Patient-level intermediate tables stay in the protected data directory.
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
import scipy
from scipy.stats import skew, spearmanr
import sklearn

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from scripts import compare_ucsf_reference_radiomics_fusion_v2 as comparison

LABEL_COUNTS_DIR = Path("E:/BrainFusion-Data/UCSF-PDGM/fusion-v2/derived/reference-radiomics-selected20-v1/cases")
PILOT_DIR = Path("E:/BrainFusion-Data/UCSF-PDGM/fusion-v2/pilot-mask-feature-sensitivity-v1")
PILOT_SUMMARY = Path("E:/BrainFusion-Runtime/research-edition/results/ucsf-pdgm-mask-feature-sensitivity-20261027-v1/feature-sensitivity-summary.json")
COHORT_CSV = Path("E:/BrainFusion-Data/UCSF-PDGM/clinical/UCSF-PDGM-metadata_v5.csv")
EXPECTED_V5_SHA256 = comparison.EXPECTED_CLINICAL_SHA256
MORPH_FEATURES = ["log1p_WT_volume_ml", "log1p_TC_volume_ml", "log1p_ET_volume_ml",
                  "edema_fraction_WT", "ET_fraction_TC"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def morphology_from_counts(counts: dict[str, int], spacing_mm: list[float]) -> dict[str, float]:
    """Convert verified BraTS 0/1/2/4 voxel counts to physical ROIs and ratios."""
    if set(counts) - {"0", "1", "2", "4"}:
        raise ValueError("Reference mask contains unsupported labels")
    voxel_mm3 = float(np.prod(np.asarray(spacing_mm, dtype=float)))
    if not math.isfinite(voxel_mm3) or voxel_mm3 <= 0:
        raise ValueError("Invalid physical voxel volume")
    necrosis = int(counts.get("1", 0))
    edema = int(counts.get("2", 0))
    enhancing = int(counts.get("4", 0))
    wt, tc, et = necrosis + edema + enhancing, necrosis + enhancing, enhancing
    if wt <= 0 or tc <= 0:
        raise ValueError("Undefined morphology ratio because WT or TC denominator is zero")
    scale = voxel_mm3 / 1000.0
    wt_ml, tc_ml, et_ml = wt * scale, tc * scale, et * scale
    vals = {"WT_volume_ml": wt_ml, "TC_volume_ml": tc_ml, "ET_volume_ml": et_ml,
            "log1p_WT_volume_ml": math.log1p(wt_ml),
            "log1p_TC_volume_ml": math.log1p(tc_ml),
            "log1p_ET_volume_ml": math.log1p(et_ml),
            "edema_fraction_WT": edema / wt,
            "ET_fraction_TC": et / tc}
    if not all(math.isfinite(v) for v in vals.values()):
        raise ValueError("Non-finite morphology feature")
    if not (0 <= vals["edema_fraction_WT"] <= 1 and 0 <= vals["ET_fraction_TC"] <= 1):
        raise ValueError("Morphology ratio outside [0,1]")
    return vals


def feature_qc(rows: list[dict[str, str]], feature_names: list[str]) -> dict:
    matrix = np.asarray([[float(row[name]) for name in feature_names] for row in rows], dtype=float)
    if not np.isfinite(matrix).all():
        raise ValueError("Fixed selected-20 panel includes non-finite values")
    per_feature = {}
    for index, name in enumerate(feature_names):
        values = matrix[:, index]
        q1, q3 = np.quantile(values, [0.25, 0.75])
        iqr = float(q3 - q1)
        lower, upper = float(q1 - 1.5 * iqr), float(q3 + 1.5 * iqr)
        median = float(np.median(values))
        per_feature[name] = {"n_finite": len(values), "median": median,
                             "q1": float(q1), "q3": float(q3), "iqr": iqr,
                             "minimum": float(np.min(values)), "maximum": float(np.max(values)),
                             "skewness_unadjusted": float(skew(values, bias=True)),
                             "iqr_fence_outlier_n_descriptive_only": int(np.count_nonzero((values < lower) | (values > upper)))}
    corr = np.eye(len(feature_names), dtype=float)
    for i in range(len(feature_names)):
        for j in range(i + 1, len(feature_names)):
            rho = spearmanr(matrix[:, i], matrix[:, j]).statistic
            corr[i, j] = corr[j, i] = float(rho)
    pairs = [{"feature_a": feature_names[i], "feature_b": feature_names[j], "spearman_rho": float(corr[i, j])}
             for i in range(len(feature_names)) for j in range(i + 1, len(feature_names))
             if abs(corr[i, j]) >= 0.85]
    return {"n_patients": len(rows), "panel_n": len(feature_names), "finite_cells": int(matrix.size),
            "missing_or_nonfinite_cells": 0, "per_feature": per_feature,
            "high_rank_correlation_threshold_abs_rho": 0.85, "high_correlation_pair_count": len(pairs),
            "high_correlation_pairs": pairs,
            "outlier_rule": "Descriptive Tukey 1.5xIQR fences; values are not removed or winsorized.",
            "selection_rule": "Fixed WAW IDH-derived selected-20 panel; no UCSF outcome-based selection or filtering.",
            "limitations": ["Distribution summaries and correlations are descriptive and do not justify outcome-driven selection.",
                            "The selected-20 panel has a WAW IDH task provenance and is not UCSF-survival validated."]}


def pilot_stability(feature_csv: Path, detail_json: Path, feature_names: list[str]) -> dict:
    with feature_csv.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    details = json.loads(detail_json.read_text(encoding="utf-8"))
    if len(rows) != 10 or len(details) != 10:
        raise ValueError("Expected the existing ten-case paired mask sensitivity set")
    detail_by_id = {item.get("patient_id"): item for item in details}
    row_by_id = {item.get("patient_id"): item for item in rows}
    if None in detail_by_id or len(detail_by_id) != 10 or set(detail_by_id) != set(row_by_id):
        raise ValueError("Existing pilot feature and recall records are not paired one-to-one")
    case_medians = {"2": [], "3": []}
    recalls = {region: [] for region in ("WT", "TC", "ET")}
    feature_correlations = {"2": [], "3": []}
    for patient in sorted(row_by_id):
        row, detail = row_by_id[patient], detail_by_id[patient]
        if detail.get("prediction_features_valid") != 20:
            raise ValueError("Existing prediction feature vector is incomplete")
        for region in recalls:
            recalls[region].append(float(detail[f"{region}_recall"]))
        for label in ("2", "3"):
            names = [name for name in feature_names if name.startswith(label + ":")]
            diffs = []
            ref_vals, pred_vals = [], []
            for name in names:
                ref = float(row[f"reference::{name}"])
                pred = float(row[f"prediction::{name}"])
                diffs.append(abs(pred - ref) / max(abs(ref), 1e-8))
                ref_vals.append(ref); pred_vals.append(pred)
            case_medians[label].append(float(np.median(diffs)))
    # Verify the stored prior aggregate independently using its patient-level source,
    # but expose only group-level summaries in the Runtime evidence.
    case_recall = [{"2": case_medians["2"][i], "3": case_medians["3"][i],
                    **{f"{region}_recall": recalls[region][i] for region in recalls}}
                   for i in range(len(rows))]
    recall_association = {}
    associations = {"2": "WT", "3": "ET"}
    for label, region in associations.items():
        rho = spearmanr([x[label] for x in case_recall], recalls[region]).statistic
        recall_association[label] = {"feature_group": "edema-related" if label == "2" else "enhancing-related",
                                     "recall_region": region, "spearman_rho_descriptive": float(rho), "n": 10}
    groups = {}
    for label, vals in case_medians.items():
        groups[label] = {"feature_count": sum(name.startswith(label + ":") for name in feature_names),
                         "case_median_absolute_relative_difference_median": float(np.median(vals)),
                         "case_median_absolute_relative_difference_q1_q3": [float(x) for x in np.quantile(vals, [0.25, 0.75])],
                         "case_median_absolute_relative_difference_range": [float(min(vals)), float(max(vals))]}
    low_recall = {}
    for region, vals in recalls.items():
        low_n = math.ceil(len(vals) / 4)
        low = sorted(vals)[:low_n]
        low_recall[region] = {"bottom_quartile_n": low_n, "bottom_quartile_mean_recall": float(np.mean(low)),
                              "minimum_recall": float(min(vals))}
    prior = json.loads(PILOT_SUMMARY.read_text(encoding="utf-8"))
    recomputed = {label: {"median_absolute_relative_difference": float(np.median(np.concatenate([
        [abs(float(row[f"prediction::{name}"]) - float(row[f"reference::{name}"])) / max(abs(float(row[f"reference::{name}"])), 1e-8)
         for row in rows] for name in feature_names if name.startswith(label + ":")])))} for label in ("2", "3")}
    return {"status": "DESCRIPTIVE_PILOT_STABILITY_REANALYSIS", "n_patients": 10,
            "segmentation_inference_rerun": False, "feature_extraction_rerun": False,
            "reference_vs_prediction_feature_error": groups,
            "case_level_feature_error_vs_recall": recall_association,
            "low_recall_summary": low_recall,
            "stored_aggregate_check": {label: {"recomputed": recomputed[label]["median_absolute_relative_difference"],
                                               "stored": prior["automatic_prediction_comparison"][label]["median_absolute_relative_difference"],
                                               "absolute_difference": abs(recomputed[label]["median_absolute_relative_difference"] - prior["automatic_prediction_comparison"][label]["median_absolute_relative_difference"])}
                                       for label in ("2", "3")},
            "feature_group_semantics": {"2": "edema-related selected features", "3": "enhancing-tumor-related selected features"},
            "limitations": ["Ten-case descriptive pilot; no independent test-set or survival-validation claim.",
                            "Case-wise error/recall association is descriptive and not an inferential effect estimate.",
                            "Mask disagreement can alter feature values; no conclusion is made about downstream survival performance."]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--feature-table", type=Path, required=True)
    parser.add_argument("--output-private", type=Path, required=True)
    parser.add_argument("--output-runtime", type=Path, required=True)
    args = parser.parse_args()
    data_root = args.data_root.resolve(strict=True)
    feature_table = args.feature_table.resolve(strict=True)
    private_out = args.output_private.resolve()
    runtime_out = args.output_runtime.resolve()
    if private_out.exists() or runtime_out.exists():
        raise FileExistsError("Refusing to overwrite prior evidence; choose a new versioned output directory")
    clinical = Path("E:/BrainFusion-Data/UCSF-PDGM/clinical/UCSF-PDGM-metadata_v5.csv").resolve(strict=True)
    if sha256(clinical) != EXPECTED_V5_SHA256:
        raise ValueError("Official v5 clinical CSV hash differs from the reviewed fixed source")
    with feature_table.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 367:
        raise ValueError(f"Expected the previously verified 367-case table, got {len(rows)}")
    ids = [row["patient_id"] for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate patient key in protected fixed feature table")
    feature_names = [key for key in rows[0] if key.startswith(("2:", "3:"))]
    if len(feature_names) != 20 or len({row.get("feature_contract_sha256") for row in rows}) != 1:
        raise ValueError("Feature schema/contract is not the existing fixed 20-panel")
    qc = feature_qc(rows, feature_names)

    case_files = {path.stem.removesuffix("-private"): path for path in LABEL_COUNTS_DIR.glob("*-private.json")}
    if set(case_files) != set(ids):
        raise ValueError("Stored reference-mask metadata is not an exact match to the existing 367-case table")
    morphology_rows = []
    for row in rows:
        case = json.loads(case_files[row["patient_id"]].read_text(encoding="utf-8"))
        if case["reference_mask_sha256"] == "" or case.get("extractor_status") not in ("succeeded", "reused_existing_pilot_verified"):
            raise ValueError("Reference feature metadata is not verified")
        geom = case["geometry"]["t1c"]
        vals = morphology_from_counts(case["reference_label_counts"], geom["spacing_mm"])
        morphology_rows.append({"patient_id": row["patient_id"], "age_at_mri_years": float(row["age_at_mri_years"]),
                                "sex_male": int(row["sex"] == "M"), "os_days": float(row["os_days"]),
                                "event": int(row["event"]), **vals,
                                "reference_mask_sha256": case["reference_mask_sha256"]})
    if len(morphology_rows) != 367:
        raise ValueError("Morphology cohort count changed unexpectedly")
    private_out.mkdir(parents=True)
    private_csv = private_out / "reference-morphology-private.csv"
    with private_csv.open("w", newline="", encoding="utf-8") as stream:
        fields = list(morphology_rows[0])
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(morphology_rows)

    clinical_x = np.asarray([[float(row["age_at_mri_years"]), int(row["sex"] == "M")] for row in rows], dtype=float)
    times = np.asarray([float(row["os_days"]) for row in rows], dtype=float)
    events = np.asarray([int(row["event"]) for row in rows], dtype=int)
    morph_x = np.asarray([[float(row[name]) for name in MORPH_FEATURES] for row in morphology_rows], dtype=float)
    if not np.isfinite(morph_x).all() or not np.isfinite(times).all() or np.any(times <= 0):
        raise ValueError("Non-finite morphology/endpoint values")
    # Reuse the same fixed five patient-level folds, alpha, metrics, and paired bootstrap.
    baseline = comparison.cv_candidate(clinical_x, morph_x, times, events, "clinical_age_sex_ridge")
    morphology = comparison.cv_candidate(np.zeros_like(clinical_x), morph_x, times, events, "radiomics_ridge")
    clinical_morphology = comparison.cv_candidate(clinical_x, morph_x, times, events, "clinical_radiomics_ridge")
    baseline["name"] = "clinical_age_sex_ridge_same_cohort"
    morphology["name"] = "reference_morphology_ridge"
    clinical_morphology["name"] = "clinical_plus_reference_morphology_ridge"
    paired = {
        morphology["name"]: comparison.paired_bootstrap_delta(times, events, morphology["_oof_risk"], baseline["_oof_risk"], comparison.SEED + 301),
        clinical_morphology["name"]: comparison.paired_bootstrap_delta(times, events, clinical_morphology["_oof_risk"], baseline["_oof_risk"], comparison.SEED + 302),
    }
    cis = {
        model["name"]: comparison.bootstrap_c_index_ci(times, events, model["_oof_risk"], comparison.SEED + 401 + index)
        for index, model in enumerate((baseline, morphology, clinical_morphology))
    }
    models = [{key: val for key, val in model.items() if not key.startswith("_")}
              for model in (baseline, morphology, clinical_morphology)]
    pilot = pilot_stability(PILOT_DIR / "reference-vs-prediction-selected20.csv",
                            PILOT_DIR / "case-recall-and-mask-hashes.json", feature_names)
    morphology_summary = {}
    for column, name in enumerate(MORPH_FEATURES):
        values = morph_x[:, column]
        q1, median, q3 = np.quantile(values, [0.25, 0.5, 0.75])
        morphology_summary[name] = {"median": float(median), "q1": float(q1), "q3": float(q3),
                                    "minimum": float(np.min(values)), "maximum": float(np.max(values))}
    volume_summary = {}
    for name in ("WT_volume_ml", "TC_volume_ml", "ET_volume_ml"):
        values = np.asarray([float(row[name]) for row in morphology_rows])
        q1, median, q3 = np.quantile(values, [0.25, 0.5, 0.75])
        volume_summary[name] = {"median": float(median), "q1": float(q1), "q3": float(q3),
                                "minimum": float(np.min(values)), "maximum": float(np.max(values))}
    morphology_corr = np.corrcoef(morph_x, rowvar=False)
    morphology_correlations = [{"feature_a": MORPH_FEATURES[i], "feature_b": MORPH_FEATURES[j],
                                "pearson_r": float(morphology_corr[i, j])}
                               for i in range(len(MORPH_FEATURES)) for j in range(i + 1, len(MORPH_FEATURES))]
    runtime_out.mkdir(parents=True)
    output = {"status": "EXPLORATORY_INTERNAL_PATIENT_LEVEL_CV",
              "pre_specified_question": "Do reference-mask morphology features add prognostic information beyond age and sex in the same 367-case UCSF cohort?",
              "cohort": {"n": len(rows), "events": int(events.sum()), "censored": int(len(events) - events.sum()),
                         "unique_patient_keys": len(set(ids)), "clinical_csv_sha256": sha256(clinical),
                         "existing_feature_table_sha256_private": sha256(feature_table),
                         "morphology_table_sha256_private": sha256(private_csv),
                         "reference_mask_hash_set_sha256": hashlib.sha256("\n".join(sorted(
                             json.loads(case_files[patient].read_text(encoding="utf-8"))["reference_mask_sha256"]
                             for patient in ids)).encode("ascii")).hexdigest(),
                         "existing_reference_mask_metadata_cases": len(case_files)},
              "morphology_definition": {"source_labels": {"1": "necrotic/non-enhancing core", "2": "edema/infiltrative region", "4": "enhancing tumor"},
                                        "WT": "labels 1+2+4", "TC": "labels 1+4", "ET": "label 4",
                                        "features": MORPH_FEATURES,
                                        "volume_unit": "mL; voxel counts multiplied by stored reference-grid spacing product and divided by 1000",
                                        "ratio_definitions": {"edema_fraction_WT": "label-2 volume / WT volume", "ET_fraction_TC": "label-4 volume / TC volume"},
                                        "invalid_denominator_exclusions": 0,
                                        "volumes_model_transformation": "natural log(1 + volume_mL)",
                                        "physical_volume_distribution_mL": volume_summary,
                                        "aggregate_feature_distribution": morphology_summary,
                                        "feature_correlation_descriptive_only": morphology_correlations},
              "endpoint_and_landmark": {"endpoint": "OS days from initial diagnosis to last clinical follow-up; event=dead per TCIA v5 glossary.",
                                         "diagnosis_to_MRI_interval": "Not available in reviewed v5 cohort fields; no origin alignment was imputed.",
                                         "interpretation": "Exploratory association only; MRI landmark does not align exactly to OS origin."},
              "models": models, "patient_bootstrap_oof_c_index_95ci": cis,
              "paired_oof_c_index_deltas_vs_same_cohort_clinical": paired,
              "validation": {"folds": 5, "patient_level_event_stratified": True, "seed": comparison.SEED,
                             "same_folds_as_existing_comparison": True, "fixed_alpha": comparison.ALPHA,
                             "no_hyperparameter_search": True, "standardization_fit_in_training_fold": True,
                             "fixed_oof_uncertainty_bootstraps": comparison.BOOTSTRAPS,
                             "brier_and_ibs": "Calculated with the same censoring-aware evaluator used for the existing comparison."},
              "fixed_20_feature_qc": qc,
              "existing_ten_case_mask_feature_stability": pilot,
              "diagnosis_mri_timepoint_review": {"official_source_hash": EXPECTED_V5_SHA256,
                                                  "glossary_fields": ["OS", "Age at MRI", "1-dead 0-alive"],
                                                  "has_diagnosis_to_mri_interval": False,
                                                  "status": "UNRESOLVED_INTERVAL; no fabricated date or time origin"},
              "scripts": {"analysis_script_sha256": sha256(Path(__file__).resolve())},
              "software": {"python": platform.python_version(), "numpy": np.__version__,
                           "scipy": scipy.__version__, "scikit_learn": sklearn.__version__},
              "limitations": ["All model comparisons use the same single UCSF cohort and fixed patient-level folds; no independent external validation.",
                              "OS begins at initial diagnosis, while MRI is acquired later; diagnosis-to-MRI interval is not reported in the reviewed v5 fields.",
                              "Only five pre-specified morphology summaries were compared; the result does not establish that morphology is generally non-informative.",
                              "The 20-feature radiomics panel was selected in a separate WAW IDH task, not for UCSF OS.",
                              "The ten-case automated-mask sensitivity pilot is descriptive and is not a survival-validation cohort."]}
    aggregate = runtime_out / "morphology-feature-stability-results.json"
    aggregate.write_text(json.dumps(output, indent=2, allow_nan=False), encoding="utf-8")
    files = [private_csv, aggregate]
    (runtime_out / "SHA256SUMS.txt").write_text("".join(f"{sha256(p)}  {p.name}\n" for p in files), encoding="utf-8")
    print(json.dumps({"status": output["status"], "n": output["cohort"]["n"], "events": output["cohort"]["events"],
                      "censored": output["cohort"]["censored"], "models": [
                          {"name": m["name"], "pooled_oof_c_index": m["pooled_oof_c_index"],
                           "ibs": m["mean_fold_ibs_180_1095_days"],
                           "brier_365_730_1095": [m["ipcw_brier"][str(h)]["mean_fold_ipcw_brier"] for h in (365,730,1095)]}
                          for m in models], "paired_deltas": paired,
                      "high_correlations": qc["high_correlation_pair_count"], "pilot": pilot["reference_vs_prediction_feature_error"]}, indent=2))


if __name__ == "__main__":
    main()
