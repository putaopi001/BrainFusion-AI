"""Real API state transitions in an owned DB, with no GPU/model training."""
import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

import nibabel as nib
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.analysis_run import AnalysisRun
from app.models.mri import MRI
from app.api import analysis
from app.services import analysis_jobs, feature_jobs
from app.services.worker_error import worker_failure
from app.research.dataset import sha256

client = TestClient(app)


@pytest.fixture
def study(tmp_path):
    case_id = client.post('/cases/create', json={
        'patient_name': 'SYNTHETIC task validation', 'age': 50, 'gender': 'female',
        'description': 'Owned pytest fixture, not clinical/model success evidence',
    }).json()['data']['case_id']
    source = tmp_path / 'mri.nii.gz'
    nib.save(nib.Nifti1Image(np.arange(60, dtype=np.float32).reshape(3, 4, 5), np.eye(4)), source)
    paths = {key: str(source) for key in analysis.SEQUENCES}
    with SessionLocal() as db:
        mri = MRI(case_id=case_id, filepath=str(source), sequences_json=json.dumps(paths))
        db.add(mri); db.commit()
        mri_id = mri.id
    return case_id, mri_id, paths


def test_concurrent_analysis_dedup_and_failed_retry(study, tmp_path, monkeypatch):
    case_id, mri_id, _ = study
    weights = tmp_path / 'models/model.pt'; weights.parent.mkdir(); weights.write_bytes(b'fixture only')
    monkeypatch.setattr(analysis.settings, 'MODEL_DIR', str(tmp_path))
    submitted = []
    monkeypatch.setattr(analysis.executor, 'submit', lambda fn, rid: submitted.append(rid))
    with ThreadPoolExecutor(max_workers=2) as callers:
        responses = list(callers.map(lambda _: client.post(f'/analysis/{case_id}'), range(2)))
    assert sorted(r.status_code for r in responses) == [202, 409]
    run_id = submitted[0]
    assert len(submitted) == 1
    assert client.get(f'/analysis/{case_id}').json()['data']['id'] == run_id
    with SessionLocal() as db:
        assert db.query(AnalysisRun).filter_by(case_id=case_id).count() == 1
        run = db.get(AnalysisRun, run_id)
        request = json.loads(run.request_json); request['output_dir'] = str(tmp_path / 'failed')
        run.request_json = json.dumps(request); db.commit()
    def failure(*args, **kwargs):
        kwargs['stderr'].write('Traceback (most recent call last):\nValueError: Empty sequence: t2f\n')
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(analysis_jobs.subprocess, 'run', failure)
    analysis_jobs.execute(run_id)
    job = client.get(f'/analysis/{case_id}').json()['data']
    assert job['state'] == 'failed' and job['result'] is None
    assert 'Empty sequence: t2f' in job['error']
    assert job['finished_time'].endswith('+00:00')
    assert client.get(f'/reports/{case_id}').status_code == 404
    retry = client.post(f'/analysis/{case_id}')
    assert retry.status_code == 202 and retry.json()['data']['id'] != run_id
    assert len(submitted) == 2
    with SessionLocal() as db:
        assert db.get(AnalysisRun, run_id).state == 'failed'
        assert db.get(MRI, mri_id).analysis_run_id == submitted[1]
        # Finish the controlled retry without producing fake success artifacts.
        db.get(AnalysisRun, submitted[1]).state = 'failed'; db.commit()


@pytest.mark.parametrize('problem', ['no_sequences', 'incomplete', 'invalid_nifti', 'missing_model'])
def test_preflight_rejects_specific_failure_without_new_run(study, tmp_path, monkeypatch, problem):
    case_id, mri_id, paths = study
    monkeypatch.setattr(analysis.settings, 'MODEL_DIR', str(tmp_path / 'no-model'))
    with SessionLocal() as db:
        mri = db.get(MRI, mri_id)
        if problem == 'no_sequences': mri.sequences_json = None
        if problem == 'incomplete': mri.sequences_json = json.dumps({'t1c': paths['t1c']})
        if problem == 'invalid_nifti':
            invalid = tmp_path / 'invalid.nii'; invalid.write_bytes(b'not nifti')
            mri.sequences_json = json.dumps({key: str(invalid) for key in paths})
        db.commit()
    response = client.post(f'/analysis/{case_id}')
    assert response.status_code == (503 if problem == 'missing_model' else 422), response.text
    assert response.json()['detail']
    with SessionLocal() as db:
        assert db.query(AnalysisRun).filter_by(case_id=case_id).count() == 0
        assert db.get(MRI, mri_id).analysis_run_id is None


def test_feature_duplicate_failure_retry_and_restart(study, tmp_path, monkeypatch):
    case_id, mri_id, paths = study
    run_id = uuid4().hex
    source = next(iter(paths.values()))
    monkeypatch.setattr(feature_jobs.settings, 'FEATURE_JOBS_DIR', str(tmp_path / 'jobs'))
    monkeypatch.setattr(feature_jobs, 'current_bundle', lambda: ({'run_id': 'fixture'}, None))
    monkeypatch.setattr(feature_jobs, 'compatibility', lambda *args: {'contract_sha256': 'test', 'model_sha256': 'test'})
    monkeypatch.setattr(feature_jobs, 'selected_features', lambda *args: ['1:original_firstorder_Mean'])
    submitted = []
    monkeypatch.setattr(feature_jobs.executor, 'submit', lambda fn, directory: submitted.append(directory))
    with SessionLocal() as db:
        mri = db.get(MRI, mri_id)
        mri.analysis_run_id, mri.segmentation_source, mri.segmentation_path = run_id, 'model', source
        db.add(AnalysisRun(id=run_id, case_id=case_id, mri_id=mri_id, state='succeeded', request_json='{}',
                           result_json=json.dumps({'mask_path': source, 'mask_sha256': sha256(source),
                                                   'input_sha256': {key: sha256(path) for key, path in paths.items()}})))
        db.commit()
    endpoint = f'/research/cases/{case_id}/features'
    with ThreadPoolExecutor(max_workers=2) as callers:
        responses = list(callers.map(lambda _: client.post(endpoint), range(2)))
    assert sorted(r.status_code for r in responses) == [202, 409]
    assert len(submitted) == 1
    first = client.get(endpoint).json()['data']
    assert first['state'] == 'queued'
    def failure(*args, **kwargs):
        kwargs['stderr'].write('RuntimeError: Image and mask geometry differ\n')
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(feature_jobs.subprocess, 'run', failure)
    feature_jobs.execute(submitted[0])
    failed = client.get(endpoint).json()['data']
    assert failed['state'] == 'failed' and failed['result'] is None
    assert 'Image and mask geometry differ' in failed['error']
    assert client.post(endpoint).status_code == 202
    assert len(submitted) == 2
    retry = client.get(endpoint).json()['data']
    assert retry['id'] != first['id'] and retry['state'] == 'queued'
    feature_jobs.recover_interrupted()
    restarted = client.get(endpoint).json()['data']
    assert restarted['state'] == 'failed' and restarted['result'] is None
    assert 'restarted' in restarted['error']
    assert json.loads((submitted[0] / 'state.json').read_text())['state'] == 'failed'


def test_worker_error_is_bounded_and_has_safe_fallback(tmp_path):
    log = tmp_path / 'worker.log'
    assert 'inspect' in worker_failure(log, 'Worker')
    log.write_text('ValueError: ' + 'x' * 20000)
    assert 'inspect' in worker_failure(log, 'Worker')  # tail lacks a complete exception prefix
    log.write_text('ValueError: ' + 'x' * 1000)
    assert len(worker_failure(log, 'Worker')) < 450
