from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.patient import Patient
from app.schemas.patient import PatientCreate


router = APIRouter(prefix="/patients", tags=["patients"])


def serialize_patient(patient: Patient) -> dict:
    return {
        "id": patient.id,
        "name": patient.name,
        "age": patient.age,
        "gender": patient.gender,
        "created_time": patient.created_time.isoformat() if patient.created_time else None,
    }


@router.post("/")
def create_patient(patient: PatientCreate, db: Session = Depends(get_db)):
    db_patient = Patient(name=patient.name, age=patient.age, gender=patient.gender)
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    return {"code": 200, "message": "患者创建成功", "data": serialize_patient(db_patient)}


@router.get("/")
def get_patients(db: Session = Depends(get_db)):
    items = db.query(Patient).order_by(Patient.id.desc()).all()
    return {"code": 200, "data": [serialize_patient(item) for item in items]}
