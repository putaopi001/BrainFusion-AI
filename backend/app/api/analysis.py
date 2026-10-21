import json
import shutil
from pathlib import Path
from uuid import uuid4
from nibabel.filebasedimages import ImageFileError

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.database import get_db
from app.models.analysis_run import AnalysisRun
from app.models.annotation import MRIAnnotation
from app.models.case import Case
from app.models.mri import MRI
from app.services.analysis_jobs import BACKEND, execute, executor, serialize, submission_lock
from app.services.mri_preview_service import generate_mri_previews
from app.services.study_validation import validate_sequences
from app.services.artifact_integrity import (
    current_analysis, analysis_problem, activated_conversion_input_hashes,
)
from app.core.storage import upload_root, public_upload_path

router = APIRouter(tags=["real-analysis"])
SEQUENCES = ("t1c", "t1n", "t2w", "t2f")


def prepare_study(paths, directory, case_id):
    validate_sequences(paths)
    return generate_mri_previews(Path(paths['t2f']), directory / 'previews', case_id)


def latest(case_id, db):
    mri = db.query(MRI).filter(MRI.case_id == case_id).order_by(MRI.id.desc()).first()
    if mri is None:
        raise HTTPException(404, "MRI not found")
    return mri


def ensure_idle(case_id, db):
    if db.query(AnalysisRun).filter(AnalysisRun.case_id == case_id, AnalysisRun.state.in_(["queued", "running"])).first():
        raise HTTPException(409, "An analysis is active; wait for it to finish")


@router.post("/studies/{case_id}")
async def upload_study(case_id: int, t1c: UploadFile = File(...), t1n: UploadFile = File(...),
                       t2w: UploadFile = File(...), t2f: UploadFile = File(...), db: Session = Depends(get_db)):
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(404, "case not found")
    ensure_idle(case_id, db)
    directory = upload_root() / f"case_{case_id}" / ("study_" + uuid4().hex)
    directory.mkdir(parents=True, exist_ok=True)
    files = {"t1c": t1c, "t1n": t1n, "t2w": t2w, "t2f": t2f}
    paths = {}
    try:
        for sequence, file in files.items():
            suffix = ".nii.gz" if (file.filename or "").lower().endswith(".nii.gz") else ".nii"
            if not (file.filename or "").lower().endswith((".nii", ".nii.gz")):
                raise HTTPException(415, "Four NIfTI sequences are required")
            destination = directory / (sequence + suffix)
            size = 0
            with destination.open("wb") as handle:
                while block := await file.read(1024 * 1024):
                    size += len(block)
                    if size > 512 * 1024**2:
                        raise HTTPException(413, "Sequence exceeds 512 MiB")
                    handle.write(block)
            paths[sequence] = str(destination)
        previews = await run_in_threadpool(prepare_study, paths, directory, case_id)
        with submission_lock:
            db.expire_all()
            ensure_idle(case_id, db)
            mri = db.query(MRI).filter(MRI.case_id == case_id).order_by(MRI.id.desc()).first()
            if mri is None:
                mri = MRI(case_id=case_id)
                db.add(mri)
                db.flush()
            elif mri.input_source == "dicom-conversion":
                # Keep the activated conversion row and its immutable source lineage as history.
                db.query(MRIAnnotation).filter(MRIAnnotation.mri_id == mri.id).update({"coordinate_contract": "obsolete-input"})
                mri = MRI(case_id=case_id)
                db.add(mri)
                db.flush()
            else:
                db.query(MRIAnnotation).filter(MRIAnnotation.mri_id == mri.id).update({"coordinate_contract": "obsolete-input"})
            mri.filepath, mri.web_path = paths["t2f"], public_upload_path(paths['t2f'])
            mri.input_source, mri.source_provenance_json = "nifti-upload", None
            mri.filename, mri.sequences_json = "Four-sequence MRI", json.dumps(paths)
            mri.segmentation_path = mri.analysis_run_id = mri.verified_run_id = None
            mri.doctor_verified, mri.segmentation_source = False, "unavailable"
            mri.slice_path = str(previews[0])
            mri.status, mri.preview_error = "preview_ready", None
            case.status, case.mri_path = "uploaded", mri.filepath
            db.commit()
            return {"code": 200, "data": {"mri_id": mri.id, "sequences": list(paths), "status": mri.status}}
    except Exception as error:
        db.rollback()
        # Only the newly created, resolved upload directory is removed.
        directory.resolve().relative_to(upload_root())
        shutil.rmtree(directory)
        if isinstance(error, HTTPException):
            raise
        raise HTTPException(422, str(error))
    finally:
        for file in files.values():
            await file.close()


@router.post("/analysis/{case_id}", status_code=202)
def start_analysis(case_id: int, db: Session = Depends(get_db)):
    with submission_lock:
        ensure_idle(case_id, db)
        mri = latest(case_id, db)
        if not mri.sequences_json:
            raise HTTPException(422, "Upload four aligned sequences before real analysis")
        try:
            sequences = json.loads(mri.sequences_json)
            validate_sequences(sequences)
        except (ValueError, TypeError, OSError, ImageFileError) as error:
            raise HTTPException(422, "Invalid or unavailable four-sequence MRI: " + str(error))
        expected_input_sha256 = None
        if mri.input_source == "dicom-conversion":
            try:
                expected_input_sha256 = activated_conversion_input_hashes(mri, sequences)
            except ValueError as error:
                raise HTTPException(409, str(error)) from None
        model_dir = Path(settings.MODEL_DIR)
        if not (model_dir / "models/model.pt").is_file():
            raise HTTPException(503, "Pretrained segmentation weights unavailable")
        run_id = uuid4().hex
        request = {"sequences": sequences, "output_dir": str(upload_root() / f"case_{case_id}" / run_id),
                   "model_dir": str(model_dir), "gpu_budget_mb": settings.GPU_BUDGET_MB}
        if expected_input_sha256 is not None:
            request["expected_input_sha256"] = expected_input_sha256
        run = AnalysisRun(id=run_id, case_id=case_id, mri_id=mri.id, request_json=json.dumps(request))
        mri.analysis_run_id, mri.doctor_verified, mri.verified_run_id = run_id, False, None
        mri.segmentation_path, mri.segmentation_source, mri.status = None, "unavailable", "processing"
        db.add(run)
        db.commit()
        executor.submit(execute, run_id)
        return {"code": 202, "data": serialize(run)}


@router.get("/analysis/{case_id}")
def get_analysis(case_id: int, db: Session = Depends(get_db)):
    mri = latest(case_id, db)
    run = db.get(AnalysisRun, mri.analysis_run_id) if mri.analysis_run_id else None
    return {"code": 200, "data": current_analysis(mri, run)}


@router.get("/analysis/{case_id}/history")
def history(case_id: int, db: Session = Depends(get_db)):
    mri = latest(case_id, db)
    return {"code": 200, "data": [{**serialize(run), 'current': run.id == mri.analysis_run_id and (run.state != 'succeeded' or not analysis_problem(mri, run))} for run in db.query(AnalysisRun).filter(AnalysisRun.case_id == case_id)
                                  .order_by(AnalysisRun.created_time.desc()).all()]}
