from fastapi import APIRouter, HTTPException, Depends, File, Form, UploadFile
from fastapi.responses import Response
import csv
import io
import json
from typing import Any, Literal
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from app.services import research_service
from app.database import get_db
from app.services import feature_jobs
from app.services import case_research_input
from app.research.survival import (EndpointContract, cox_ph, kaplan_meier,
                                   public_validation, validate_endpoint)
from app.services import segmentation_evaluation
from app.services.local_auth import require_doctor
from starlette.concurrency import run_in_threadpool

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


class SurvivalContractInput(BaseModel):
    endpoint: Literal['OS', 'PFS']
    patient_id: str = Field(min_length=1)
    duration: str = Field(min_length=1)
    event: str = Field(min_length=1)
    time_origin: str = Field(min_length=1)
    expected_time_origin: str = Field(min_length=1)
    time_unit: Literal['days', 'months', 'years']
    event_value: str
    censored_value: str
    research_use_authorized: bool = False

    def to_contract(self):
        return EndpointContract(
            endpoint=self.endpoint, patient_id=self.patient_id, duration=self.duration,
            event=self.event, time_origin=self.time_origin,
            expected_time_origin=self.expected_time_origin, time_unit=self.time_unit,
            event_value=self.event_value, censored_value=self.censored_value,
            research_use_authorized=self.research_use_authorized,
        )


class SurvivalRowsInput(BaseModel):
    dataset_scope: Literal['synthetic_engineering']
    contract: SurvivalContractInput
    rows: list[dict[str, Any]]


class CoxInput(SurvivalRowsInput):
    features: list[list[float]]
    feature_names: list[str]
    l2: float = Field(default=0.1, gt=0, le=1000)


def survival_validation(payload):
    if any(not str(row.get(payload.contract.patient_id, '')).startswith('SYNTHETIC-')
           for row in payload.rows):
        raise HTTPException(403, 'Survival software API currently accepts synthetic engineering rows only.')
    audit = validate_endpoint(payload.rows, payload.contract.to_contract())
    return audit, public_validation(audit)


@router.get('/survival/status')
def survival_status():
    return {
        'code': 200,
        'data': {
            'research_status': 'BLOCKED_BY_DATA',
            'reason': 'Current survival records do not have a verified common time origin and research-use authorization.',
            'software': {
                'endpoint_validation': 'available',
                'kaplan_meier': 'synthetic_engineering_only',
                'cox_ph': 'synthetic_engineering_only',
                'random_survival_forest': 'not_available',
            },
            'individual_predictions_available': False,
            'api_scope': 'synthetic_engineering_only',
            'scope': 'status only; no patient rows are loaded or modeled',
        },
    }


@router.post('/survival/validate')
def validate_survival(payload: SurvivalRowsInput):
    _, result = survival_validation(payload)
    return {'code': 200, 'data': result}


@router.post('/survival/kaplan-meier')
def survival_kaplan_meier(payload: SurvivalRowsInput):
    audit, result = survival_validation(payload)
    if not audit['eligible']:
        raise HTTPException(409, {'validation': result})
    return {'code': 200, 'data': kaplan_meier(audit)}


@router.post('/survival/cox')
def survival_cox(payload: CoxInput):
    audit, result = survival_validation(payload)
    if not audit['eligible']:
        raise HTTPException(409, {'validation': result})
    try:
        result = cox_ph(audit, payload.features, payload.feature_names, payload.l2)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    return {'code': 200, 'data': result}


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


def _evaluation_context(case_id, analysis_run_id, db):
    try:
        return segmentation_evaluation.current_run_context(case_id, analysis_run_id, db)
    except KeyError as error:
        raise HTTPException(404, str(error)) from None
    except (OSError, TypeError) as error:
        raise HTTPException(409, 'Required analysis artifacts are unavailable or invalid') from None
    except ValueError as error:
        raise HTTPException(409, str(error)) from None


def _public_evaluation(record):
    if not record:
        return None
    return {key: value for key, value in record.items() if key != "authorization_receipt_sha256"}


@router.get('/cases/{case_id}/analysis/{analysis_run_id}/segmentation-evaluation')
def get_segmentation_evaluation(case_id: int, analysis_run_id: str,
                                identity: dict = Depends(require_doctor), db: Session = Depends(get_db)):
    context = _evaluation_context(case_id, analysis_run_id, db)
    record = segmentation_evaluation.load_latest(context)
    result = context['result']
    return {'code': 200, 'data': {
        'status': record.get('status') if record else 'NOT_AVAILABLE',
        'reference_annotation_available': bool(record),
        'case_id': case_id,
        'analysis_run_id': analysis_run_id,
        'mri_id': context['mri'].id,
        'model_version': result.get('model'),
        'input_sha256': context['input_sha256'],
        'prediction_mask_sha256': context['mask_sha256'],
        'record': _public_evaluation(record),
        'note': 'This local review session is not verification of professional credentials or external research authorization.' if not identity.get('professional_credential_verified') else None,
    }}


@router.post('/cases/{case_id}/analysis/{analysis_run_id}/segmentation-evaluation', status_code=201)
async def create_segmentation_evaluation(
    case_id: int,
    analysis_run_id: str,
    reference_mask: UploadFile = File(...),
    dataset_version: str = Form(..., min_length=1, max_length=160),
    annotation_id: str = Form(..., min_length=1, max_length=160),
    authorization_receipt: str = Form(..., min_length=8, max_length=512),
    research_use_authorized: bool = Form(False),
    identity: dict = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    if not research_use_authorized:
        raise HTTPException(403, 'Explicit research-use authorization is required for reference-label evaluation')
    context = _evaluation_context(case_id, analysis_run_id, db)
    try:
        record = await run_in_threadpool(
            segmentation_evaluation.evaluate_uploaded_reference,
            context, reference_mask.file, reference_mask.filename, dataset_version,
            annotation_id, authorization_receipt, identity,
        )
        return {'code': 201, 'data': _public_evaluation(record)}
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    except (OSError, TypeError, KeyError) as error:
        # Expose only the exception class; filesystem paths and artifact contents stay private.
        raise HTTPException(409, 'Evaluation artifacts are unavailable or invalid (' + type(error).__name__ + ')') from None
    finally:
        await reference_mask.close()


@router.get('/cases/{case_id}/analysis/{analysis_run_id}/segmentation-evaluation.csv')
def export_segmentation_evaluation(case_id: int, analysis_run_id: str,
                                   identity: dict = Depends(require_doctor), db: Session = Depends(get_db)):
    context = _evaluation_context(case_id, analysis_run_id, db)
    record = segmentation_evaluation.load_latest(context)
    if not record:
        raise HTTPException(409, 'NOT_AVAILABLE: a reviewed reference annotation is required')
    output = io.StringIO(newline='')
    columns = ['case_id', 'mri_id', 'analysis_run_id', 'model_version', 'dataset_version',
               'annotation_ref', 'protocol', 'evaluation_id', 'mask_label', 'dice', 'hd95_mm',
               'hd95_status', 'hd95_reason', 'precision', 'recall', 'true_positive_voxels',
               'false_positive_voxels', 'false_negative_voxels', 'empty_rule']
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator='\n')
    writer.writeheader()
    for label, metrics in record.get('regions', {}).items():
        writer.writerow({
            'case_id': record.get('case_id'), 'mri_id': record.get('mri_id'),
            'analysis_run_id': record.get('analysis_run_id'), 'model_version': record.get('model_version'),
            'dataset_version': record.get('dataset_version'), 'annotation_ref': record.get('annotation_ref'),
            'protocol': record.get('protocol'), 'evaluation_id': record.get('evaluation_id'),
            'mask_label': label, **metrics,
        })
    return Response(content=output.getvalue(), media_type='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="segmentation-evaluation-{analysis_run_id}.csv"'})
