"""Fit the final full-cohort research Cox artifact for the audited 4-feature CaPTk panel.

This reuses the existing 596-row five-fold comparison (verified by hash) and
fits only the final inference artifact. Scan IDs and patient-level rows remain
in memory; output contains aggregate fit metadata and model parameters only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.research.survival import EndpointContract, cox_ph, validate_endpoint  # noqa: E402

EXPECTED_CLINICAL_SHA256 = "fd5749ae5a8d77e599e02264d961d94107752f0244e34bf0bc711a75fe0e2ec5"
EXPECTED_RADIOMICS_SHA256 = "e3d9df986fb64a0d42674c7c79527f4110fb920e58e80981b3d317aa1f188fbb"
EXPECTED_CV_SHA256 = "259d52e8a5b123d10381edad852b67bd4fd68820e218753cc3552079c1dc0d58"
SEED = 20261026
L2 = 0.1
ENDPOINT_RULE = (
    "Researcher-defined S1: baseline _11 only; Deceased with positive "
    "Survival_from_surgery_days_UPDATED is event; Alive or Lost to Follow-up "
    "with positive Survival_Censor is censored; uncertain-date deaths excluded. "
    "The censor time is assumed days in first-surgery context; official censor "
    "semantics/unit/origin/derivation and updated event-time rule remain unresolved."
)
FEATURES = [
    ("T1GD", "ET", "T1GD_ET_Intensity_Mean"),
    ("FLAIR", "ED", "FLAIR_ED_Intensity_Mean"),
    ("T2", "ED", "T2_ED_Intensity_Mean"),
    ("T1", "NC", "T1_NC_Intensity_Mean"),
]
CLINICAL_NAMES = ["age_years", "gender_M", "IDH1_mutated", "IDH1_NOS_NEC", "GTR_over_90pct"]
FEATURE_NAMES = CLINICAL_NAMES + [entry[2] for entry in FEATURES]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def number(value):
    try:
        result = float(str(value).strip())
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def read_csv_bytes(data: bytes) -> list[dict]:
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline="")))


def candidates(clinical_path: Path) -> list[dict]:
    if sha256(clinical_path) != EXPECTED_CLINICAL_SHA256:
        raise ValueError("Official clinical CSV hash differs from the audited v1.2 input.")
    with clinical_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
    if len(rows) != 671:
        raise ValueError("Official clinical v1.2 row count differs from the audited 671 rows.")
    output = []
    for row in rows:
        scan_id = str(row.get("ID", "")).strip()
        if not scan_id.endswith("_11"):
            continue
        status = str(row.get("Survival_Status", "")).strip()
        event_time = number(row.get("Survival_from_surgery_days_UPDATED"))
        censor_time = number(row.get("Survival_Censor"))
        if status == "Deceased" and event_time is not None and event_time > 0:
            duration, event = event_time, 1
        elif status in {"Alive", "Lost to Follow-up"} and censor_time is not None and censor_time > 0:
            duration, event = censor_time, 0
        else:
            continue
        output.append({"scan_id": scan_id, "patient_id": scan_id[:-3], "duration": duration,
                       "event": event, "row": row})
    if (len(output) != 608 or sum(r["event"] for r in output) != 585
            or len({r["patient_id"] for r in output}) != len(output)):
        raise ValueError("Researcher-defined S1 cohort differs from the audited 608/585 counts.")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clinical", type=Path, required=True)
    parser.add_argument("--radiomics-zip", type=Path, required=True)
    parser.add_argument("--existing-cv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if not output.is_relative_to(Path("E:/BrainFusion-Runtime/research-edition").resolve()):
        raise ValueError("Fusion model may only be written under the controlled research runtime.")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite model output: {output}")
    if sha256(args.radiomics_zip.resolve()) != EXPECTED_RADIOMICS_SHA256:
        raise ValueError("CaPTk feature archive hash differs from the audited official asset.")
    if sha256(args.existing_cv.resolve()) != EXPECTED_CV_SHA256:
        raise ValueError("Existing 596-row fusion CV result differs from the verified result.")
    cv = json.loads(args.existing_cv.read_text(encoding="utf-8"))
    combined = cv.get("models", {}).get("clinical_plus_radiomics", {})
    if (cv.get("cohort", {}).get("n") != 596
            or cv.get("radiomics", {}).get("features") != [feature for _, _, feature in FEATURES]
            or combined.get("n") != 596 or combined.get("events") != 574
            or combined.get("candidate_censored") != 22
            or not combined.get("five_fold_patient_level_cv")):
        raise ValueError("Existing CV provenance does not match the prespecified fusion panel/cohort.")

    rows = candidates(args.clinical.resolve())
    selected: dict[str, dict[str, float | None]] = {}
    with zipfile.ZipFile(args.radiomics_zip.resolve()) as archive:
        for modality, region, feature in FEATURES:
            expected_name = f"Radiomic_Features_CaPTk_automaticsegm_{modality}_{region}.csv"
            matches = [name for name in archive.namelist() if name.endswith(expected_name)]
            if len(matches) != 1:
                raise ValueError(f"Expected exactly one CaPTk table {expected_name} in archive.")
            table_rows = read_csv_bytes(archive.read(matches[0]))
            if not table_rows or "SubjectID" not in table_rows[0] or feature not in table_rows[0]:
                raise ValueError(f"CaPTk table missing expected ID/feature columns: {expected_name}")
            ids = [str(table.get("SubjectID", "")).strip() for table in table_rows]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate SubjectID in selected CaPTk table {expected_name}.")
            for table in table_rows:
                scan_id = str(table.get("SubjectID", "")).strip()
                selected.setdefault(scan_id, {})[feature] = number(table.get(feature))

    analysis = []
    missing_radiomics = 0
    for candidate in rows:
        values = selected.get(candidate["scan_id"], {})
        radiomics = [values.get(feature) for _, _, feature in FEATURES]
        if any(value is None for value in radiomics):
            missing_radiomics += 1
            continue
        clinical = candidate["row"]
        gender = str(clinical.get("Gender", "")).strip()
        gender_m = 1.0 if gender == "M" else (0.0 if gender == "F" else None)
        idh = str(clinical.get("IDH1", "")).strip()
        idh_mutated = 1.0 if idh == "Mutated" else 0.0
        idh_nos = 1.0 if idh == "NOS/NEC" else 0.0
        resection = str(clinical.get("GTR_over90percent", "")).strip()
        gtr = 1.0 if resection == "Y" else (0.0 if resection == "N" else None)
        clinical_features = [number(clinical.get("Age_at_scan_years")), gender_m,
                             idh_mutated, idh_nos, gtr]
        analysis.append({**{k: candidate[k] for k in ("patient_id", "duration", "event")},
                         "features": clinical_features + radiomics})
    if (len(analysis) != 596 or missing_radiomics != 12
            or sum(r["event"] for r in analysis) != 574):
        raise ValueError("Feature-complete fusion cohort differs from audited N=596/574/22 and 12 missing.")
    if len({r["patient_id"] for r in analysis}) != len(analysis):
        raise ValueError("Duplicate patients in feature-complete cohort.")

    matrix = np.asarray([row["features"] for row in analysis], dtype=float)
    medians = np.nanmedian(matrix, axis=0)
    if not np.isfinite(medians).all():
        raise ValueError("At least one selected feature has no finite training value.")
    missing = ~np.isfinite(matrix)
    for column in range(matrix.shape[1]):
        matrix[missing[:, column], column] = medians[column]
    means = np.mean(matrix, axis=0)
    scales = np.std(matrix, axis=0)
    if not np.isfinite(scales).all() or np.any(scales <= np.finfo(float).eps):
        raise ValueError("A prespecified fusion feature is constant after training-cohort imputation.")

    endpoint_rows = [{"patient_id": row["patient_id"], "duration": row["duration"],
                      "event": str(row["event"]), "origin": ENDPOINT_RULE} for row in analysis]
    contract = EndpointContract("OS", "patient_id", "duration", "event", "origin", ENDPOINT_RULE,
                                "days", "1", "0", True)
    audit = validate_endpoint(endpoint_rows, contract)
    if not audit["eligible"]:
        raise ValueError("Fusion endpoint contract failed: " + ", ".join(audit["issues"]))
    fit = cox_ph(audit, matrix, FEATURE_NAMES, l2=L2)
    if not fit.get("converged"):
        raise ValueError("Final full-cohort fusion Cox fit did not converge.")
    coefficients_standardized = [fit["coefficients"][name] * float(scale)
                                 for name, scale in zip(FEATURE_NAMES, scales)]
    linear_predictor = ((matrix - means) / scales) @ np.asarray(coefficients_standardized)
    durations = np.asarray([row["duration"] for row in analysis], dtype=float)
    events = np.asarray([row["event"] for row in analysis], dtype=int)
    event_times = np.unique(durations[events == 1])
    increments = []
    for time in event_times:
        count = int(np.sum((durations == time) & (events == 1)))
        risk_sum = float(np.exp(linear_predictor[durations >= time]).sum())
        if count <= 0 or not math.isfinite(risk_sum) or risk_sum <= 0:
            raise ValueError("Fusion Breslow baseline hazard calculation failed.")
        increments.append(count / risk_sum)
    cumulative_hazard = np.cumsum(np.asarray(increments, dtype=float))
    baseline_survival = np.exp(-cumulative_hazard)

    model = {
        "artifact_schema_version": 1,
        "model_id": "upenn-clinical-captk-fusion-cox-research",
        "model_version": "1.0.0-research-only",
        "model_type": "CoxPH",
        "research_only": True,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "endpoint": {"name": "OS", "status": "RESEARCHER_DEFINED_ENDPOINT_WITH_LIMITATIONS",
                     "official_endpoint_validated": False, "time_unit": "days",
                     "time_origin": "assumed first-surgery context; censor origin is not officially documented",
                     "rule": ENDPOINT_RULE},
        "features": {
            "names": FEATURE_NAMES,
            "means": means.tolist(), "scales": scales.tolist(),
            "coefficients_standardized": coefficients_standardized,
            "imputation_medians": medians.tolist(),
            "encoding": {"inputs": ["age_years", "gender", "IDH1", "GTR_over90percent"],
                         "age_unit": "years", "gender_reference": "F",
                         "IDH1_reference": "Wildtype; Mutated and NOS/NEC one-hot indicators",
                         "GTR_reference": "N; unknown/missing imputed to training median",
                         "unknown_handling": "training-cohort median imputation; fitted from final training cohort"},
            "radiomics": {"source": "TCIA official CaPTk radiomic_features_CaPTk.zip",
                          "segmentation": "automatic-segmentation-derived",
                          "feature_names": [feature for _, _, feature in FEATURES],
                          "feature_rows": "exact full scan ID join; baseline _11 only",
                          "units": "original CaPTk intensity means; modality-specific intensity scale",
                          "BrainFusion_20_feature_mapping": False,
                          "required_inputs": [feature for _, _, feature in FEATURES]},
            "training_ranges": {"age_years": [float(matrix[:, 0].min()), float(matrix[:, 0].max())]},
        },
        "baseline": {"method": "Breslow cumulative baseline hazard at standardized x=0",
                     "times_days": event_times.tolist(),
                     "cumulative_hazard": cumulative_hazard.tolist(),
                     "survival": baseline_survival.tolist()},
        "training": {"n": len(analysis), "events": int(events.sum()),
                     "censored": int((events == 0).sum()), "baseline_records": 611,
                     "candidate_s1_n": 608, "candidate_s1_events": 585,
                     "candidate_s1_censored": 23, "feature_missing_rows_excluded": missing_radiomics,
                     "patient_unit": "normalized patient; exact scan-key join; baseline _11 only",
                     "input_sha256": {"clinical_csv": EXPECTED_CLINICAL_SHA256,
                                      "official_captk_archive": EXPECTED_RADIOMICS_SHA256,
                                      "existing_cv_results": EXPECTED_CV_SHA256},
                     "trainer_sha256": sha256(Path(__file__).resolve()),
                     "source_commit_at_run": "a1c1fe33497c6f93512b00804f8fe4cee714fd0b",
                     "seed": SEED, "l2_penalty": L2, "tie_method": "Breslow"},
        "validation": {"status": "REUSED_EXISTING_INTERNAL_PATIENT_LEVEL_CV_NOT_RERUN",
                       "source": "previously audited analysis-v2/fusion-cv-results.json",
                       "source_sha256": EXPECTED_CV_SHA256,
                       "method": "5-fold patient-level stratified CV; fold-local median imputation/scaling; seed 20261026",
                       "cohort_n": 596, "candidate_events": 574, "candidate_censored": 22,
                       "clinical_only_mean_fold_c_index": cv["models"]["clinical_only"]["fold_c_index_mean"],
                       "clinical_only_fold_c_index_sd": cv["models"]["clinical_only"]["fold_c_index_sd"],
                       "fusion_mean_fold_c_index": combined["fold_c_index_mean"],
                       "fusion_fold_c_index_sd": combined["fold_c_index_sd"],
                       "radiomics_only_mean_fold_c_index": cv["models"]["radiomics_only"]["fold_c_index_mean"],
                       "radiomics_only_fold_c_index_sd": cv["models"]["radiomics_only"]["fold_c_index_sd"],
                       "external_validation": False, "clinical_validation": False,
                       "one_year_classification": "NOT_RUN"},
        "optimizer": {"converged": bool(fit["converged"]), "message": fit["optimizer_message"]},
        "diagnostics": {"scope": "full-cohort exploratory trend screen only; not a formal PH test",
                        "proportional_hazards_screening": fit["proportional_hazards_screening"]},
        "limitations": [
            "RESEARCH_ONLY: official OS endpoint definitions remain incomplete.",
            "The model uses a researcher-defined S1 event/censor rule and assumed day-based first-surgery context.",
            "Four CaPTk features are automatic-segmentation-derived and do not represent BrainFusion radiomics.",
            "Internal CV is reused from the audited run and provides no independent external validation or clinical utility evidence.",
            "The fused model's previous CV comparison showed no demonstrated gain over the clinical model.",
            "Prediction API accepts only synthetic requests; no patient-level predictions are stored.",
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    artifact_path = output / "cox-model.json"
    manifest_path = output / "model-manifest.json"
    if artifact_path.exists() or manifest_path.exists():
        raise FileExistsError("Refusing to overwrite a fusion model artifact.")
    artifact_path.write_text(json.dumps(model, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    manifest = {"artifact_schema_version": 1, "model_id": model["model_id"],
                "model_version": model["model_version"], "model_type": model["model_type"],
                "research_only": True, "artifact_file": "cox-model.json",
                "artifact_sha256": sha256(artifact_path),
                "source_commit": model["training"]["source_commit_at_run"]}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"model_id": model["model_id"], "model_version": model["model_version"],
                      "n": len(analysis), "events": int(events.sum()), "censored": int((events == 0).sum()),
                      "cv_reused": True, "cv_fusion_mean_c_index": model["validation"]["fusion_mean_fold_c_index"],
                      "final_converged": model["optimizer"]["converged"],
                      "artifact_sha256": manifest["artifact_sha256"], "artifact_dir": str(output)}, indent=2))


if __name__ == "__main__":
    main()
