"""Finalize a completed pilot from its already-written artifacts (no inference)."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.research.feature_contract import PROTOCOL, contract_hash, selected_features


CHECKPOINT_SHA256 = "860ccb3f1c21c99d0410ad8a1ac4ef6b8fab60cec0a503b0ba42675741a750ae"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def json_native(value):
    if isinstance(value, dict):
        return {str(k): json_native(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_native(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--checkpoint-dir", type=Path, default=Path("E:/BrainFusion-Runtime/models/monai-brats"))
    parser.add_argument("--radiomics-research-dir", type=Path, default=Path("E:/BrainFusion-Runtime/results/research"))
    parser.add_argument("--refresh-summary", action="store_true",
                        help="Refresh only this pilot's generated aggregate JSON/report/hash after verifying its status and pinned source")
    args = parser.parse_args()
    data_root, out = args.data_root.resolve(strict=True), args.output_root.resolve(strict=True)
    result_path = out / "PILOT-RESULTS.json"
    if result_path.exists() and not args.refresh_summary:
        raise FileExistsError(f"Refusing to overwrite existing result: {result_path}")

    manifest = load_json(data_root / "subset-manifest.json")
    if manifest.get("dataset") != "MedOtter/UCSF-PDGM" or manifest.get("revision") != "e9372219cf1cd2fdd52260cd45f7514b4aa7638e":
        raise ValueError("Unexpected dataset source/revision")
    cases = manifest.get("selected_cases", [])
    if result_path.exists():
        previous = load_json(result_path)
        if (previous.get("status") != "PILOT_DATA_FLOW_COMPLETE_SURVIVAL_MODELING_NOT_ESTIMABLE"
                or previous.get("subset_revision") != manifest.get("revision")):
            raise ValueError("Existing result is not this pinned pilot; refusing summary refresh")
    ids = [case["patient_id"] for case in cases]
    if len(ids) != 10 or len(set(ids)) != 10:
        raise ValueError("Expected ten unique pilot cases")
    if manifest.get("downloaded_files") != 50:
        raise ValueError("Expected five verified MRI/mask files per case")
    for case in cases:
        for record in case["files"]:
            path = data_root / "cases" / case["patient_id"] / Path(record["path"]).name
            if not path.is_file() or path.stat().st_size != record["size"] or digest(path) != record["lfs_sha256"]:
                raise ValueError(f"Pinned source file failed integrity validation: {record['path']}")

    metrics_path = out / "segmentation" / "case-metrics.json"
    qc_path = out / "qc" / "space-and-input-hashes.json"
    private_csv = data_root / "derived" / out.name / "matched-clinical-radiomics.csv"
    crosswalk = data_root / "derived" / out.name / "clinical-image-crosswalk.csv"
    if any(not p.is_file() for p in (metrics_path, qc_path, private_csv, crosswalk)):
        raise FileNotFoundError("A required completed pilot artifact is absent; no inference is run by this finalizer")
    segmentation_rows = load_json(metrics_path)
    qc_rows = load_json(qc_path)
    if {r["patient_id"] for r in segmentation_rows} != set(ids) or {r["patient_id"] for r in qc_rows} != set(ids):
        raise ValueError("The inference/QC artifacts do not cover exactly the pinned patient set")
    for row in segmentation_rows:
        if row["metrics"].get("independent_external_validation") is not False:
            raise ValueError("Independent-validation status is not explicitly false")
        if row["checkpoint_sha256"] != CHECKPOINT_SHA256:
            raise ValueError("A prediction does not reference the reviewed checkpoint hash")
        for p in (out / "predictions" / row["patient_id"] / "prediction.nii.gz",
                  out / "overlays" / f"{row['patient_id']}_comparison.png"):
            if not p.is_file():
                raise FileNotFoundError(p)

    with private_csv.open("r", encoding="utf-8-sig", newline="") as f:
        private_rows = list(csv.DictReader(f))
    with crosswalk.open("r", encoding="utf-8-sig", newline="") as f:
        crosswalk_rows = list(csv.DictReader(f))
    if len(private_rows) != 10 or len(crosswalk_rows) != 10:
        raise ValueError("Patient-level feature/crosswalk tables are incomplete")
    if {r["patient_id"] for r in private_rows} != set(ids) or {r["image_folder_id"] for r in crosswalk_rows} != set(ids):
        raise ValueError("Patient-level join does not cover the exact selected cases")
    if len({r["normalized_numeric_id"] for r in private_rows}) != 10:
        raise ValueError("Duplicate normalized patient ID in matched feature table")

    feature_pointer = args.radiomics_research_dir.resolve(strict=True) / "latest.json"
    pointer = load_json(feature_pointer)
    feature_run = feature_pointer.parent / pointer["run_id"]
    feature_summary = load_json(feature_run / "summary.json")
    bundle = feature_run / "models.joblib"
    if digest(bundle) != feature_summary["artifact_sha256"]["models.joblib"]:
        raise ValueError("Existing BrainFusion feature-contract bundle hash mismatch")
    import joblib
    feature_bundle = joblib.load(bundle)
    features = selected_features(feature_bundle)
    feature_contract_sha = contract_hash(feature_bundle)
    if len(features) != 20:
        raise ValueError("Expected the existing selected-20 feature contract")
    feature_complete = [all(r.get(k, "") not in ("", "None", "nan") and math.isfinite(float(r[k])) for k in features)
                        for r in private_rows]
    if not all(feature_complete):
        raise ValueError("One or more matched cases have incomplete selected-20 feature vectors")

    regions = ("WT", "TC", "ET")
    aggregate = {}
    for region in regions:
        dice = [float(r["metrics"]["regions"][region]["dice"]) for r in segmentation_rows]
        precision = [float(r["metrics"]["regions"][region]["precision"]) for r in segmentation_rows
                     if r["metrics"]["regions"][region]["precision"] is not None]
        recall = [float(r["metrics"]["regions"][region]["recall"]) for r in segmentation_rows
                  if r["metrics"]["regions"][region]["recall"] is not None]
        hd95 = [float(r["metrics"]["regions"][region]["hd95_mm"]) for r in segmentation_rows
                if r["metrics"]["regions"][region]["hd95_mm"] is not None]
        pred_volume = [float(r["metrics"]["volumes_ml"][region]) for r in segmentation_rows]
        ref_volume = [float(r["metrics"]["reference_volumes_ml"][region]) for r in segmentation_rows]
        aggregate[region] = {"dice_mean": statistics.fmean(dice), "dice_sd": statistics.stdev(dice),
                             "dice_median": statistics.median(dice), "dice_range": [min(dice), max(dice)],
                             "precision_mean": statistics.fmean(precision) if precision else None,
                             "recall_mean": statistics.fmean(recall) if recall else None,
                             "hd95_mm_mean": statistics.fmean(hd95) if hd95 else None,
                             "hd95_mm_median": statistics.median(hd95) if hd95 else None,
                             "n_hd95_available": len(hd95),
                             "prediction_volume_ml_mean": statistics.fmean(pred_volume),
                             "reference_volume_ml_mean": statistics.fmean(ref_volume),
                             "volume_delta_ml_mean": statistics.fmean([a - b for a, b in zip(pred_volume, ref_volume)])}

    n_events = sum(int(r["event_1_dead_0_alive"]) for r in private_rows)
    checkpoint_dir = args.checkpoint_dir.resolve(strict=True)
    checkpoint = checkpoint_dir / "models" / "model.pt"
    checkpoint_source = load_json(checkpoint_dir / "source.json")
    model_metadata = load_json(checkpoint_dir / "configs" / "metadata.json")
    if digest(checkpoint) != CHECKPOINT_SHA256:
        raise ValueError("SegResNet checkpoint hash mismatch")

    result = {
        "status": "PILOT_DATA_FLOW_COMPLETE_SURVIVAL_MODELING_NOT_ESTIMABLE",
        "dataset": "UCSF-PDGM v5 via MedOtter derived BraTS-format subset",
        "subset_revision": manifest["revision"], "subset_manifest_sha256": digest(data_root / "subset-manifest.json"),
        "official_metadata_sha256": manifest["clinical_comparison"]["UCSF-PDGM-metadata_v5.csv"]["official_local_sha256"],
        "source_comparison": manifest["clinical_comparison"],
        "overlap_screening": {"field": "TCIA v5 metadata BraTS21 ID", "selected_cases_nonempty_ids": 0,
                              "selection_excluded_nonempty_mapping_ids": True,
                              "direct_mapping_workbook_url": "https://wiki.cancerimagingarchive.net/download/attachments/210043011/BraTS2021_MappingToTCIA.xlsx?api=v2",
                              "workbook_download_status": "FAILED_TLS_HANDSHAKE; cohort exclusion used the byte-identical v5 metadata field instead",
                              "limitation": "This screens the published BraTS21 mapping field only; it does not resolve overlap with the checkpoint's BraTS2018 training cases."},
        "cohort": {"n": 10, "events_in_pilot": n_events, "censored_in_pilot": 10 - n_events,
                    "selection": manifest["selection"], "baseline_only": True,
                    "selected_all_without_bratS21_mapping": True,
                    "event_stratified_sample_not_population_representative": True,
                    "same_patient_join": "Normalized numeric patient ID from the official baseline clinical ID maps to the four-digit image folder; ten unique IDs checked."},
        "model": {"name": model_metadata["name"], "source_revision": checkpoint_source.get("sha"),
                  "checkpoint_sha256": CHECKPOINT_SHA256, "training_data_source": model_metadata.get("data_source"),
                  "reported_training_volumes": 285, "reported_split": {"train": 200, "validation": 42, "test": 43},
                  "training_case_manifest_available": False, "training_overlap_with_ucsf": "UNKNOWN"},
        "segmentation": {"status": "PUBLIC_REFERENCE_AGREEMENT", "metrics": aggregate,
                         "regions": {"WT": "prediction labels 1/2/3; reference 1/2/4", "TC": "prediction 1/3; reference 1/4", "ET": "prediction 3; reference 4"},
                         "reference_conversion_for_evaluator": "Derived copy only: 0/1/2/4 -> 0/1/2/3 by 4->3; originals unchanged.",
                         "case_metrics_path": str(metrics_path), "overlays_path": str(out / "overlays"),
                         "independent_external_validation": False,
                         "limitation": "MONAI public checkpoint reports BraTS 2018 training. Its exact training-case list is unavailable, so overlap with UCSF cannot be excluded."},
        "radiomics": {"status": "MATCHED_FEATURE_EXTRACTION_COMPLETE", "n": 10, "complete_selected20_vectors": 10,
                      "contract_sha256": feature_contract_sha, "feature_bundle_sha256": digest(bundle),
                      "feature_names": features,
                      "contract_limitation": "This selected-20 panel was derived from a separate WAW IDH task; it was reused unchanged as a pilot extraction panel and is not presented as UCSF-survival-selected."},
        "survival_model_comparison": {
            "clinical_age_sex_baseline": "NOT_REEVALUATED: pilot IDs overlap the UCSF model-development cohort and no held-out comparison was predeclared.",
            "radiomics_only_cox": "NOT_FIT: n=10 with 20 features is insufficient for meaningful patient-level validation.",
            "clinical_plus_radiomics_cox": "NOT_FIT: n=10 with 20 features is insufficient for meaningful patient-level validation.",
            "rsf": "NOT_RUN: cohort too small; no compatible scikit-survival dependency was used.",
            "relative_fusion_gain": "NOT_ESTIMATED"},
        "spatial_qc": {"all_four_sequences_and_reference_geometry_match": all(r["sequence_geometries_match"] and r["reference_geometry_matches"] for r in qc_rows),
                        "shape": [240, 240, 155], "spacing_mm": [1.0, 1.0, 1.0], "label_encoding": [0, 1, 2, 4]},
        "evidence_paths": {"case_metrics": str(metrics_path), "space_and_input_hashes": str(qc_path),
                           "patient_level_crosswalk_and_features": str(crosswalk),
                           "patient_level_outputs_location": str(data_root / "derived" / out.name)},
        "software": {"prediction_persistence": "none", "inference_count": 10,
                     "feature_contract_sha256": feature_contract_sha,
                     "checkpoint_sha256": CHECKPOINT_SHA256}
    }
    result_path.write_text(json.dumps(json_native(result), indent=2, allow_nan=False), encoding="utf-8")
    report = [
        "# UCSF-PDGM matched pilot — 2026-10-27",
        "",
        "Status: **PILOT_DATA_FLOW_COMPLETE_SURVIVAL_MODELING_NOT_ESTIMABLE**.",
        "",
        "Ten event-stratified, baseline IDH-wildtype GBM cases were acquired from immutable MedOtter revision `e9372219cf1cd2fdd52260cd45f7514b4aa7638e`. All 50 MRI/reference files match the repository LFS SHA-256; the mirror v5 metadata and glossary are byte-identical to the locally held TCIA-designated copies. Patient joins use normalized numeric IDs, not row order.",
        "",
        f"All ten cases completed the existing SegResNet pipeline, WT/TC/ET public-reference comparison and the unchanged BrainFusion selected-20 radiomics panel. {n_events} cases carry candidate death status and {10-n_events} candidate alive/censored status in the source table; this deliberately event-stratified pilot is not a survival cohort.",
        "",
        "## Aggregate segmentation agreement (mean ± SD)",
        "",
        "| Region | Dice | HD95 (mm) |",
        "|---|---:|---:|",
    ]
    for region in regions:
        a = aggregate[region]
        report.append(f"| {region} | {a['dice_mean']:.4f} ± {a['dice_sd']:.4f} | {a['hd95_mm_mean']:.2f} |")
    report += [
        "",
        "Mean precision / recall and mean predicted/reference/delta volume in ml are included per region in `PILOT-RESULTS.json`; exact case-level TP/FP/FN, precision/recall, volume and metrics are in the protected `segmentation/case-metrics.csv`.",
        "",
        "The cohort excluded cases with a populated official v5 `BraTS21 ID` field. The separately linked TCIA mapping workbook attachment was attempted but failed its TLS handshake; the blank v5 field in the official CSV (also byte-identical to the pinned mirror CSV) was the actual per-case screening criterion. The workbook failure does not change this pilot's public-reference status, but the checkpoint's BraTS2018 overlap remains unknown.",
    ]
    report += [
        "",
        "These are public-reference agreement measurements, not independent external validation: the MONAI checkpoint is described as BraTS 2018-trained, but an exact training-case manifest is unavailable. Reference source is the pinned mirror's dataset card, which describes the labels as neuroradiologist manually corrected/approved and identifies 0/1/2/4 semantics; the full TCIA image package was not downloaded for bytewise comparison.",
        "",
        "## Same-patient radiomics data",
        "",
        f"Extracted {len(features)} existing BrainFusion selected features for all ten matched patients (complete vectors: {sum(feature_complete)}/10). The feature panel was selected in an unrelated WAW IDH task and is reused only for pipeline feasibility; it is not reselected or validated for UCSF survival.",
        "",
        "## Survival/fusion conclusions",
        "",
        "No Cox, fusion survival model, or RSF was fitted. With only ten event-stratified cases and twenty imaging features, a patient-level survival comparison would be severely underpowered and leakage-prone. Do not interpret this pilot as evidence of model performance or fusion benefit.",
        "",
        "Patient-level crosswalk/features remain under the protected `E:\\BrainFusion-Data` derived path recorded in `PILOT-RESULTS.json`; this evidence directory contains aggregate results and paths only.",
    ]
    (out / "PILOT-REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    sums = []
    for path in sorted(p for p in out.rglob("*") if p.is_file() and p.name != "SHA256SUMS.txt"):
        sums.append(f"{digest(path)}  {path.relative_to(out).as_posix()}")
    (out / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "n": 10, "events": n_events,
                      "censored": 10 - n_events, "feature_complete_n": sum(feature_complete),
                      "segmentation_means": aggregate}, indent=2))


if __name__ == "__main__":
    main()
