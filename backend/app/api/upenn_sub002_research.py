"""Read-only manifest and files for the existing UPENN sub-002 research run.

The API is disabled unless all three isolated research directories are supplied.
It has no patient/case database writes and accepts no user-provided file paths.
"""
import hashlib
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.core.config import settings
from app.services.local_auth import require_doctor

router = APIRouter(prefix="/api/research/upenn-sub002", tags=["research-upenn-sub002"])

EXPECTED_INPUTS = {
    "t1c": ("sub-002_ce-gd_T1w.nii.gz", "23fa90d5f6024e3bc2e95ef47b3150a17d6c9036a8fd982121913191442fee67"),
    "t1n": ("sub-002_T1w.nii.gz", "7888caf8394d7e9dbd12862023c686af8214b7f0a15fcc519297cbe8de40aca3"),
    "t2w": ("sub-002_T2w.nii.gz", "3af54de46e2b50fc9b54893841144438b191f572b641976ae2cfb56b16346c0e"),
    "t2f": ("sub-002_FLAIR.nii.gz", "7eec5ca79f758cb99f594004737b85646bb942b40c9afae108d986188736df3c"),
}
PREDICTION_SHA = "a2e90567d49653a2966c2f8e4dfbcfdbbd91a1550ccd7c9ed43bee60a6ee9cfd"
METRICS_SHA = "9469df44977d1ff6171d9d14ac3ac1faf782f6d708e95dae81ec10b0c0fd93d9"
METRICS_CSV_SHA = "a3c60c83d8f047666ca6a02312fcd2e4d0f83ccd00781e35f28d322cd4d45504"
OVERLAY_SHA = "c331b9b485b4d59e96e0844a2b0b56e0348a0610c15692f6055320da5fe5a7e0"
RUN_EVIDENCE = "run-evidence.json"
RUN_EVIDENCE_SHA = "761108c2fd6492b16daf679cc317bb01bb0fc30ce731a8843ca6d6616e072755"
SPATIAL_QC_SHA = "9292dbc269a5e5a32599035164244c4a15501ed4a39b7d596cbc28b147be883e"
RUN_OVERLAY_SHA = "2a77786282e04bca00f19051c26b4cec0979d5632e03e8d7c1299ead571643d8"


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _roots() -> tuple[Path, Path, Path]:
    values = (settings.UPENN_SUB002_INPUT_DIR, settings.UPENN_SUB002_RESULT_DIR,
              settings.UPENN_SUB002_EVIDENCE_DIR)
    if not all(str(value).strip() for value in values):
        raise HTTPException(404, "UPENN sub-002 research viewer is not enabled in this runtime.")
    try:
        roots = tuple(Path(value).resolve(strict=True) for value in values)
    except OSError as error:
        raise HTTPException(503, "Configured UPENN research evidence is unavailable.") from error
    if not all(root.is_dir() for root in roots):
        raise HTTPException(503, "Configured UPENN research evidence is unavailable.")
    return roots  # type: ignore[return-value]


def _file(root: Path, name: str, expected: str) -> Path:
    path = (root / name).resolve(strict=True)
    if path.parent != root or not path.is_file() or _sha(path) != expected:
        raise HTTPException(409, f"Pinned research file integrity check failed: {name}.")
    return path


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HTTPException(409, "Pinned research evidence JSON is unreadable.") from error
    if not isinstance(value, dict):
        raise HTTPException(409, "Pinned research evidence JSON has an invalid shape.")
    return value


def _verified_files():
    input_root, result_root, evidence_root = _roots()
    run = _load_json(_file(result_root, RUN_EVIDENCE, RUN_EVIDENCE_SHA))
    if run.get("mask_sha256") != PREDICTION_SHA or run.get("input_sha256") != {k: v[1] for k, v in EXPECTED_INPUTS.items()}:
        raise HTTPException(409, "The existing inference manifest does not match the pinned input/output set.")
    files = {key: _file(input_root, filename, sha) for key, (filename, sha) in EXPECTED_INPUTS.items()}
    files["prediction"] = _file(result_root, "prediction.nii.gz", PREDICTION_SHA)
    files["overlay"] = _file(result_root, "tri-planar-overlay.png", RUN_OVERLAY_SHA)
    files["metrics"] = _file(evidence_root, "segmentation-metrics.json", METRICS_SHA)
    files["metrics_csv"] = _file(evidence_root, "segmentation-metrics.csv", METRICS_CSV_SHA)
    files["review_overlay"] = _file(evidence_root, "segmentation-overlay-review.png", OVERLAY_SHA)
    return run, files


@router.get("/manifest")
def manifest(identity: dict = Depends(require_doctor)):
    run, files = _verified_files()
    metrics = _load_json(files["metrics"])
    spatial = _load_json(_file(Path(settings.UPENN_SUB002_RESULT_DIR).resolve(), "spatial-qc.json", SPATIAL_QC_SHA))
    if spatial.get("status") != "PASS" or spatial.get("shape_match") is not True or spatial.get("affine_match") is not True:
        raise HTTPException(409, "Saved spatial quality evidence did not pass.")
    region_metrics = metrics.get("metrics")
    if not isinstance(region_metrics, dict) or set(region_metrics) != {"WT", "TC", "ET"}:
        raise HTTPException(409, "Saved public-reference metrics are incomplete.")
    file_urls = {key: f"/api/research/upenn-sub002/files/{key}" for key in files}
    import nibabel as nib
    import numpy as np
    sequence_info = {}
    reference_shape = None
    reference_affine = None
    reviewed_spacing = spatial.get("spacing_mm")
    reviewed_units_contract = (
        run.get("input_space_checked") == "all four MRI inputs share shape/affine; 1mm LPS; official source hashes verified"
        and run.get("inference_contract_review", {}).get("input_spacing_mm") == [1, 1, 1]
        and isinstance(reviewed_spacing, list) and len(reviewed_spacing) == 3
        and all(isinstance(value, (int, float)) and abs(float(value) - 1.0) < 1e-4 for value in reviewed_spacing)
    )
    for key in EXPECTED_INPUTS:
        image = nib.load(str(files[key]))
        values = np.asarray(image.dataobj, dtype=np.float32)
        finite = values[np.isfinite(values)]
        spatial_unit = image.header.get_xyzt_units()[0]
        affine_spacing = nib.affines.voxel_sizes(image.affine)
        if (image.ndim != 3 or not finite.size or not np.all(np.isfinite(image.affine))
                or (spatial_unit != "mm" and not (spatial_unit == "unknown" and reviewed_units_contract))
                or not np.allclose(affine_spacing, reviewed_spacing, atol=1e-4, rtol=0)):
            raise HTTPException(409, "A pinned input NIfTI has invalid volume or geometry metadata.")
        if reference_shape is None:
            reference_shape, reference_affine = image.shape, image.affine.copy()
        elif image.shape != reference_shape or not np.allclose(image.affine, reference_affine, atol=1e-4, rtol=0):
            raise HTTPException(409, "The pinned UPENN four-sequence images do not share the reviewed physical grid.")
        sequence_info[key] = {"sequence": key, "nifti_url": file_urls[key], "source_revision": EXPECTED_INPUTS[key][1],
                              "display_min": float(np.percentile(finite, 1)),
                              "display_max": float(np.percentile(finite, 99.5))}
    prediction_image = nib.load(str(files["prediction"]))
    if prediction_image.shape != reference_shape or not np.allclose(prediction_image.affine, reference_affine, atol=1e-4, rtol=0):
        raise HTTPException(409, "The pinned prediction mask does not share the reviewed four-sequence physical grid.")
    return {"code": 200, "data": {
        "study_id": "UPENN-GBM-sub-002", "case_link_status": "UNLINKED_RESEARCH_CASE",
        "source_scope": "UPENN-GBM official NIfTI research copy; not linked to DICOM study by numeric similarity",
        "inference": {"model": run.get("model"), "revision": run.get("revision"),
                      "checkpoint_sha256": run.get("checkpoint_sha256"), "prediction_sha256": run.get("mask_sha256"),
                      "device": run.get("device"), "purpose": run.get("purpose"), "reference_mask_used_for_inference": False},
        "inputs": [{"sequence": key, "sha256": EXPECTED_INPUTS[key][1], "url": file_urls[key]}
                   for key in EXPECTED_INPUTS],
        "sequences": sequence_info, "available_sequences": list(EXPECTED_INPUTS),
        "prediction": {"url": file_urls["prediction"], "sha256": PREDICTION_SHA,
                       "volumes_ml": {key: run.get("volumes", {}).get(key, {}).get("ml") for key in ("WT", "TC", "ET")}},
        "spatial_qc": {key: spatial.get(key) for key in ("status", "prediction_shape", "shape_match", "affine_match", "spacing_mm", "orientation")},
        "geometry": {"shape": list(reference_shape), "spacing_mm": list(map(float, reviewed_spacing)),
                     "spatial_unit_source": "header_mm" if nib.load(str(files["t1c"])).header.get_xyzt_units()[0] == "mm" else "pinned_source_and_inference_spatial_qc",
                     "orientation": list(nib.aff2axcodes(reference_affine))},
        "reference_agreement": {"status": "PUBLIC_REFERENCE_AGREEMENT", "scope": metrics.get("claim_scope"),
                                "training_overlap_status": metrics.get("training_overlap_status"),
                                "expert_review_status": metrics.get("expert_review_status"),
                                "reference_sha256": metrics.get("files", {}).get("official_local_reference", {}).get("sha256"),
                                "mirror_revision": metrics.get("reference_source", {}).get("revision"),
                                "regions": region_metrics, "csv_url": file_urls["metrics_csv"]},
        "overlay_url": file_urls["review_overlay"], "run_overlay_url": file_urls["overlay"],
        "limitations": ["单病例公开参考一致性，不是独立外部验证。", "checkpoint 训练病例重叠未知。",
                        "未建立 UPENN DICOM 与 sub-002 的患者映射。"],
    }}


@router.get("/files/{file_key}")
def research_file(file_key: str, identity: dict = Depends(require_doctor)):
    _, files = _verified_files()
    if file_key not in files:
        raise HTTPException(404, "Research file key is not available.")
    path = files[file_key]
    media_type = "image/png" if file_key in {"overlay", "review_overlay"} else "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=path.name, content_disposition_type="inline",
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
