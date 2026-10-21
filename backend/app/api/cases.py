from pathlib import Path
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.case import Case
from app.models.mri import MRI
from app.models.patient import Patient
from app.models.prediction import Prediction
from app.models.report import Report
from app.models.doctor_opinion import DoctorOpinion
from app.schemas.case import CaseCreate
from app.schemas.doctor_opinion import DoctorOpinionUpdate
from app.services import mri_service
from app.services.current_report import current_model_report
from app.core.time import utc_iso
from app.core.storage import public_upload_path


router = APIRouter(prefix="/cases", tags=["cases"])


def source_lineage_summary(mri):
    if not mri:
        return None
    if mri.input_source != "dicom-conversion" or not mri.source_provenance_json:
        return {"input_source": mri.input_source or "legacy"}
    try:
        value = json.loads(mri.source_provenance_json)
        return {key: value.get(key) for key in ("format", "conversion_version_id", "plan_revision",
                "model_input_contract", "archive_id", "study_uid", "activated_utc", "inference_performed")}
    except (ValueError, TypeError):
        return {"input_source": "dicom-conversion", "integrity_status": "invalid"}


def preview_urls(slice_path: str | None) -> list[str]:
    if not slice_path:
        return []
    path = Path(slice_path)
    prefix = path.stem.rsplit("_", 1)[0]
    return [
        public_upload_path(str(item))
        for item in sorted(path.parent.glob(f"{prefix}_*.png"))
        if public_upload_path(str(item))
    ]


def preview_views(slice_path: str | None) -> dict[str, list[str]]:
    empty = {"axial": [], "coronal": [], "sagittal": []}
    if not slice_path:
        return empty
    path = Path(slice_path)
    parts = path.stem.split("_")
    if len(parts) < 4:
        empty["axial"] = preview_urls(slice_path)
        return empty
    prefix = "_".join(parts[:2])
    return {
        view: [
            public_upload_path(str(item))
            for item in sorted(path.parent.glob(f"{prefix}_{view}_*.png"))
            if public_upload_path(str(item))
        ]
        for view in ("axial", "coronal", "sagittal")
    }


@router.get("/")
def get_cases(
    search: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Case, Patient).join(Patient, Case.patient_id == Patient.id)
    if search:
        keyword = f"%{search.strip()}%"
        query = query.filter(
            or_(Case.description.ilike(keyword), Patient.name.ilike(keyword))
        )
    if status:
        query = query.filter(Case.status == status)
    rows = query.order_by(Case.id.desc()).all()
    return {
        "code": 200,
        "data": [
            {
                "id": case.id,
                "patient_id": case.patient_id,
                "patient_name": patient.name if patient else "",
                "description": case.description,
                "status": case.status,
            }
            for case, patient in rows
        ],
    }


@router.post("/create")
def create_case(payload: CaseCreate, db: Session = Depends(get_db)):
    description = payload.description.strip()
    if not description:
        raise HTTPException(status_code=422, detail="description is required")

    if payload.patient_id is not None:
        patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
        if not patient:
            raise HTTPException(status_code=404, detail="patient not found")
    else:
        patient_name = (payload.patient_name or "").strip()
        if not patient_name:
            raise HTTPException(status_code=422, detail="patient_name is required")
        if payload.age is None or not 0 <= payload.age <= 120:
            raise HTTPException(status_code=422, detail="age must be between 0 and 120")
        if payload.gender not in {"male", "female", "other"}:
            raise HTTPException(status_code=422, detail="invalid gender")
        patient = Patient(name=patient_name, age=payload.age, gender=payload.gender)
        db.add(patient)
        db.flush()

    case = Case(patient_id=patient.id, description=description, status="created")
    db.add(case)
    db.commit()
    db.refresh(case)
    return {
        "code": 200,
        "message": "case created",
        "data": {"case_id": case.id, "patient_id": patient.id},
    }


@router.get("/{case_id}/detail")
def case_detail(case_id: int, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="case not found")

    patient = db.query(Patient).filter(Patient.id == case.patient_id).first()
    mri = db.query(MRI).filter(MRI.case_id == case_id).order_by(MRI.id.desc()).first()
    # Preserve legacy rows, but never present their unvalidated values as current.
    legacy_prediction = db.query(Prediction).filter(Prediction.case_id == case_id).first()
    legacy_report = db.query(Report).filter(Report.case_id == case_id, Report.analysis_run_id.is_(None)).first()
    report = current_model_report(mri, db)
    from app.models.analysis_run import AnalysisRun
    from app.services.artifact_integrity import current_analysis
    run = db.get(AnalysisRun, mri.analysis_run_id) if mri and mri.analysis_run_id else None
    if run and (run.case_id != case.id or run.mri_id != mri.id):
        run = None
    analysis = current_analysis(mri, run) if run else None
    previews = preview_urls(mri.slice_path) if mri else []
    views = preview_views(mri.slice_path) if mri else {"axial": [], "coronal": [], "sagittal": []}

    return {
        "code": 200,
        "data": {
            "case": {"id": case.id, "description": case.description, "status": case.status},
            "patient": {
                "name": patient.name if patient else "",
                "age": patient.age if patient else None,
                "gender": patient.gender if patient else "",
            },
            "mri": {
                "id": mri.id if mri else None,
                "filename": mri.filename if mri else "",
                "file_url": (mri.web_path or public_upload_path(mri.filepath)) if mri else None,
                "slice_url": previews[0] if previews else None,
                "preview_urls": previews,
                "preview_views": views,
                "has_preview": bool(previews),
                "preview_error": mri.preview_error if mri else None,
                "modality": mri.modality if mri else "",
                "status": mri.status if mri else "",
                "doctor_verified": bool(mri and mri.doctor_verified and analysis and not analysis['stale']),
                "input_source": mri.input_source if mri and mri.input_source else ("legacy" if mri else None),
                "source_provenance": source_lineage_summary(mri),
                "analysis_run_id": mri.analysis_run_id if mri else None,
                "verified_run_id": mri.verified_run_id if mri else None,
            },
            "prediction": None,
            "legacy_outputs": {
                "available": False,
                "has_prediction": bool(legacy_prediction),
                "has_report": bool(legacy_report),
                "reason": "Historical unvalidated outputs are excluded from current results and PDF reports.",
            },
            "report": {
                "analysis_run_id": report.analysis_run_id,
                "risk_level": report.risk_level,
                "summary": report.summary,
                "recommendation": report.recommendation,
                "created_time": utc_iso(report.created_time),
            } if report else None,
            "analysis": analysis,
        },
    }


@router.get("/{case_id}/doctor-opinion")
def get_doctor_opinion(case_id: int, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="case not found")
    opinion = db.query(DoctorOpinion).filter(DoctorOpinion.case_id == case_id).first()
    return {
        "code": 200,
        "data": {
            "author": opinion.author if opinion else "",
            "content": opinion.content if opinion else "",
            "updated_time": utc_iso(opinion.updated_time) if opinion else None,
        },
    }


@router.put("/{case_id}/doctor-opinion")
def save_doctor_opinion(case_id: int, payload: DoctorOpinionUpdate, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="case not found")
    opinion = db.query(DoctorOpinion).filter(DoctorOpinion.case_id == case_id).first()
    if opinion is None:
        opinion = DoctorOpinion(case_id=case_id)
        db.add(opinion)
    opinion.author = (payload.author or "").strip() or None
    opinion.content = payload.content.strip()
    db.commit()
    db.refresh(opinion)
    return {"code": 200, "data": {"updated_time": utc_iso(opinion.updated_time)}}


@router.get("/{case_id}/survival")
def get_survival_prediction(case_id: int, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="case not found")
    raise HTTPException(503, "No validated survival model is available")
