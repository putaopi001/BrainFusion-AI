import io
import json
from uuid import uuid4
import nibabel as nib
import numpy as np
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.analysis_run import AnalysisRun
from app.models.mri import MRI
from app.services.analysis_jobs import execute, recover_interrupted_jobs

client = TestClient(app)


def create_mri(tmp_path):
    patient = client.post('/patients/', json={'name': 'State validation', 'age': 50, 'gender': 'other'}).json()['data']['id']
    case_id = client.post('/cases/create', json={'patient_id': patient, 'description': 'Validation'}).json()['data']['case_id']
    source, mask = tmp_path / 'mri.nii.gz', tmp_path / 'mask.nii.gz'
    image = nib.Nifti1Image(np.zeros((3, 4, 5), np.uint8), np.eye(4))
    nib.save(image, source)
    nib.save(image, mask)
    with SessionLocal() as db:
        mri = MRI(case_id=case_id, filepath=str(source), segmentation_path=str(mask), segmentation_source='model', status='analyzed')
        db.add(mri)
        db.commit()
        return case_id, mri.id, mask


def test_invalid_uploaded_mask_preserves_previous_result(tmp_path):
    case_id, mri_id, mask = create_mri(tmp_path)
    before = mask.read_bytes()
    response = client.post(f'/mri/{case_id}/segmentation', files={'file': ('invalid.nii.gz', io.BytesIO(b'not a nifti'), 'application/gzip')})
    assert response.status_code == 422, response.text
    with SessionLocal() as db:
        assert db.get(MRI, mri_id).segmentation_path == str(mask)
    assert mask.read_bytes() == before


def test_failed_worker_does_not_produce_report_or_confirmation(tmp_path, monkeypatch):
    case_id, mri_id, _ = create_mri(tmp_path)
    run_id = uuid4().hex
    with SessionLocal() as db:
        mri = db.get(MRI, mri_id)
        mri.analysis_run_id, mri.doctor_verified = run_id, False
        db.add(AnalysisRun(id=run_id, case_id=case_id, mri_id=mri_id, request_json=json.dumps({'output_dir': str(tmp_path / 'failed-run')})))
        db.commit()
    def failure(*args, **kwargs):
        raise RuntimeError('Intentional worker failure')
    monkeypatch.setattr('app.services.analysis_jobs.subprocess.run', failure)
    execute(run_id)
    with SessionLocal() as db:
        assert db.get(AnalysisRun, run_id).state == 'failed'
        assert db.get(MRI, mri_id).status == 'failed'
    assert client.post(f'/mri/{case_id}/verify', params={'run_id': run_id}).status_code == 409
    assert client.get(f'/reports/{case_id}').status_code == 404


def test_restart_marks_interrupted_job_failed(tmp_path):
    case_id, mri_id, _ = create_mri(tmp_path)
    run_id = uuid4().hex
    with SessionLocal() as db:
        mri = db.get(MRI, mri_id)
        mri.analysis_run_id, mri.status = run_id, 'processing'
        db.add(AnalysisRun(id=run_id, case_id=case_id, mri_id=mri_id, state='running', request_json='{}'))
        db.commit()
    recover_interrupted_jobs()
    with SessionLocal() as db:
        run = db.get(AnalysisRun, run_id)
        assert run.state == 'failed'
        assert 'restarted' in run.error
        assert db.get(MRI, mri_id).status == 'failed'
