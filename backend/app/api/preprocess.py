from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.mri import MRI
from app.services.feature_service import save_mri_feature
from app.services.preprocess_service import preprocess_mri
from app.core.storage import resolve_stored_path


router = APIRouter()


@router.post("/preprocess/{case_id}")
def preprocess(case_id: int, db: Session = Depends(get_db)):
    mri = db.query(MRI).filter(MRI.case_id == case_id).order_by(MRI.id.desc()).first()
    if mri is None:
        raise HTTPException(status_code=404, detail="MRI not found")

    source = resolve_stored_path(mri.filepath)
    if not source.is_file():
        raise HTTPException(status_code=404, detail="MRI file is missing")

    result = preprocess_mri(str(source))
    mri.processed_path = result["processed_path"]
    mri.status = "processed"
    feature_id = save_mri_feature(mri.id, result)
    db.commit()

    return {
        "code": 200,
        "message": "预处理完成",
        "data": {
            "case_id": case_id,
            "mri_id": mri.id,
            "feature_id": feature_id,
            "processed_path": mri.processed_path,
            "preprocess": result,
        },
    }
