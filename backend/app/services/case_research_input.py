"""Clinical input snapshots with an explicit patient default and override version."""
import hashlib
from uuid import uuid4

from fastapi import HTTPException

from app.core.time import utc_iso
from app.models.case import Case
from app.models.case_research_input import CaseResearchInput
from app.models.patient import Patient


def current(case_id, db):
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(404, 'case not found')
    patient = db.get(Patient, case.patient_id)
    if patient is None:
        raise HTTPException(409, 'Associated patient is missing')
    saved = db.get(CaseResearchInput, case_id)
    age, gender = (saved.age, saved.gender) if saved else (patient.age, patient.gender)
    version = saved.version if saved else 'patient_' + hashlib.sha256(
        f'{patient.id}:{age}:{gender}'.encode()).hexdigest()[:24]
    valid = age is not None and 0 <= age <= 120 and gender in ('male', 'female')
    return {
        'case_id': case_id, 'patient_id': patient.id, 'age': age, 'gender': gender,
        'female': gender == 'female' if gender in ('male', 'female') else None,
        'version': version, 'source': 'case_research_override' if saved else 'associated_patient',
        'updated_time': utc_iso(saved.updated_time) if saved else utc_iso(patient.updated_time),
        'available': valid,
        'reason': None if valid else 'Age 0–120 and male/female are required by the current research model; unknown/other is not mapped to male.',
    }


def update(case_id, age, female, db):
    before = current(case_id, db)
    if before['age'] == age and before['female'] == female:
        return before
    saved = db.get(CaseResearchInput, case_id)
    if saved is None:
        saved = CaseResearchInput(case_id=case_id)
        db.add(saved)
    saved.age, saved.gender, saved.version = age, 'female' if female else 'male', uuid4().hex
    db.commit()
    return current(case_id, db)


def matches(state, clinical):
    inputs = state.get('clinical_input', {})
    return (clinical['available'] and inputs.get('age') == clinical['age']
            and inputs.get('female') == clinical['female']
            and (state.get('clinical_input_version') == clinical['version']
                 or (not state.get('clinical_input_version') and clinical['source'] == 'associated_patient')))
