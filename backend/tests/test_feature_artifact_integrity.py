"""Externally modified input bytes invalidate presentation, not historical files."""
import json
import os
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.mri import MRI
from app.models.analysis_run import AnalysisRun
from app.services import feature_jobs, case_research_input
from app.research.dataset import sha256

client = TestClient(app)


@pytest.mark.parametrize('change', ['sequence', 'mask', 'missing', 'missing_lineage', 'same_size_restored_mtime'])
def test_current_get_invalidates_changed_artifacts_and_preserves_state(tmp_path, monkeypatch, change):
    case_id = client.post('/cases/create', json={'patient_name': 'SYNTHETIC file integrity', 'age': 50,
                          'gender': 'female', 'description': 'Owned file modification test'}).json()['data']['case_id']
    source, mask = tmp_path / 'source.bin', tmp_path / 'mask.bin'
    source.write_bytes(b'initial data'); mask.write_bytes(b'initial mask')
    paths = {key: str(source) for key in ['t1c', 't1n', 't2w', 't2f']}
    result = {'probability': .25, 'input_sha256': {key: sha256(source) for key in paths}, 'mask_sha256': sha256(mask)}
    analysis_id, job_id = uuid4().hex, uuid4().hex
    with SessionLocal() as db:
        clinical = case_research_input.current(case_id, db)
        mri = MRI(case_id=case_id, analysis_run_id=analysis_id, segmentation_source='model',
                   segmentation_path=str(mask), sequences_json=json.dumps(paths))
        db.add(mri); db.flush()
        db.add(AnalysisRun(id=analysis_id, case_id=case_id, mri_id=mri.id, state='succeeded', request_json='{}',
                          result_json=json.dumps({**result, 'mask_path': str(mask)})))
        db.commit()
    monkeypatch.setattr(feature_jobs.settings, 'FEATURE_JOBS_DIR', str(tmp_path / 'jobs'))
    monkeypatch.setattr(feature_jobs, 'current_bundle', lambda: ({'run_id': 'fixture'}, None))
    directory = tmp_path / 'jobs' / str(case_id) / analysis_id / job_id; directory.mkdir(parents=True)
    state = {'id': job_id, 'state': 'succeeded', 'case_id': case_id, 'analysis_run_id': analysis_id,
             'research_run_id': 'fixture', 'clinical_input': {'age': 50, 'female': True},
             'clinical_input_version': clinical['version'], 'result': result}
    feature_jobs.save(directory, state)
    endpoint = f'/research/cases/{case_id}/features'
    assert client.get(endpoint).json()['data']['stale'] is False
    if change in ['sequence', 'mask', 'same_size_restored_mtime']:
        changed = source if change in ['sequence', 'same_size_restored_mtime'] else mask
        before = changed.stat()
        if change == 'same_size_restored_mtime':
            content = bytearray(changed.read_bytes())
            content[0] ^= 1
            changed.write_bytes(content)
            os.utime(changed, ns=(before.st_atime_ns, before.st_mtime_ns))
            assert changed.stat().st_size == before.st_size
            assert changed.stat().st_mtime_ns == before.st_mtime_ns
        else:
            changed.write_bytes(b'modified data')
            os.utime(changed, ns=(before.st_mtime_ns + 1_000_000_000,) * 2)
    if change == 'missing': source.unlink()  # Exact owned fixture, not patient data.
    if change == 'missing_lineage':
        del state['result']['input_sha256']; feature_jobs.save(directory, state)
    before = (directory / 'state.json').read_bytes()
    value = client.get(endpoint).json()['data']
    assert value['id'] == job_id and value['stale'] is True and value['result'] is None
    assert 'changed' in value['stale_reason'] if change in ['sequence', 'mask', 'same_size_restored_mtime'] else 'unavailable' in value['stale_reason']
    assert (directory / 'state.json').read_bytes() == before
