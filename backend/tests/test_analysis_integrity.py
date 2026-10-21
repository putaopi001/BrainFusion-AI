"""Current-only consumers reject modified bytes while history is unchanged."""
import json
import os
from pathlib import Path
from uuid import uuid4
import nibabel as nib
import numpy as np
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.analysis_run import AnalysisRun
from app.models.mri import MRI
from app.models.report import Report
from app.models.case import Case
from app.research.dataset import sha256
from app.services import analysis_jobs

client = TestClient(app)


def test_worker_rejects_dicom_inference_result_with_unreviewed_input_hash(tmp_path, monkeypatch):
    case_id = client.post('/cases/create', json={'patient_name': 'SYNTHETIC DICOM hash guard', 'age': 50,
        'gender': 'female', 'description': 'Worker contract fixture; no inference'}).json()['data']['case_id']
    paths = {}
    for role in ('t1c', 't1n', 't2w', 't2f'):
        source = tmp_path / (role + '.nii.gz')
        source.write_bytes(('reviewed-' + role).encode('ascii'))
        paths[role] = str(source)
    expected = {role: sha256(path) for role, path in paths.items()}
    run_id = uuid4().hex
    output_dir = tmp_path / 'worker-output'
    with SessionLocal() as db:
        case = db.get(Case, case_id)
        mri = MRI(case_id=case_id, filepath=paths['t2f'], sequences_json=json.dumps(paths),
            input_source='dicom-conversion', analysis_run_id=run_id, status='processing')
        db.add(mri); db.flush()
        run = AnalysisRun(id=run_id, case_id=case_id, mri_id=mri.id, state='queued',
            request_json=json.dumps({'sequences': paths, 'output_dir': str(output_dir),
                'model_dir': str(tmp_path / 'model'), 'expected_input_sha256': expected}))
        db.add(run); db.commit()

    def fake_worker(args, cwd, stdout, stderr, timeout):
        request = json.loads(Path(args[-1]).read_text(encoding='utf-8'))
        result = {'mask_path': str(tmp_path / 'unopened-mask.nii.gz'),
            'input_sha256': {**expected, 't1c': '0' * 64}}
        Path(request['output_dir'], 'result.json').write_text(json.dumps(result), encoding='utf-8')
        return subprocess.CompletedProcess(args, 0)
    import subprocess
    monkeypatch.setattr(analysis_jobs.subprocess, 'run', fake_worker)
    analysis_jobs.execute(run_id)

    with SessionLocal() as db:
        run = db.get(AnalysisRun, run_id)
        mri = db.get(MRI, run.mri_id)
        assert run.state == 'failed'
        assert 'reviewed DICOM conversion' in run.error
        assert mri.status == 'failed'
        assert mri.segmentation_path is None
        assert db.query(Report).filter_by(analysis_run_id=run_id).count() == 0


@pytest.mark.parametrize('change', ['sequence', 'mask', 'missing', 'mask_path', 'missing_lineage', 'corrupt_metadata', 'same_size_restored_mtime'])
def test_all_current_consumers_reject_drift_but_preserve_history(tmp_path, change):
    case_id = client.post('/cases/create', json={'patient_name': 'SYNTHETIC current integrity', 'age': 50,
                          'gender': 'female', 'description': 'Owned drift fixture, not new real inference'}).json()['data']['case_id']
    source, mask = tmp_path / 'input.nii.gz', tmp_path / 'mask.nii.gz'
    nib.save(nib.Nifti1Image(np.ones((3, 4, 5), np.uint8), np.eye(4)), source)
    nib.save(nib.Nifti1Image(np.ones((3, 4, 5), np.uint8), np.eye(4)), mask)
    paths = {key: str(source) for key in ['t1c', 't1n', 't2w', 't2f']}
    run_id = uuid4().hex
    result = {'model': 'SYNTHETIC unit fixture', 'volumes_ml': {'WT': 1}, 'mask_path': str(mask),
              'mask_sha256': sha256(mask), 'input_sha256': {key: sha256(source) for key in paths}}
    with SessionLocal() as db:
        mri = MRI(case_id=case_id, filepath=str(source), sequences_json=json.dumps(paths),
                  segmentation_path=str(mask), segmentation_source='model', analysis_run_id=run_id,
                  doctor_verified=True, verified_run_id=run_id)
        db.add(mri); db.flush(); mri_id = mri.id
        db.add(AnalysisRun(id=run_id, case_id=case_id, mri_id=mri_id, state='succeeded', request_json='{}', result_json=json.dumps(result)))
        report = Report(case_id=case_id, analysis_run_id=run_id, summary='["Saved synthetic test report"]', recommendation='[]')
        db.add(report); db.commit(); report_id = report.id
    assert client.get(f'/reports/{case_id}').status_code == 200
    assert client.get(f'/mri/{case_id}/mask/axial/2', params={'version': run_id}).status_code == 200
    assert client.get(f'/mri/{case_id}/mask/axial/2', params={'version': 'old-version'}).status_code == 409
    assert client.get(f'/cases/{case_id}/detail').json()['data']['analysis']['stale'] is False
    if change in ['sequence', 'mask', 'same_size_restored_mtime']:
        changed = source if change in ['sequence', 'same_size_restored_mtime'] else mask
        before = changed.stat()
        if change == 'same_size_restored_mtime':
            content = bytearray(changed.read_bytes())
            content[len(content) // 2] ^= 1
            changed.write_bytes(content)
            os.utime(changed, ns=(before.st_atime_ns, before.st_mtime_ns))
            assert changed.stat().st_size == before.st_size
            assert changed.stat().st_mtime_ns == before.st_mtime_ns
        else:
            nib.save(nib.Nifti1Image(np.full((3, 4, 5), 2, np.uint8), np.eye(4)), changed)
            os.utime(changed, ns=(before.st_mtime_ns + 1_000_000_000,) * 2)
    if change == 'missing': source.unlink()
    with SessionLocal() as db:
        if change == 'mask_path': db.get(MRI, mri_id).segmentation_path = str(source)
        if change == 'missing_lineage':
            del result['input_sha256']; db.get(AnalysisRun, run_id).result_json = json.dumps(result)
        if change == 'corrupt_metadata': db.get(AnalysisRun, run_id).result_json = 'invalid json'
        db.commit()
        historical = db.get(AnalysisRun, run_id).result_json
    job = client.get(f'/analysis/{case_id}').json()['data']
    assert job['state'] == 'succeeded' and job['stale'] is True and job['result'] is None and job['error']
    detail = client.get(f'/cases/{case_id}/detail').json()['data']
    assert detail['report'] is None and detail['analysis']['result'] is None
    assert detail['mri']['doctor_verified'] is False
    assert client.get(f'/mri/{case_id}').json()['data']['doctor_verified'] is False
    assert client.get(f'/reports/{case_id}').status_code == 404
    assert client.post(f'/reports/generate/{case_id}').status_code == 404
    assert client.post(f'/mri/{case_id}/verify', params={'run_id': run_id}).status_code == 409
    seg = client.get(f'/mri/{case_id}/segmentation').json()['data']
    assert seg['available'] is False and seg['stale'] is True
    assert client.get(f'/mri/{case_id}/mask/axial/2').status_code == 409
    history = client.get(f'/analysis/{case_id}/history')
    assert history.status_code == 200
    row = next(item for item in history.json()['data'] if item['id'] == run_id)
    assert row['state'] == 'succeeded' and row['current'] is False
    if change != 'corrupt_metadata': assert row['result'] == json.loads(historical)
    with SessionLocal() as db:
        assert db.get(AnalysisRun, run_id).state == 'succeeded'
        assert db.get(AnalysisRun, run_id).result_json == historical
        assert db.get(MRI, mri_id).doctor_verified is True  # historical confirmation kept, not displayed as current
        assert db.get(Report, report_id).summary == '["Saved synthetic test report"]'
