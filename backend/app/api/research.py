from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from app.services import research_service
from app.database import get_db
from app.services import feature_jobs
from app.services import case_research_input

router = APIRouter(prefix='/research', tags=['research'])


def invoke(function, *args):
    try:
        return {'code': 200, 'data': function(*args)}
    except KeyError as error:
        raise HTTPException(404, str(error))
    except (FileNotFoundError, ImportError) as error:
        raise HTTPException(503, 'Research artifact or dependency unavailable: ' + str(error))
    except ValueError as error:
        raise HTTPException(409, str(error))


@router.get('/summary')
def summary():
    return invoke(lambda: research_service.current_summary()[0])


@router.get('/patients/{source_patient_id}')
def development_prediction(source_patient_id: str):
    return invoke(research_service.predict_development, source_patient_id)


class ClinicalInput(BaseModel):
    age: int = Field(ge=0, le=120)
    female: bool


@router.post('/clinical')
def clinical_prediction(inputs: ClinicalInput):
    return invoke(research_service.predict_clinical, inputs.age, inputs.female)


@router.post('/cases/{case_id}/features', status_code=202)
def extract_case_features(case_id: int, inputs: ClinicalInput | None = None, db: Session = Depends(get_db)):
    clinical = (case_research_input.update(case_id, inputs.age, inputs.female, db)
                if inputs else case_research_input.current(case_id, db))
    if not clinical['available']:
        raise HTTPException(409, clinical['reason'])
    return invoke(feature_jobs.submit, case_id, clinical['age'], clinical['female'], db)


@router.get('/cases/{case_id}/features')
def get_case_features(case_id: int, db: Session = Depends(get_db)):
    return invoke(feature_jobs.current, case_id, db)


@router.get('/cases/{case_id}/clinical-input')
def get_case_clinical_input(case_id: int, db: Session = Depends(get_db)):
    return invoke(case_research_input.current, case_id, db)


@router.put('/cases/{case_id}/clinical-input')
def update_case_clinical_input(case_id: int, inputs: ClinicalInput, db: Session = Depends(get_db)):
    return invoke(case_research_input.update, case_id, inputs.age, inputs.female, db)
