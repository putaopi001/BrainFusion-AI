import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.mri import MRI
from app.services.current_report import current_model_report
router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/{case_id}")
def get_report(case_id: int, db: Session = Depends(get_db)):
    mri = db.query(MRI).filter(MRI.case_id == case_id).order_by(MRI.id.desc()).first()
    report = current_model_report(mri, db)
    if not report:
        raise HTTPException(404, "No successful report for the current run")
    return {"code": 200, "data": {"id": report.id, "analysis_run_id": report.analysis_run_id,
        "summary": json.loads(report.summary), "recommendation": json.loads(report.recommendation)}}

@router.post("/generate/{case_id}")
def create_report(case_id: int, db: Session = Depends(get_db)):
    return get_report(case_id, db)
