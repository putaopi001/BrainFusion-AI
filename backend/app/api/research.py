from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
import csv
import io
import json
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


@router.get('/cases/{case_id}/features.csv')
def export_case_features(case_id: int, db: Session = Depends(get_db)):
    state = feature_jobs.current(case_id, db)
    if (not state or state.get('state') != 'succeeded' or state.get('stale')
            or not isinstance(state.get('result'), dict)):
        raise HTTPException(409, 'A current successful radiomics result is required for export')
    result = state['result']
    features = result.get('selected_features')
    if not isinstance(features, dict) or not features:
        raise HTTPException(409, 'The current task has no radiomics features to export')
    if not isinstance(result.get('protocol'), dict) or not result['protocol']:
        raise HTTPException(409, 'The current task has no persisted extraction protocol')
    output = io.StringIO(newline='')
    columns = ['analysis_run_id', 'research_run_id', 'contract_sha256', 'feature_source',
               'device', 'software_versions_json', 'radiomics_protocol_json', 'input_sha256_json', 'mask_sha256',
               'feature_record_id', 'extraction_seconds', 'mask_label', 'feature_name', 'value',
               'region_voxel_count', 'noncomputable_reason']
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator='\n')
    writer.writeheader()
    versions = json.dumps(result.get('versions', {}), sort_keys=True, separators=(',', ':'))
    protocol = json.dumps(result.get('protocol', {}), sort_keys=True, separators=(',', ':'))
    inputs = json.dumps(result.get('input_sha256', {}), sort_keys=True, separators=(',', ':'))
    voxel_counts = result.get('region_voxel_counts', {})
    for key, value in sorted(features.items()):
        label, separator, feature_name = key.partition(':')
        if not separator or label not in {'1', '2', '3'}:
            raise HTTPException(409, 'Stored radiomics feature key is invalid')
        writer.writerow({
            'analysis_run_id': state.get('analysis_run_id', ''),
            'research_run_id': state.get('research_run_id', ''),
            'contract_sha256': result.get('contract_sha256', ''),
            'feature_source': result.get('feature_source', ''),
            'device': result.get('device', ''),
            'software_versions_json': versions,
            'radiomics_protocol_json': protocol,
            'input_sha256_json': inputs,
            'mask_sha256': result.get('mask_sha256', ''),
            'feature_record_id': result.get('feature_record_id', ''),
            'extraction_seconds': result.get('extraction_seconds', ''),
            'mask_label': label,
            'feature_name': feature_name,
            'value': '' if value is None else value,
            'region_voxel_count': voxel_counts.get(label, ''),
            'noncomputable_reason': 'empty mask region' if value is None else '',
        })
    filename = f'brainfusion-case-{case_id}-features.csv'
    return Response(content=output.getvalue(), media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="{filename}"'})


@router.get('/cases/{case_id}/clinical-input')
def get_case_clinical_input(case_id: int, db: Session = Depends(get_db)):
    return invoke(case_research_input.current, case_id, db)


@router.put('/cases/{case_id}/clinical-input')
def update_case_clinical_input(case_id: int, inputs: ClinicalInput, db: Session = Depends(get_db)):
    return invoke(case_research_input.update, case_id, inputs.age, inputs.female, db)
