"""Run a bounded UCSF-PDGM multi-case segmentation/radiomics feasibility pilot.

All predictions and case-level outputs are written only under a new protected
runtime directory. This script intentionally does not fit a survival model:
the event-stratified 5-10-case convenience pilot is not an estimable cohort.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import nibabel as nib
import numpy as np
from PIL import Image, ImageDraw


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.ai.imaging.monai_segmenter import SegmentationInput, segment, sha256
from app.services.segmentation_metrics import evaluate
from app.research.feature_contract import PROTOCOL, selected_features, contract_hash
from app.core.config import settings

EXPECTED_CHECKPOINT = "860ccb3f1c21c99d0410ad8a1ac4ef6b8fab60cec0a503b0ba42675741a750ae"
SEQUENCES = {"t1c": "T1c", "t1n": "T1", "t2w": "T2", "t2f": "FLAIR"}


def file_digest(path: Path) -> str:
    return sha256(str(path))


def json_native(value):
    """Convert NumPy scalar/array values to standard JSON values."""
    if isinstance(value, dict):
        return {str(k): json_native(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_native(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def read_metadata(path: Path) -> dict[int, dict[str, str]]:
    rows: dict[int, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            raw = row["ID"].strip()
            if "_FU" in raw:
                continue
            number = int(raw.rsplit("-", 1)[1])
            if number in rows:
                raise ValueError(f"Duplicate normalized baseline clinical ID {number}")
            rows[number] = row
    return rows


def recode_reference_labels(reference: np.ndarray) -> np.ndarray:
    """Map UCSF/BraTS labels 0/1/2/4 to the existing evaluator's 0/1/2/3.

    This operates on a derived array only; the source NIfTI is never changed.
    """
    if not np.isin(np.unique(reference), [0, 1, 2, 4]).all():
        raise ValueError("UCSF reference labels must be a subset of 0/1/2/4")
    recoded = np.zeros(reference.shape, dtype=np.uint8)
    recoded[reference == 1] = 1
    recoded[reference == 2] = 2
    recoded[reference == 4] = 3
    return recoded


def overlay(image_path: Path, reference_path: Path, prediction_path: Path, target: Path) -> int:
    image = nib.load(str(image_path), mmap=False)
    reference = np.asarray(nib.load(str(reference_path), mmap=False).dataobj)
    prediction = np.asarray(nib.load(str(prediction_path), mmap=False).dataobj)
    tumor = reference > 0
    if not tumor.any():
        tumor = prediction > 0
    z = int(np.argmax(tumor.sum(axis=(0, 1)))) if tumor.any() else image.shape[2] // 2
    gray = np.asarray(image.dataobj[:, :, z], dtype=np.float32)
    nonzero = gray[np.isfinite(gray) & (gray != 0)]
    low, high = np.percentile(nonzero, [1, 99]) if nonzero.size else (float(gray.min()), float(gray.max()))
    if not high > low:
        high = low + 1
    base = np.clip((gray - low) / (high - low), 0, 1)
    base = np.flipud(np.rot90(base))
    rgb = np.repeat((base * 255).astype(np.uint8)[..., None], 3, axis=2)
    ref = np.flipud(np.rot90(reference[:, :, z] > 0))
    pred = np.flipud(np.rot90(prediction[:, :, z] > 0))
    overlap_mask = ref & pred
    panels = []
    for title, selected, color in (
        ("T1c", None, None),
        ("Reference (red)", ref, (255, 48, 48)),
        ("Prediction (cyan)", pred, (0, 220, 255)),
        ("Overlap (yellow)", overlap_mask, (255, 220, 0)),
    ):
        canvas = Image.fromarray(rgb.copy(), mode="RGB").resize((384, 384), Image.Resampling.NEAREST)
        if selected is not None:
            mask_img = Image.fromarray(selected.astype(np.uint8) * 255).resize((384, 384), Image.Resampling.NEAREST)
            color_img = Image.new("RGB", (384, 384), color)
            canvas.paste(color_img, mask=mask_img)
        panels.append((title, canvas))
    sheet = Image.new("RGB", (792, 808), "#202124")
    draw = ImageDraw.Draw(sheet)
    for i, (title, canvas) in enumerate(panels):
        x, y = 8 + (i % 2) * 392, 8 + (i // 2) * 400
        draw.text((x + 4, y + 2), f"{title} · axial z={z}", fill="white")
        sheet.paste(canvas, (x, y + 22))
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target, format="PNG", optimize=True)
    return z


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--clinical-csv", type=Path, default=Path("E:/BrainFusion-Data/UCSF-PDGM/clinical/UCSF-PDGM-metadata_v5.csv"))
    parser.add_argument("--checkpoint-dir", type=Path, default=Path("E:/BrainFusion-Runtime/models/monai-brats"))
    parser.add_argument("--radiomics-research-dir", type=Path, default=Path(settings.RESEARCH_DIR))
    parser.add_argument("--radiomics-worker", type=Path, default=Path("E:/BrainFusion-Runtime/envs/radiomics311-delivery-20261010T081105_95f1c109-independent/python.exe"))
    parser.add_argument("--case-count", type=int, default=10)
    args = parser.parse_args()
    data_root, out = args.data_root.resolve(strict=True), args.output_root.resolve()
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite a previous pilot run: {out}")
    checkpoint_dir = args.checkpoint_dir.resolve(strict=True)
    worker = args.radiomics_worker.resolve(strict=True)
    if not 5 <= args.case_count <= 10:
        raise ValueError("This controlled pilot is limited to 5-10 cases")
    manifest = json.loads((data_root / "subset-manifest.json").read_text(encoding="utf-8"))
    if manifest["dataset"] != "MedOtter/UCSF-PDGM" or manifest["revision"] != "e9372219cf1cd2fdd52260cd45f7514b4aa7638e":
        raise ValueError("Input subset does not match the pinned dataset revision")
    cases = manifest["selected_cases"]
    if len(cases) != args.case_count:
        raise ValueError(f"Expected {args.case_count} cases, found {len(cases)}")
    metadata_csv = data_root / "sources" / "TCIA-v5-local-official" / "UCSF-PDGM-metadata_v5.csv"
    clinical = read_metadata(metadata_csv)
    if file_digest(args.clinical_csv.resolve(strict=True)) != file_digest(metadata_csv):
        raise ValueError("Analysis clinical CSV differs from the copied, hash-verified official v5 file")
    checkpoint = checkpoint_dir / "models" / "model.pt"
    checkpoint_hash = file_digest(checkpoint)
    if checkpoint_hash != EXPECTED_CHECKPOINT:
        raise ValueError("SegResNet checkpoint SHA-256 does not match the reviewed source")
    checkpoint_source = json.loads((checkpoint_dir / "source.json").read_text(encoding="utf-8"))
    metadata = json.loads((checkpoint_dir / "configs" / "metadata.json").read_text(encoding="utf-8"))

    pointer_file = args.radiomics_research_dir.resolve(strict=True) / "latest.json"
    pointer = json.loads(pointer_file.read_text(encoding="utf-8"))
    feature_run = pointer_file.parent / pointer["run_id"]
    summary = json.loads((feature_run / "summary.json").read_text(encoding="utf-8"))
    bundle_path = feature_run / "models.joblib"
    if file_digest(bundle_path) != summary["artifact_sha256"]["models.joblib"]:
        raise ValueError("Existing BrainFusion radiomics research bundle hash mismatch")
    import joblib
    bundle = joblib.load(bundle_path)
    feature_keys = selected_features(bundle)
    if len(feature_keys) != 20 or len(set(feature_keys)) != 20:
        raise ValueError("Expected the existing selected 20-feature contract")
    feature_contract_sha = contract_hash(bundle)

    out.mkdir(parents=True, exist_ok=False)
    private_rows, segmentation_rows, qc_rows, feature_complete = [], [], [], []
    case_rows = []
    derived_root = data_root / "derived" / out.name
    derived_root.mkdir(parents=True, exist_ok=False)
    for case in cases:
        patient = case["patient_id"]
        number = int(case["normalized_numeric_id"])
        clinical_row = clinical.get(number)
        if clinical_row is None or clinical_row["ID"].strip() != case["clinical_id"]:
            raise ValueError(f"Normalized patient crosswalk failed for {patient}")
        if clinical_row["BraTS21 ID"].strip():
            raise ValueError(f"Selected case unexpectedly overlaps BraTS2021: {patient}")
        case_dir = data_root / "cases" / patient
        seq_paths = {seq: case_dir / f"{patient}_{suffix}.nii.gz" for seq, suffix in SEQUENCES.items()}
        original_mask = case_dir / f"{patient}_tumor_segmentation.nii.gz"
        if any(not p.is_file() for p in (*seq_paths.values(), original_mask)):
            raise FileNotFoundError(f"Missing one or more pinned MRI/mask files for {patient}")
        for record in case["files"]:
            path = data_root / "cases" / patient / Path(record["path"]).name
            if file_digest(path) != record["sha256"] or path.stat().st_size != record["size"]:
                raise ValueError(f"Pinned file hash changed since download for {patient}")
        images = {key: nib.load(str(path), mmap=False) for key, path in seq_paths.items()}
        ref_img = nib.load(str(original_mask), mmap=False)
        spatial = images["t1c"]
        for key, image in images.items():
            if image.shape != spatial.shape or not np.allclose(image.affine, spatial.affine, atol=1e-4, rtol=0):
                raise ValueError(f"MRI physical space/shape mismatch in {patient}: {key}")
            if not np.isfinite(np.asarray(image.dataobj)).all():
                raise ValueError(f"Nonfinite MRI voxels in {patient}: {key}")
        ref = np.asarray(ref_img.dataobj)
        if ref.shape != spatial.shape or not np.allclose(ref_img.affine, spatial.affine, atol=1e-4, rtol=0):
            raise ValueError(f"Reference mask shape/affine mismatch in {patient}")
        values, counts = np.unique(ref, return_counts=True)
        try:
            # 1: non-enhancing core, 2: edema, 4: enhancing tumor.
            recoded = recode_reference_labels(ref)
        except ValueError as exc:
            raise ValueError(f"Reference labels outside official 0/1/2/4 in {patient}") from exc
        case_derived = derived_root / patient
        case_derived.mkdir(parents=True)
        recoded_path = case_derived / "reference_bf_1_2_3.nii.gz"
        recoded_img = nib.Nifti1Image(recoded, ref_img.affine, header=ref_img.header.copy())
        recoded_img.set_qform(ref_img.get_qform(), int(ref_img.header["qform_code"]))
        recoded_img.set_sform(ref_img.get_sform(), int(ref_img.header["sform_code"]))
        nib.save(recoded_img, str(recoded_path))

        result_dir = out / "predictions" / patient
        start = time.perf_counter()
        seg_result = segment(SegmentationInput(
            sequences={key: str(path) for key, path in seq_paths.items()},
            output_dir=str(result_dir), model_dir=str(checkpoint_dir), roi=(128, 128, 96), gpu_budget_mb=6000,
        ))
        prediction = Path(seg_result["mask_path"])
        metrics = evaluate(prediction, recoded_path)
        metrics["scope"] = "PUBLIC_REFERENCE_AGREEMENT"
        metrics["independent_external_validation"] = False
        metrics["reason_not_independent"] = "MONAI checkpoint is BraTS2018-trained but its training-case manifest is not available; overlap with UCSF was not exhaustively excluded."
        overlay_file = out / "overlays" / f"{patient}_comparison.png"
        peak_slice = overlay(seq_paths["t1c"], original_mask, prediction, overlay_file)
        predicted_img = nib.load(str(prediction), mmap=False)
        pred_values, pred_counts = np.unique(np.asarray(predicted_img.dataobj), return_counts=True)
        case_metric = {"patient_id": patient, "metrics": metrics, "prediction_sha256": file_digest(prediction),
                       "reference_sha256": file_digest(original_mask), "recoded_reference_sha256": file_digest(recoded_path),
                       "overlay_sha256": file_digest(overlay_file), "peak_reference_tumor_slice": peak_slice,
                       "prediction_labels": {str(int(k)): int(v) for k, v in zip(pred_values, pred_counts)},
                       "reference_labels": {str(int(k)): int(v) for k, v in zip(values, counts)},
                       "inference_device": seg_result["device"], "inference_seconds": seg_result["seconds"],
                       "checkpoint_sha256": seg_result["checkpoint_sha256"],
                       "input_sha256": seg_result["input_sha256"]}
        segmentation_rows.append(case_metric)
        spatial_record = {"patient_id": patient, "shape": list(spatial.shape),
                          "spacing_mm": [float(x) for x in spatial.header.get_zooms()[:3]],
                          "affine": np.asarray(spatial.affine).round(6).tolist(),
                          "sequence_geometries_match": True, "reference_geometry_matches": True,
                          "official_label_counts": case_metric["reference_labels"],
                          "reference_sha256": file_digest(original_mask),
                          "image_sha256": {k: file_digest(p) for k, p in seq_paths.items()}}
        qc_rows.append(spatial_record)

        request_file = case_derived / "radiomics-request.json"
        feature_out = case_derived / "radiomics-features.json"
        request = {"sequences": {key: str(value) for key, value in seq_paths.items()},
                   "mask_path": str(recoded_path), "selected_features": feature_keys,
                   "protocol": PROTOCOL, "contract_sha256": feature_contract_sha,
                   "feature_source": "UCSF-PDGM v5 expert-corrected label recode 0/1/2/4 -> 0/1/2/3; predefined BrainFusion selected20 WAW-derived feature contract"}
        request_file.write_text(json.dumps(request, indent=2), encoding="utf-8")
        subprocess.run([str(worker), "-B", str(BACKEND / "tools" / "extract_selected_radiomics.py"),
                        "--request", str(request_file), "--output", str(feature_out)],
                       cwd=str(BACKEND), timeout=300, check=True, capture_output=True, text=True)
        feature_result = json.loads(feature_out.read_text(encoding="utf-8"))
        if feature_result.get("status") != "succeeded" or set(feature_result["features"]) != set(feature_keys):
            raise ValueError(f"Radiomics feature contract failed for {patient}")
        feature_row = {"patient_id": patient, "clinical_id": clinical_row["ID"],
                       "normalized_numeric_id": number,
                       "sex": clinical_row["Sex"], "age_at_mri_years": clinical_row["Age at MRI"],
                       "diagnosis": clinical_row["Final pathologic diagnosis (WHO 2021)"],
                       "idh": clinical_row["IDH"], "os_days": clinical_row["OS"],
                       "event_1_dead_0_alive": clinical_row["1-dead 0-alive"],
                       "brats21_id": clinical_row["BraTS21 ID"], **feature_result["features"],
                       "feature_source_mask_sha256": file_digest(original_mask),
                       "features_contract_sha256": feature_contract_sha}
        private_rows.append(feature_row)
        finite_count = sum(v is not None and np.isfinite(float(v)) for v in feature_result["features"].values())
        feature_complete.append(finite_count == len(feature_keys))
        case_rows.append({"patient_id": patient, "event": int(clinical_row["1-dead 0-alive"]),
                          "os_days": int(float(clinical_row["OS"])), "finite_selected_features": finite_count,
                          "selected_feature_count": len(feature_keys), "features_complete": finite_count == len(feature_keys),
                          "inference_seconds": round(time.perf_counter() - start, 2)})
        print(f"Processed {patient}: five pinned NIfTIs, prediction/evaluation and {finite_count}/20 BrainFusion features")

    # Patient-level crosswalk and features are kept under the protected data root.
    private_path = derived_root / "matched-clinical-radiomics.csv"
    with private_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(private_rows[0].keys()))
        writer.writeheader(); writer.writerows(private_rows)
    crosswalk_path = derived_root / "clinical-image-crosswalk.csv"
    with crosswalk_path.open("w", newline="", encoding="utf-8") as f:
        fields = ["clinical_id", "image_folder_id", "normalized_numeric_id", "join_rule", "brats21_id", "image_source_revision"]
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader()
        for case in cases:
            writer.writerow({"clinical_id": case["clinical_id"], "image_folder_id": case["patient_id"],
                             "normalized_numeric_id": case["normalized_numeric_id"],
                             "join_rule": "parse numeric suffix after UCSF-PDGM-; baseline only; format to four digits for image folder",
                             "brats21_id": "", "image_source_revision": manifest["revision"]})
    (out / "qc" / "space-and-input-hashes.json").parent.mkdir(parents=True, exist_ok=True)
    (out / "qc" / "space-and-input-hashes.json").write_text(json.dumps(qc_rows, indent=2), encoding="utf-8")
    regions = ["WT", "TC", "ET"]
    (out / "segmentation" / "case-metrics.json").parent.mkdir(parents=True, exist_ok=True)
    (out / "segmentation" / "case-metrics.json").write_text(json.dumps(segmentation_rows, indent=2), encoding="utf-8")
    metric_fields = ["patient_id"] + [f"{region}_{metric}" for region in regions for metric in
                      ("dice", "hd95_mm", "precision", "recall", "tp_voxels", "fp_voxels", "fn_voxels",
                       "prediction_ml", "reference_ml", "volume_delta_ml")]
    with (out / "segmentation" / "case-metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=metric_fields); writer.writeheader()
        for row in segmentation_rows:
            output_row = {"patient_id": row["patient_id"]}
            for region in regions:
                m = row["metrics"]["regions"][region]
                output_row.update({
                    f"{region}_dice": m["dice"], f"{region}_hd95_mm": m["hd95_mm"],
                    f"{region}_precision": m["precision"], f"{region}_recall": m["recall"],
                    f"{region}_tp_voxels": m["true_positive_voxels"],
                    f"{region}_fp_voxels": m["false_positive_voxels"],
                    f"{region}_fn_voxels": m["false_negative_voxels"],
                    f"{region}_prediction_ml": row["metrics"]["volumes_ml"][region],
                    f"{region}_reference_ml": row["metrics"]["reference_volumes_ml"][region],
                    f"{region}_volume_delta_ml": round(row["metrics"]["volumes_ml"][region]
                                                        - row["metrics"]["reference_volumes_ml"][region], 4),
                })
            writer.writerow(output_row)

    aggregate = {}
    for region in regions:
        vals = [row["metrics"]["regions"][region]["dice"] for row in segmentation_rows]
        hd95 = [row["metrics"]["regions"][region]["hd95_mm"] for row in segmentation_rows
                if row["metrics"]["regions"][region]["hd95_mm"] is not None]
        aggregate[region] = {"dice_mean": float(np.mean(vals)), "dice_sd": float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0,
                             "dice_median": float(np.median(vals)), "dice_range": [float(np.min(vals)), float(np.max(vals))],
                             "hd95_mm_mean": float(np.mean(hd95)) if hd95 else None,
                             "hd95_mm_median": float(np.median(hd95)) if hd95 else None,
                             "n_hd95_available": len(hd95)}
    n_events = sum(int(r["event_1_dead_0_alive"]) for r in private_rows)
    comparison = {
        "clinical_age_sex_baseline": "NOT_REEVALUATED: selected pilot IDs are part of the full UCSF development cohort and no valid held-out split was predeclared for this 10-case acquisition pilot",
        "radiomics_only_cox": "NOT_FIT: event-stratified pilot n=10, 20 features, insufficient for meaningful patient-level validation",
        "clinical_plus_radiomics_cox": "NOT_FIT: event-stratified pilot n=10, 20 features, insufficient for meaningful patient-level validation",
        "rsf": "NOT_RUN: no compatible sksurv dependency; cohort is also too small",
        "relative_fusion_gain": "NOT_ESTIMATED",
    }
    result = {
        "status": "PILOT_DATA_FLOW_COMPLETE_SURVIVAL_MODELING_NOT_ESTIMABLE",
        "dataset": "UCSF-PDGM v5 via MedOtter derived BraTS-format subset",
        "subset_revision": manifest["revision"], "subset_manifest_sha256": file_digest(data_root / "subset-manifest.json"),
        "official_metadata_sha256": file_digest(metadata_csv),
        "model": {"name": "MONAI BraTS MRI SegResNet", "source_revision": checkpoint_source.get("sha"),
                  "checkpoint_sha256": checkpoint_hash, "training_data_source": metadata.get("data_source"),
                  "reported_training_volumes": 285, "reported_split": {"train": 200, "validation": 42, "test": 43},
                  "training_case_manifest_available": False, "training_overlap_with_ucsf": "UNKNOWN"},
        "cohort": {"n": len(private_rows), "events_in_pilot": n_events, "censored_in_pilot": len(private_rows) - n_events,
                   "selection": manifest["selection"], "baseline_only": True,
                   "selected_all_without_bratS21_mapping": all(not r["brats21_id"] for r in private_rows),
                   "event_stratified_sample_not_population_representative": True,
                   "same_patient_join": "official metadata normalized numeric ID equals four-digit HF case folder ID"},
        "segmentation": {"status": "PUBLIC_REFERENCE_AGREEMENT", "metrics": aggregate,
                         "regions": {"WT": "pred labels 1/2/3; reference labels 1/2/4", "TC": "pred 1/3; reference 1/4", "ET": "pred 3; reference 4"},
                         "label_conversion_for_existing_evaluator": "reference 0/1/2/4 -> 0/1/2/3; 4->3; original reference files unchanged",
                         "case_level_path": str(out / "segmentation" / "case-metrics.json"),
                         "overlays": str(out / "overlays"),
                         "independent_external_validation": False,
                         "limitation": "Checkpoint is the public BraTS2018 MONAI model; exact training-case list is unavailable, so UCSF overlap cannot be excluded."},
        "radiomics": {"status": "MATCHED_FEATURE_EXTRACTION_COMPLETE", "n": len(private_rows),
                      "contract": "existing selected20 WAW-derived BrainFusion feature panel, reused unchanged",
                      "contract_sha256": feature_contract_sha, "finite_features_per_case": case_rows,
                      "private_crosswalk": str(crosswalk_path), "private_matched_feature_table": str(private_path),
                      "limitations": ["The panel is selected from a separate WAW IDH task and is not retrained or selected on UCSF survival.",
                                      "Only ten deliberately event-stratified cases were downloaded; this is a pipeline pilot, not a survival cohort."]},
        "survival_model_comparison": comparison,
        "software": {"segmentation_inference": "existing pinned BrainFusion wrapper; inference run once per selected UCSF case",
                     "radiomics_worker": str(worker), "radiomics_worker_sha256": file_digest(worker.parent / "source.json"),
                     "radiomics_protocol": PROTOCOL, "radiomics_contract_sha256": feature_contract_sha,
                     "existing_bundle_sha256": file_digest(bundle_path), "prediction_persistence": "none"},
        "source": "https://huggingface.co/datasets/MedOtter/UCSF-PDGM/tree/" + manifest["revision"],
    }
    (out / "PILOT-RESULTS.json").write_text(
        json.dumps(json_native(result), indent=2, allow_nan=False), encoding="utf-8")
    (out / "SHA256SUMS.txt").write_text("\n".join(
        f"{file_digest(path)}  {path.relative_to(out).as_posix()}"
        for path in sorted(out.rglob("*")) if path.is_file() and path.name != "SHA256SUMS.txt") + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "n": len(private_rows), "events": n_events,
                      "censored": len(private_rows) - n_events, "feature_complete_n": sum(feature_complete),
                      "segmentation_means": aggregate, "comparison": comparison}, indent=2))


if __name__ == "__main__":
    main()
