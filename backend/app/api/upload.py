from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.case import Case
from app.models.mri import MRI
from app.models.prediction import Prediction
from app.models.report import Report
from app.services.mri_preview_service import generate_mri_previews


router = APIRouter(prefix="", tags=["upload"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
BACKEND_DIR = UPLOAD_DIR.parent
ALLOWED_SUFFIXES = (".nii", ".nii.gz", ".dcm")
MAX_UPLOAD_SIZE = 2 * 1024 * 1024 * 1024


def is_allowed_mri(filename: str) -> bool:
    return filename.lower().endswith(ALLOWED_SUFFIXES)


@router.post("/upload/{case_id}")
async def upload_mri(
    case_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="case not found")

    original_filename = Path(file.filename or "").name
    if not original_filename or not is_allowed_mri(original_filename):
        raise HTTPException(
            status_code=415,
            detail="only .nii, .nii.gz, and .dcm MRI files are supported",
        )

    case_dir = UPLOAD_DIR / f"case_{case_id}"
    case_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid4().hex}_{original_filename}"
    destination = case_dir / stored_filename

    try:
        total_size = 0
        with destination.open("wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                total_size += len(chunk)
                if total_size > MAX_UPLOAD_SIZE:
                    raise HTTPException(status_code=413, detail="MRI file is too large")
                buffer.write(chunk)

        relative_path = destination.relative_to(UPLOAD_DIR).as_posix()
        web_path = f"/uploads/{relative_path}"
        mri = db.query(MRI).filter(MRI.case_id == case_id).first()

        if mri is None:
            mri = MRI(case_id=case_id)
            db.add(mri)
            db.flush()

        previous_path = mri.filepath
        mri.filename = original_filename
        storage_path = destination.relative_to(BACKEND_DIR).as_posix()
        mri.filepath = storage_path
        mri.web_path = web_path
        mri.slice_path = None
        mri.preview_error = None
        mri.modality = "MRI"
        mri.status = "processing"
        case.mri_path = storage_path
        case.status = "uploaded"

        preview_paths = []
        if original_filename.lower().endswith((".nii", ".nii.gz")):
            try:
                preview_paths = generate_mri_previews(destination, case_dir / "previews", mri.id)
                mri.slice_path = str(preview_paths[0])
                mri.status = "preview_ready"
            except Exception as error:
                mri.preview_error = f"{type(error).__name__}: {error}"
                mri.status = "failed"
        else:
            mri.preview_error = "DICOM preview is not supported for a single uploaded file."
            mri.status = "failed"

        db.query(Prediction).filter(Prediction.case_id == case_id).delete()
        db.query(Report).filter(Report.case_id == case_id).delete()

        db.commit()
        db.refresh(mri)
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    if previous_path and previous_path != str(destination):
        previous = Path(previous_path)
        if not previous.is_absolute():
            previous = BACKEND_DIR / previous
        try:
            previous.relative_to(UPLOAD_DIR)
        except ValueError:
            previous = None
        if previous:
            previous.unlink(missing_ok=True)

    return {
        "code": 200,
        "message": "MRI upload success",
        "data": {
            "mri_id": mri.id,
            "filename": mri.filename,
            "file_url": mri.web_path,
            "status": mri.status,
            "case_status": case.status,
            "preview_count": len(preview_paths),
            "preview_error": mri.preview_error,
        },
    }
