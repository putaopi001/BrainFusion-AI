"""Legacy rows remain intact while only version-bound model reports are current."""
import json
from uuid import uuid4

import pytest
import nibabel as nib
import numpy as np
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.analysis_run import AnalysisRun
from app.models.mri import MRI
from app.models.prediction import Prediction
from app.models.report import Report
from app.research.dataset import sha256

client = TestClient(app)


def create_case():
    return client.post('/cases/create', json={
        'patient_name': 'Output validation', 'age': 50,
        'gender': 'female', 'description': 'Isolated output validation',
    }).json()['data']['case_id']


def seed_current(case_id, tmp_path, state='succeeded', source='model'):
    run_id = uuid4().hex
    image, mask = tmp_path / (run_id + '.nii.gz'), tmp_path / (run_id + '_mask.nii.gz')
    nib.save(nib.Nifti1Image(np.ones((3, 4, 5), np.uint8), np.eye(4)), image)
    nib.save(nib.Nifti1Image(np.ones((3, 4, 5), np.uint8), np.eye(4)), mask)
    paths = {key: str(image) for key in ['t1c', 't1n', 't2w', 't2f']}
    with SessionLocal() as db:
        mri = MRI(case_id=case_id, filename='validation.nii.gz',
                  status='analyzed', segmentation_source=source, analysis_run_id=run_id,
                  filepath=str(image), sequences_json=json.dumps(paths), segmentation_path=str(mask))
        db.add(mri)
        db.flush()
        db.add(AnalysisRun(id=run_id, case_id=case_id, mri_id=mri.id,
                           state=state, request_json='{}', result_json=json.dumps({
                               'model': 'MONAI test contract', 'volumes_ml': {'WT': 12.5},
                               'mask_path': str(mask), 'mask_sha256': sha256(mask),
                               'input_sha256': {key: sha256(image) for key in paths},
                           })))
        db.add(Report(case_id=case_id, analysis_run_id=run_id, risk_level='unavailable',
                      summary='["Version-bound segmentation"]', recommendation='["Review boundaries"]'))
        db.commit()
        return run_id, mri.id


def test_legacy_rows_are_archived_not_current_even_without_mri():
    case_id = create_case()
    with SessionLocal() as db:
        old_prediction = Prediction(case_id=case_id, tumor_probability=.91, risk_score=.78,
                                    fusion_score=.85, risk_level='high', model_version='BrainFusion-v0.4')
        old_report = Report(case_id=case_id, risk_level='high',
                            summary='["LEGACY_PLACEHOLDER_SUMMARY"]', recommendation='["OLD_TREATMENT"]')
        db.add_all([old_prediction, old_report])
        db.commit()
        ids = old_prediction.id, old_report.id
    for with_mri in (False, True):
        if with_mri:
            with SessionLocal() as db:
                db.add(MRI(case_id=case_id, status='preview_ready', segmentation_source='unavailable'))
                db.commit()
        detail = client.get(f'/cases/{case_id}/detail').json()['data']
        assert detail['prediction'] is None and detail['report'] is None
        assert detail['legacy_outputs'] == {
            'available': False, 'has_prediction': True, 'has_report': True,
            'reason': 'Historical unvalidated outputs are excluded from current results and PDF reports.',
        }
        assert 'LEGACY_PLACEHOLDER_SUMMARY' not in json.dumps(detail)
        assert client.get(f'/prediction/{case_id}').status_code == 503
        assert client.get(f'/reports/{case_id}').status_code == 404
    archive = client.get('/debug/predictions').json()
    old = next(item for item in archive['data'] if item['id'] == ids[0])
    assert archive['available'] is False
    assert old['source'] == 'legacy_unverified' and old['current'] is False
    with SessionLocal() as db:
        assert db.get(Prediction, ids[0]).risk_score == .78
        assert db.get(Report, ids[1]).summary == '["LEGACY_PLACEHOLDER_SUMMARY"]'


@pytest.mark.parametrize('state,source', [
    ('queued', 'model'), ('running', 'model'), ('failed', 'model'),
    ('succeeded', 'uploaded'), ('succeeded', 'mock'), ('succeeded', 'unavailable'),
])
def test_inactive_or_non_model_reports_cannot_be_exported(state, source, tmp_path):
    case_id = create_case()
    seed_current(case_id, tmp_path, state, source)
    assert client.get(f'/cases/{case_id}/detail').json()['data']['report'] is None
    assert client.get(f'/reports/{case_id}').status_code == 404
    assert client.post(f'/reports/generate/{case_id}').status_code == 404


def test_current_successful_report_survives_later_legacy_insert(tmp_path):
    case_id = create_case()
    run_id, _ = seed_current(case_id, tmp_path)
    with SessionLocal() as db:
        db.add(Report(case_id=case_id, risk_level='high', summary='["LATE_LEGACY"]', recommendation='[]'))
        db.commit()
    detail = client.get(f'/cases/{case_id}/detail').json()['data']
    assert detail['report']['analysis_run_id'] == run_id
    assert detail['report']['created_time'].endswith('+00:00')
    response = client.get(f'/reports/{case_id}')
    assert response.status_code == 200
    assert response.json()['data']['analysis_run_id'] == run_id
    assert client.post(f'/reports/generate/{case_id}').status_code == 200
    assert detail['prediction'] is None


def test_cross_case_analysis_reference_is_not_a_current_result(tmp_path):
    case_id, other_case = create_case(), create_case()
    run_id, _ = seed_current(other_case, tmp_path)
    with SessionLocal() as db:
        db.add(MRI(case_id=case_id, analysis_run_id=run_id, segmentation_source='model'))
        db.add(Report(case_id=case_id, analysis_run_id=run_id, summary='[]', recommendation='[]'))
        db.commit()
    detail = client.get(f'/cases/{case_id}/detail').json()['data']
    assert detail['report'] is None and detail['analysis'] is None
    assert client.get(f'/reports/{case_id}').status_code == 404
    assert client.post(f'/mri/{case_id}/verify', params={'run_id': run_id}).status_code == 409


def test_reanalysis_invalidates_old_current_report_but_preserves_it(tmp_path):
    case_id = create_case()
    old_run, mri_id = seed_current(case_id, tmp_path)
    new_run = uuid4().hex
    with SessionLocal() as db:
        mri = db.get(MRI, mri_id)
        mri.analysis_run_id, mri.segmentation_source = new_run, 'unavailable'
        db.add(AnalysisRun(id=new_run, case_id=case_id, mri_id=mri_id,
                           state='running', request_json='{}'))
        db.commit()
    assert client.get(f'/cases/{case_id}/detail').json()['data']['report'] is None
    assert client.get(f'/reports/{case_id}').status_code == 404
    with SessionLocal() as db:
        assert db.query(Report).filter(Report.analysis_run_id == old_run).count() == 1
