from pathlib import Path

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


router = APIRouter(prefix="/cases", tags=["cases"])


def public_upload_path(path: str | None) -> str | None:
    if not path:
        return None
    normalized = path.replace("\\", "/")
    marker = "/uploads/"
    index = normalized.lower().find(marker)
    if index >= 0:
        return normalized[index:]
    if normalized.startswith("uploads/"):
        return f"/{normalized}"
    return None


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
    prediction = db.query(Prediction).filter(Prediction.case_id == case_id).order_by(Prediction.id.desc()).first()
    report = db.query(Report).filter(Report.case_id == case_id).order_by(Report.id.desc()).first()
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
            },
            "prediction": {
                "tumor_probability": prediction.tumor_probability,
                "risk_score": prediction.risk_score,
                "fusion_score": prediction.fusion_score,
                "risk_level": prediction.risk_level,
                "model_version": prediction.model_version,
                "created_time": prediction.created_time.isoformat() if prediction.created_time else None,
            } if prediction else None,
            "report": {
                "risk_level": report.risk_level,
                "summary": report.summary,
                "recommendation": report.recommendation,
                "created_time": report.created_time.isoformat() if report.created_time else None,
            } if report else None,
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
            "updated_time": opinion.updated_time.isoformat() if opinion else None,
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
    return {"code": 200, "data": {"updated_time": opinion.updated_time.isoformat()}}
