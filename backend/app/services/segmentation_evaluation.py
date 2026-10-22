"""Controlled evaluation of a current model mask against a supplied reference label."""
import hashlib
import json
import os
import re
import threading
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path

import nibabel as nib
import numpy as np
from nibabel.filebasedimages import ImageFileError

from app.core.storage import upload_root
from app.services.artifact_integrity import analysis_problem, checked_digest
from app.services.segmentation_metrics import evaluate, validate_mask

PROTOCOL = "brainfusion-segmentation-eval-v1"
MAX_REFERENCE_BYTES = 512 * 1024**2
_evaluation_lock = threading.Lock()


def _within(path: Path, root: Path) -> Path:
    resolved, base = path.resolve(strict=True), root.resolve(strict=True)
    try:
        resolved.relative_to(base)
    except ValueError:
        raise ValueError("Evaluation artifacts must be stored under the configured upload runtime") from None
    if not resolved.is_file():
        raise ValueError("Evaluation artifact must be a regular file")
    return resolved


def current_run_context(case_id, run_id, db):
    from app.models.analysis_run import AnalysisRun
    from app.models.mri import MRI

    run = db.get(AnalysisRun, run_id)
    if run is None or run.case_id != case_id:
        raise KeyError("analysis run not found for this case")
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", run.id):
        raise ValueError("Analysis run identifier is not eligible for an evaluation artifact path")
    mri = db.get(MRI, run.mri_id)
    if mri is None or mri.case_id != case_id or mri.analysis_run_id != run.id:
        raise ValueError("Analysis run is not the current run for this case MRI")
    problem = analysis_problem(mri, run)
    if problem:
        raise ValueError("Current analysis lineage is stale or invalid; a current successful analysis is required")
    result = json.loads(run.result_json or "{}")
    request = json.loads(run.request_json or "{}")
    sequences = request.get("sequences")
    if not isinstance(sequences, dict) or set(sequences) != {"t1c", "t1n", "t2w", "t2f"}:
        raise ValueError("Analysis run does not contain the required four-sequence input lineage")
    root = upload_root().resolve(strict=True)
    safe_sequences = {key: _within(Path(value), root) for key, value in sequences.items()}
    mask_path = _within(Path(result["mask_path"]), root)
    if Path(mri.segmentation_path).resolve(strict=True) != mask_path:
        raise ValueError("Prediction mask is no longer linked to this analysis run")
    input_sha256 = {key: checked_digest(path) for key, path in safe_sequences.items()}
    if result.get("input_sha256") != input_sha256:
        raise ValueError("MRI input files no longer match the saved analysis fingerprints")
    mask_sha256 = checked_digest(mask_path)
    if result.get("mask_sha256") != mask_sha256:
        raise ValueError("Prediction mask no longer matches the saved analysis fingerprint")
    reference_space = nib.load(str(safe_sequences["t1c"]), mmap=False)
    if len(reference_space.shape) != 3 or not np.isfinite(reference_space.affine).all() or abs(float(np.linalg.det(reference_space.affine[:3, :3]))) < 1e-8:
        raise ValueError("Analysis MRI must be a finite, invertible 3D physical space")
    predicted = nib.load(str(mask_path), mmap=False)
    for name, image in (("prediction", predicted),):
        if image.shape != reference_space.shape or not np.allclose(image.affine, reference_space.affine, atol=1e-4, rtol=0):
            raise ValueError(f"{name} mask does not match the analysis MRI physical space")
    # Ensure all four registered inputs share the reference grid before accepting a label.
    for key, path in safe_sequences.items():
        image = nib.load(str(path), mmap=False)
        if image.shape != reference_space.shape or not np.allclose(image.affine, reference_space.affine, atol=1e-4, rtol=0):
            raise ValueError(f"MRI sequence {key} does not share the analysis reference space")
    return {
        "run": run, "mri": mri, "result": result, "request": request,
        "sequences": safe_sequences, "mask_path": mask_path, "mask_sha256": mask_sha256,
        "input_sha256": input_sha256, "reference_space": reference_space,
        # Keep Windows paths short while retaining a stable, per-case/run namespace.
        "evaluation_dir": (root / "seg_eval" / f"{case_id}-{hashlib.sha256(run.id.encode()).hexdigest()[:12]}").resolve(),
    }


def _record_path(context, evaluation_id):
    root = upload_root().resolve(strict=True)
    directory = context["evaluation_dir"]
    try:
        directory.relative_to(root)
    except ValueError:
        raise ValueError("Evaluation artifact path escaped configured runtime") from None
    return directory / f"{evaluation_id[:24]}.json"


def load_latest(context):
    directory = context["evaluation_dir"]
    if not directory.is_dir():
        return None
    records = sorted(directory.glob("*.json"), key=lambda path: path.stat().st_mtime_ns, reverse=True)
    if not records:
        return None
    try:
        record = json.loads(records[0].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return record


def evaluate_uploaded_reference(context, source, filename, dataset_version, annotation_id,
                                authorization_receipt, reviewer):
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,159}", dataset_version.strip())
            or not annotation_id.strip() or not authorization_receipt.strip()):
        raise ValueError("Dataset version, annotation ID and authorization receipt are required")
    name = (filename or "").lower()
    suffix = ".nii.gz" if name.endswith(".nii.gz") else ".nii" if name.endswith(".nii") else ""
    if not suffix:
        raise ValueError("Reference annotation must be a NIfTI file")

    directory = context["evaluation_dir"]
    root = upload_root().resolve(strict=True)
    try:
        directory.resolve().relative_to(root)
    except ValueError:
        raise ValueError("Evaluation artifact path escaped configured runtime") from None
    directory.mkdir(parents=True, exist_ok=True)
    directory.resolve(strict=True).relative_to(root)
    temp_path = directory / (".reference-upload-" + uuid4().hex + suffix)
    retained = None
    retained_created = False
    digest = hashlib.sha256()
    size = 0
    try:
        with temp_path.open("xb") as handle:
            while block := source.read(1024 * 1024):
                size += len(block)
                if size > MAX_REFERENCE_BYTES:
                    raise ValueError("Reference annotation exceeds 512 MiB")
                digest.update(block)
                handle.write(block)
        if size == 0:
            raise ValueError("Reference annotation is empty")
        retained = directory / ("r-" + digest.hexdigest()[:20] + suffix)
        if retained.exists():
            temp_path.unlink()
        else:
            os.replace(temp_path, retained)
            retained_created = True
        reference_path = _within(retained, root)
        reference = nib.load(str(reference_path), mmap=False)
        labels = validate_mask(reference, context["reference_space"])
        if not np.isin(np.unique(labels), [0, 1, 2, 3]).all():
            raise ValueError("Reference annotation labels must use background 0 and tumor labels 1, 2, 3")
        metadata = {
            "protocol": PROTOCOL,
            "scope": "synthetic_engineering" if dataset_version.strip().upper().startswith("SYNTHETIC-") else "reference_label_authorization_asserted_unverified",
            "case_id": context["run"].case_id,
            "analysis_run_id": context["run"].id,
            "mri_id": context["mri"].id,
            "dataset_version": dataset_version.strip(),
            # Keep only a digest of the source reference token; it could be a sensitive UID.
            "annotation_ref": hashlib.sha256(annotation_id.strip().encode("utf-8")).hexdigest(),
            "authorization_receipt_sha256": hashlib.sha256(authorization_receipt.strip().encode("utf-8")).hexdigest(),
            "research_use_attested": True,
            "external_authorization_verified": False,
            "reviewer_role": reviewer.get("role"),
            "authentication_method": reviewer.get("authentication_method"),
            "professional_credential_verified": reviewer.get("professional_credential_verified", False),
            "model_version": context["result"].get("model"),
            "input_sha256": context["input_sha256"],
            "prediction_mask_sha256": context["mask_sha256"],
            "reference_mask_sha256": digest.hexdigest(),
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "units": {"hd95": "mm", "volumes": "mL", "counts": "voxels"},
        }
        identity = {key: value for key, value in metadata.items() if key not in {"evaluated_at"}}
        evaluation_id = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        record_path = _record_path(context, evaluation_id)
        existing = None
        with _evaluation_lock:
            if record_path.exists():
                existing = json.loads(record_path.read_text(encoding="utf-8"))
                if existing.get("evaluation_id") != evaluation_id:
                    raise ValueError("Evaluation artifact identifier collision; refusing to overwrite")
            else:
                result = evaluate(context["mask_path"], reference_path)
                metadata["evaluation_id"] = evaluation_id
                metadata["status"] = "PASS"
                metadata["regions"] = result["regions"]
                metadata["prediction_volumes_ml"] = result["volumes_ml"]
                metadata["reference_volumes_ml"] = result["reference_volumes_ml"]
                # The process lock plus exclusive create keeps retries idempotent;
                # no database row is created for an identical evaluation fingerprint.
                with record_path.open("x", encoding="utf-8") as handle:
                    json.dump(metadata, handle, ensure_ascii=False, sort_keys=True, indent=2)
                existing = metadata
        return existing
    except ImageFileError as error:
        if retained_created and retained:
            try:
                retained.unlink(missing_ok=True)
            except OSError:
                pass
        raise ValueError("Reference annotation is not a readable NIfTI image") from error
    except Exception:
        if retained_created and retained:
            try:
                retained.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    finally:
        temp_path.unlink(missing_ok=True)
