"""Extract the pinned BrainFusion-20 panel from UCSF v5 reference masks.

All patient-level outputs stay beneath the protected E: data directory. The
script is resumable, checks the pinned LFS hashes, and never runs segmentation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import nibabel as nib
import numpy as np

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.research.feature_contract import PROTOCOL, contract_hash, selected_features

PILOT_ROOT = Path("E:/BrainFusion-Data/UCSF-PDGM/research-v2/MedOtter-UCSF-PDGM-e9372219")
PILOT_DERIVED = "ucsf-pdgm-fusion-pilot-20261027-v1"
RADIOMICS_DIR = Path("E:/BrainFusion-Runtime/results/research")
DEFAULT_WORKER = Path("E:/BrainFusion-Runtime/envs/radiomics311-delivery-20261010T081105_95f1c109-independent/python.exe")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, allow_nan=False), encoding="utf-8")
    os.replace(tmp, path)


def load_contract() -> tuple[list[str], str, str]:
    pointer = json.loads((RADIOMICS_DIR / "latest.json").read_text(encoding="utf-8"))
    run = RADIOMICS_DIR / pointer["run_id"]
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    bundle_path = run / "models.joblib"
    if digest(bundle_path) != summary["artifact_sha256"]["models.joblib"]:
        raise ValueError("Radiomics contract bundle hash mismatch")
    import joblib
    bundle = joblib.load(bundle_path)
    features = selected_features(bundle)
    c_hash = contract_hash(bundle)
    if len(features) != 20 or len(set(features)) != 20:
        raise ValueError("Expected the existing fixed 20-feature panel")
    return features, c_hash, digest(bundle_path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--worker", type=Path, default=DEFAULT_WORKER)
    ap.add_argument("--max-cases", type=int, default=0, help="process at most this many pending cases; 0 means all available")
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()
    root = args.data_root.resolve(strict=True)
    progress_path = root / "download-progress.json"
    inventory_path = root / "cohort-file-inventory.json"
    cohort_path = root / "eligible-cohort-private.csv"
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    if progress.get("revision") != inventory.get("revision") or inventory["revision"] != "e9372219cf1cd2fdd52260cd45f7514b4aa7638e":
        raise ValueError("Download and inventory revisions differ or are not the approved pin")
    worker = args.worker.resolve(strict=True)
    features, c_hash, bundle_hash = load_contract()
    pilot_csv = PILOT_ROOT / "derived" / PILOT_DERIVED / "matched-clinical-radiomics.csv"
    pilot_features, pilot_qc = {}, {}
    if pilot_csv.is_file():
        with pilot_csv.open("r", encoding="utf-8-sig", newline="") as f:
            pilot_features = {r["patient_id"]: r for r in csv.DictReader(f)}
        qc_path = Path("E:/BrainFusion-Runtime/research-edition/results") / PILOT_DERIVED / "qc" / "space-and-input-hashes.json"
        if qc_path.is_file():
            pilot_qc = {r["patient_id"]: r for r in json.loads(qc_path.read_text(encoding="utf-8"))}
    derived = root / "derived" / "reference-radiomics-selected20-v1"
    case_out = derived / "cases"
    case_out.mkdir(parents=True, exist_ok=True)

    with cohort_path.open("r", encoding="utf-8-sig", newline="") as f:
        cohort_rows = {row["patient_id"]: row for row in csv.DictReader(f)}
    records = progress.get("case_records", {})
    available = sorted(set(records) & set(inventory["case_files"]))
    pending = [p for p in available if not (case_out / f"{p}-private.json").is_file()]
    if args.max_cases:
        pending = pending[:args.max_cases]
    success, failed = 0, []
    for patient in pending:
        row = cohort_rows[patient]
        rec = records[patient]
        file_map = {Path(x["path"]).name: x for x in rec["files"]}
        folder = Path(rec["directory"])
        if rec["kind"] == "reused_verified_prior_pilot":
            folder = PILOT_ROOT / "cases" / patient
        files = {}
        for suffix in ("T1.nii.gz", "T1c.nii.gz", "T2.nii.gz", "FLAIR.nii.gz", "tumor_segmentation.nii.gz"):
            expected_name = f"{patient}_{suffix}"
            item = file_map.get(expected_name)
            if not item:
                raise ValueError(f"Manifest file missing for {patient}: {expected_name}")
            path = Path(item.get("local_path") or (folder / expected_name)).resolve(strict=True)
            if path.stat().st_size != int(item["size"]) or digest(path) != item["sha256"]:
                raise ValueError(f"Pinned file hash mismatch; refusing extraction: {path}")
            files[suffix] = path

        seq = {"t1n": files["T1.nii.gz"], "t1c": files["T1c.nii.gz"],
               "t2w": files["T2.nii.gz"], "t2f": files["FLAIR.nii.gz"]}
        mask_path = files["tumor_segmentation.nii.gz"]
        # Check all image affine/shape contracts and official 0/1/2/4 labels.
        imgs = {k: nib.load(str(v), mmap=True) for k, v in seq.items()}
        ref = nib.load(str(mask_path), mmap=True)
        base = imgs["t1c"]
        geometries = {}
        for key, image in imgs.items():
            if image.shape != base.shape or not np.allclose(image.affine, base.affine, atol=1e-4, rtol=0):
                raise ValueError(f"MRI geometry mismatch in {patient}: {key}")
            geometries[key] = {"shape": list(image.shape), "affine": image.affine.round(6).tolist(),
                               "spacing_mm": [float(x) for x in image.header.get_zooms()[:3]]}
        raw_mask = np.asarray(ref.dataobj)
        if ref.shape != base.shape or not np.allclose(ref.affine, base.affine, atol=1e-4, rtol=0):
            raise ValueError(f"Reference mask geometry mismatch in {patient}")
        labels, counts = np.unique(raw_mask, return_counts=True)
        if not set(int(x) for x in labels).issubset({0, 1, 2, 4}):
            raise ValueError(f"Unexpected official reference labels for {patient}: {labels.tolist()}")
        recoded = np.zeros(raw_mask.shape, dtype=np.uint8)
        recoded[raw_mask == 1] = 1
        recoded[raw_mask == 2] = 2
        recoded[raw_mask == 4] = 3
        recoded_path = case_out / f"{patient}-reference-bf-1-2-3.nii.gz"
        if not recoded_path.exists():
            out_img = nib.Nifti1Image(recoded, ref.affine, header=ref.header.copy())
            out_img.set_qform(ref.get_qform(), int(ref.header["qform_code"]))
            out_img.set_sform(ref.get_sform(), int(ref.header["sform_code"]))
            nib.save(out_img, str(recoded_path))
        else:
            old = nib.load(str(recoded_path), mmap=True)
            if old.shape != ref.shape or not np.allclose(old.affine, ref.affine, atol=1e-4, rtol=0) or not np.array_equal(np.asarray(old.dataobj), recoded):
                raise ValueError(f"Existing derived recode differs; refusing overwrite: {recoded_path}")
        output_path = case_out / f"{patient}-features.json"
        reused = patient in pilot_features
        if reused:
            prior_row, qc = pilot_features[patient], pilot_qc.get(patient)
            expected_inputs = {k: file_map[Path(v).name]["sha256"] for k, v in seq.items()}
            if (prior_row.get("features_contract_sha256") != c_hash or not qc
                    or prior_row.get("feature_source_mask_sha256") != digest(mask_path)
                    or qc.get("reference_sha256") != digest(mask_path)
                    or qc.get("image_sha256") != expected_inputs):
                raise ValueError(f"Existing pilot feature provenance does not match pinned case files: {patient}")
            vals = {key: (float(prior_row[key]) if prior_row.get(key) not in ("", "None", "nan") else None) for key in features}
            if not all(v is not None and math.isfinite(v) for v in vals.values()):
                raise ValueError(f"Existing pilot feature vector is incomplete: {patient}")
            finite, extracted = 20, {"versions": {"source": "verified completed UCSF pilot"}, "seconds": None}
            extractor_status = "reused_existing_pilot_verified"
        else:
            request_path = case_out / f"{patient}-request.json"
            request = {"sequences": {k: str(v) for k, v in seq.items()}, "mask_path": str(recoded_path),
                       "selected_features": features, "protocol": PROTOCOL, "contract_sha256": c_hash,
                       "feature_source": "UCSF-PDGM pinned v5 BraTS-format reference mask, official 0/1/2/4 recoded to BrainFusion 0/1/2/3; fixed WAW-derived selected-20 panel; exploratory only"}
            atomic_json(request_path, request)
            try:
                subprocess.run([str(worker), "-B", str(BACKEND / "tools" / "extract_selected_radiomics.py"),
                                "--request", str(request_path), "--output", str(output_path)],
                               cwd=str(BACKEND), timeout=args.timeout, check=True, capture_output=True, text=True)
                extracted = json.loads(output_path.read_text(encoding="utf-8"))
                vals = extracted.get("features", {})
                if extracted.get("status") != "succeeded" or set(vals) != set(features):
                    raise ValueError("Radiomics worker returned incompatible feature schema")
                finite = sum(v is not None and math.isfinite(float(v)) for v in vals.values())
                extractor_status = "succeeded"
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError, json.JSONDecodeError) as exc:
                failed.append({"case_token": hashlib.sha256(patient.encode()).hexdigest(), "reason": f"{type(exc).__name__}: {str(exc)[:500]}"})
                print(f"Feature extraction failed for one case: {type(exc).__name__}", flush=True)
                continue
        private = {"patient_id": patient, "clinical_id": row["clinical_id"], "age_at_mri_years": float(row["age_at_mri"]),
                   "sex": row["sex"], "os_days": int(row["os_days"]), "event": int(row["event"]),
                   "brats21_id": row["brats21_id"], **vals,
                   "input_sha256": {k: item["sha256"] for k, item in ((k, file_map[Path(v).name]) for k, v in seq.items())},
                   "reference_mask_sha256": digest(mask_path), "recoded_mask_sha256": digest(recoded_path),
                   "feature_contract_sha256": c_hash, "extractor_status": extractor_status, "finite_features": finite,
                   "feature_count": len(features), "geometry": geometries, "reference_label_counts": {str(int(k)): int(v) for k, v in zip(labels, counts)},
                   "radiomics_versions": extracted.get("versions"), "radiomics_seconds": extracted.get("seconds")}
        atomic_json(output_path.with_name(f"{patient}-private.json"), private)
        success += 1
        print(f"Reference features ready: {patient} ({finite}/20 finite; {'reused pilot' if reused else 'extracted'})", flush=True)

    # Assemble a private patient-level CSV locally; only aggregate metadata is emitted to Runtime.
    all_records = []
    for path in sorted(case_out.glob("UCSF-PDGM-*-private.json")):
        obj = json.loads(path.read_text(encoding="utf-8"))
        if obj.get("feature_contract_sha256") != c_hash:
            raise ValueError(f"Stored feature contract mismatch: {path.name}")
        all_records.append(obj)
    if all_records:
        fields = ["patient_id", "clinical_id", "age_at_mri_years", "sex", "os_days", "event", "brats21_id", *features,
                  "reference_mask_sha256", "recoded_mask_sha256", "feature_contract_sha256"]
        table = root / "reference-radiomics-selected20-private.csv"
        tmp = table.with_suffix(".csv.tmp")
        with tmp.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader()
            for obj in all_records:
                writer.writerow({k: obj.get(k) for k in fields})
        os.replace(tmp, table)
    counts = [int(obj["finite_features"]) for obj in all_records]
    column_coverage = {}
    for name in features:
        values = [float(obj[name]) for obj in all_records if obj.get(name) is not None and math.isfinite(float(obj[name]))]
        column_coverage[name] = {"finite_n": len(values), "missing_n": len(all_records) - len(values),
                                 "finite_fraction": len(values) / len(all_records) if all_records else None,
                                 "median": float(np.median(values)) if values else None}
    geometry_signatures = sorted({json.dumps({k: v["shape"] for k, v in obj["geometry"].items()}, sort_keys=True)
                                  for obj in all_records})
    runtime = Path("E:/BrainFusion-Runtime/research-edition/results/ucsf-pdgm-reference-radiomics-v2-20261027")
    runtime.mkdir(parents=True, exist_ok=True)
    source_manifest = {"dataset": "MedOtter/UCSF-PDGM", "revision": inventory["revision"], "license": inventory["license"],
                       "eligible_cohort": inventory["cohort"], "mirror_inventory_sha256": digest(inventory_path),
                       "mirror_available_patients": inventory["mirror_availability"]["all_files_metadata_and_lfs_sha_verified"],
                       "mirror_expected_transfer_bytes": inventory["mirror_availability"]["expected_transfer_bytes"],
                       "braTS21_mapped_patients_in_eligible_v5_cohort": inventory["cohort"]["braTS21_mapped"],
                       "feature_contract_sha256": c_hash, "feature_bundle_sha256": bundle_hash,
                       "fixed_feature_count": len(features), "feature_source": "WAW IDH-derived selected-20 fixed panel, reused without outcome-based selection",
                       "feature_semantics": "labels 2 and 3 in the recoded reference mask; no segmentation inference",
                       "extraction_protocol": PROTOCOL, "per_feature_coverage": column_coverage,
                       "geometry_signature_count": len(geometry_signatures),
                       "all_four_sequences_and_reference_geometry_checked": True,
                       "available_downloaded_cases": len(available), "extracted_cases": len(all_records),
                       "feature_complete_cases": sum(n == 20 for n in counts), "feature_value_completeness": sum(counts) / (20 * len(counts)) if counts else None,
                       "case_failures_this_run": failed, "patient_level_table_sha256": digest(root / "reference-radiomics-selected20-private.csv") if all_records else None,
                       "privacy": "Patient-level table and per-case hashes remain in protected data directory; runtime summary contains aggregates only.",
                       "limitations": ["Exploratory fixed feature panel derived in separate WAW IDH task; not selected/validated for UCSF survival.",
                                       "Endpoint and population come from TCIA v5, with OS from initial diagnosis; diagnosis-to-MRI interval is not recorded.",
                                       "BraTS overlap and SegResNet training overlap are tracked separately; these are reference-mask features, not automatic-prediction features."]}
    atomic_json(runtime / "reference-radiomics-summary.json", source_manifest)
    print(json.dumps({"extracted_this_run": success, "available_downloaded_cases": len(available),
                      "feature_rows": len(all_records), "complete_rows": source_manifest["feature_complete_cases"],
                      "failures": len(failed), "csv_sha256_private": source_manifest["patient_level_table_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
