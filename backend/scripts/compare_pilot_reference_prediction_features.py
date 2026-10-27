"""Compare existing reference-mask vs existing prediction-mask radiomics for ten cases.

This script performs no segmentation inference. It reuses reference features from
the completed pilot and extracts the same fixed 20-feature contract on existing
prediction masks only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy.stats import spearmanr

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.research.feature_contract import PROTOCOL, contract_hash, selected_features


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-data-root", type=Path, required=True)
    parser.add_argument("--pilot-runtime-root", type=Path, required=True)
    parser.add_argument("--radiomics-research-dir", type=Path, default=Path("E:/BrainFusion-Runtime/results/research"))
    parser.add_argument("--radiomics-worker", type=Path, default=Path("E:/BrainFusion-Runtime/envs/radiomics311-delivery-20261010T081105_95f1c109-independent/python.exe"))
    parser.add_argument("--output-data-root", type=Path, required=True)
    parser.add_argument("--output-runtime-root", type=Path, required=True)
    args = parser.parse_args()
    data_root, prior_runtime = args.pilot_data_root.resolve(strict=True), args.pilot_runtime_root.resolve(strict=True)
    data_out, runtime_out = args.output_data_root.resolve(), args.output_runtime_root.resolve()
    if data_out.exists() or runtime_out.exists():
        raise FileExistsError("Sensitivity output version already exists; refusing overwrite")
    worker = args.radiomics_worker.resolve(strict=True)
    manifest = json.loads((data_root / "subset-manifest.json").read_text(encoding="utf-8"))
    metric_rows = json.loads((prior_runtime / "segmentation" / "case-metrics.json").read_text(encoding="utf-8"))
    reference_csv = data_root / "derived" / prior_runtime.name / "matched-clinical-radiomics.csv"
    with reference_csv.open("r", encoding="utf-8-sig", newline="") as f:
        ref_rows = list(csv.DictReader(f))
    patient_ids = {c["patient_id"] for c in manifest["selected_cases"]}
    if {r["patient_id"] for r in metric_rows} != patient_ids or {r["patient_id"] for r in ref_rows} != patient_ids:
        raise ValueError("Prior pilot feature/metric records do not align exactly")

    feature_pointer = args.radiomics_research_dir.resolve(strict=True) / "latest.json"
    pointer = json.loads(feature_pointer.read_text(encoding="utf-8"))
    feature_run = feature_pointer.parent / pointer["run_id"]
    summary = json.loads((feature_run / "summary.json").read_text(encoding="utf-8"))
    bundle_path = feature_run / "models.joblib"
    if digest(bundle_path) != summary["artifact_sha256"]["models.joblib"]:
        raise ValueError("Existing selected-feature contract bundle hash mismatch")
    import joblib
    bundle = joblib.load(bundle_path)
    features = selected_features(bundle)
    if len(features) != 20:
        raise ValueError("Expected exact prior BrainFusion selected-20 panel")
    contract_sha = contract_hash(bundle)
    ref_by_id = {r["patient_id"]: r for r in ref_rows}
    metrics_by_id = {r["patient_id"]: r for r in metric_rows}
    source_map = {r["patient_id"]: r for r in manifest["selected_cases"]}
    data_out.mkdir(parents=True)
    case_results, feature_rows = [], []
    for patient in sorted(patient_ids):
        case_dir = data_root / "cases" / patient
        pred_path = prior_runtime / "predictions" / patient / "prediction.nii.gz"
        ref_mask = data_root / "derived" / prior_runtime.name / patient / "reference_bf_1_2_3.nii.gz"
        if not pred_path.is_file() or not ref_mask.is_file():
            raise FileNotFoundError(f"Missing existing prediction or recoded reference for {patient}")
        pimg, rimg = nib.load(str(pred_path), mmap=True), nib.load(str(ref_mask), mmap=True)
        if pimg.shape != rimg.shape or not np.allclose(pimg.affine, rimg.affine, atol=1e-4, rtol=0):
            raise ValueError(f"Prediction/reference geometry mismatch for {patient}")
        sequences = {key: str(case_dir / f"{patient}_{suffix}.nii.gz") for key, suffix in
                     (("t1c", "T1c"), ("t1n", "T1"), ("t2w", "T2"), ("t2f", "FLAIR"))}
        request_path = data_out / f"{patient}-prediction-radiomics-request.json"
        feature_path = data_out / f"{patient}-prediction-radiomics.json"
        request = {"sequences": sequences, "mask_path": str(pred_path), "selected_features": features,
                   "protocol": PROTOCOL, "contract_sha256": contract_sha,
                   "feature_source": "Existing SegResNet prediction mask; sensitivity comparison only; no retraining or clinical prediction"}
        request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")
        error = None
        try:
            subprocess.run([str(worker), "-B", str(BACKEND / "tools" / "extract_selected_radiomics.py"),
                            "--request", str(request_path), "--output", str(feature_path)],
                           cwd=str(BACKEND), timeout=300, check=True, capture_output=True, text=True)
            result = json.loads(feature_path.read_text(encoding="utf-8"))
            if result.get("status") != "succeeded" or set(result.get("features", {})) != set(features):
                error = f"Prediction-mask feature contract failed: {result.get('status')}"
                predicted = {}
            else:
                predicted = result["features"]
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError) as exc:
            error = f"{type(exc).__name__}: {str(exc)[:500]}"
            predicted = {}
        row = {"patient_id": patient, "clinical_id": ref_by_id[patient]["clinical_id"]}
        valid_prediction = 0
        for key in features:
            rv = float(ref_by_id[patient][key])
            raw_pv = predicted.get(key)
            try:
                pv = float(raw_pv)
            except (TypeError, ValueError):
                pv = float("nan")
            if not math.isfinite(rv):
                raise ValueError(f"Nonfinite reference feature value for {patient}, {key}")
            if math.isfinite(pv):
                valid_prediction += 1
            row[f"reference::{key}"] = rv
            row[f"prediction::{key}"] = pv if math.isfinite(pv) else ""
            row[f"absolute_delta::{key}"] = pv - rv if math.isfinite(pv) else ""
        feature_rows.append(row)
        metrics = metrics_by_id[patient]["metrics"]["regions"]
        rec = {"patient_id": patient, "reference_mask_sha256": digest(ref_mask),
               "prediction_mask_sha256": digest(pred_path), "prediction_feature_output_sha256": digest(feature_path) if feature_path.is_file() else None,
               "WT_recall": metrics["WT"]["recall"], "TC_recall": metrics["TC"]["recall"],
               "ET_recall": metrics["ET"]["recall"], "reference_feature_vector_complete": True,
               "prediction_feature_vector_complete": valid_prediction == len(features),
               "prediction_features_valid": valid_prediction, "prediction_feature_error": error}
        case_results.append(rec)
        print(f"Compared existing masks for one pilot case; valid prediction features {valid_prediction}/{len(features)}")

    feature_fields = ["patient_id", "clinical_id"] + [f"{prefix}::{name}" for name in features
                      for prefix in ("reference", "prediction", "absolute_delta")]
    feature_table = data_out / "reference-vs-prediction-selected20.csv"
    with feature_table.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=feature_fields)
        w.writeheader(); w.writerows(feature_rows)
    runtime_out.mkdir(parents=True)
    metric_groups = {}
    for label in ("2", "3"):
        keys = [name for name in features if name.startswith(label + ":")]
        deltas, correlations = [], []
        for key in keys:
            pairs = [(float(r[f"reference::{key}"]), float(r[f"prediction::{key}"])) for r in feature_rows
                     if r[f"prediction::{key}"] != "" and math.isfinite(float(r[f"prediction::{key}"]))]
            if not pairs:
                continue
            rv = np.asarray([x[0] for x in pairs])
            pv = np.asarray([x[1] for x in pairs])
            denom = np.maximum(np.abs(rv), 1e-8)
            deltas.extend((np.abs(pv - rv) / denom).tolist())
            if np.std(rv) > 0 and np.std(pv) > 0:
                correlations.append(float(spearmanr(rv, pv).statistic))
        metric_groups[label] = {"feature_count": len(keys), "median_absolute_relative_difference": float(np.median(deltas)) if deltas else None,
                               "spearman_feature_case_correlations_median": float(np.median(correlations)) if correlations else None,
                               "valid_correlations": len(correlations)}
    low_recall = {}
    for region in ("WT", "TC", "ET"):
        ordered = sorted(case_results, key=lambda r: (float("inf") if r[f"{region}_recall"] is None else r[f"{region}_recall"], r["patient_id"]))
        valid = [float(r[f"{region}_recall"]) for r in ordered if r[f"{region}_recall"] is not None]
        low_recall[region] = {"bottom_quartile_n": max(1, math.ceil(len(ordered) / 4)),
                              "bottom_quartile_mean_recall": float(np.mean(valid[:max(1, math.ceil(len(ordered)/4))])) if valid else None,
                              "minimum_recall": min(valid) if valid else None}
    result = {"status": "DESCRIPTIVE_PILOT_FEATURE_SENSITIVITY", "n": len(feature_rows),
              "segmentation_inference_rerun": False, "feature_contract_sha256": contract_sha,
              "feature_bundle_sha256": digest(bundle_path), "radiomics_worker_sha256": digest(worker),
              "reference_feature_source_sha256": digest(reference_csv),
              "automatic_prediction_comparison": metric_groups,
              "label_group_definition": {"2": "edema-related selected features", "3": "enhancing-tumor-related selected features"},
              "low_recall_summary": low_recall,
              "case_detail_path": str(data_out / "case-recall-and-mask-hashes.json"),
              "limitations": ["Ten-case event-stratified pilot only; descriptive, no inferential claims.",
                              "BrainFusion panel was selected in a separate WAW IDH task and is not UCSF-survival validated.",
                              "Mask-derived feature changes reflect segmentation disagreement and are not survival-model performance."]}
    (data_out / "case-recall-and-mask-hashes.json").write_text(json.dumps(case_results, indent=2), encoding="utf-8")
    (runtime_out / "feature-sensitivity-summary.json").write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    files = [p for p in data_out.rglob("*") if p.is_file()] + [p for p in runtime_out.rglob("*") if p.is_file()]
    lines = [f"{digest(path)}  {path.relative_to(path.anchor)}" for path in sorted(files)]
    (runtime_out / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "n": len(feature_rows), "groups": metric_groups,
                      "low_recall": low_recall}, indent=2))


if __name__ == "__main__":
    main()
