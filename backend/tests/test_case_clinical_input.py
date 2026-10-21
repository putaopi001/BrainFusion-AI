"""Clinical changes invalidate results without changing the patient's record."""
import json
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models.case import Case
from app.models.mri import MRI
from app.models.patient import Patient
from app.models.analysis_run import AnalysisRun
from app.services import feature_jobs
from app.research.dataset import sha256

client = TestClient(app)


def create_case(gender='female'):
    return client.post('/cases/create', json={
        'patient_name': 'Clinical input test', 'age': 50, 'gender': gender,
        'description': 'Isolated clinical version test',
    }).json()['data']['case_id']


def clinical(case_id):
    response = client.get(f'/research/cases/{case_id}/clinical-input')
    assert response.status_code == 200, response.text
    return response.json()['data']


def test_patient_default_and_idempotent_case_override_keep_patient_unchanged():
    case_id = create_case()
    original = clinical(case_id)
    assert original['source'] == 'associated_patient'
    assert original['age'] == 50 and original['female'] is True
    assert clinical(case_id)['version'] == original['version']
    path = f'/research/cases/{case_id}/clinical-input'
    same = client.put(path, json={'age': 50, 'female': True}).json()['data']
    assert same['version'] == original['version']
    changed = client.put(path, json={'age': 51, 'female': False}).json()['data']
    assert changed['version'] != original['version']
    assert changed['source'] == 'case_research_override'
    assert clinical(case_id)['version'] == changed['version']
    assert client.put(path, json={'age': 51, 'female': False}).json()['data']['version'] == changed['version']
    with SessionLocal() as db:
        patient = db.get(Patient, db.get(Case, case_id).patient_id)
        assert patient.age == 50 and patient.gender == 'female'


def test_unknown_gender_is_not_silently_mapped_to_male(monkeypatch):
    case_id = create_case('other')
    value = clinical(case_id)
    assert value['available'] is False and value['female'] is None
    response = client.post(f'/research/cases/{case_id}/features')
    assert response.status_code == 409 and 'not mapped to male' in response.json()['detail']
    assert client.put(f'/research/cases/{case_id}/clinical-input', json={'age': 121, 'female': False}).status_code == 422


def test_optional_feature_request_uses_saved_case_input(monkeypatch):
    case_id = create_case()
    submitted = []
    monkeypatch.setattr(feature_jobs, 'submit', lambda cid, age, female, db: submitted.append((cid, age, female)) or {'state': 'queued'})
    assert client.post(f'/research/cases/{case_id}/features').status_code == 202
    assert submitted[-1] == (case_id, 50, True)
    # Existing clients retain their explicit-input workflow, now with persistence.
    assert client.post(f'/research/cases/{case_id}/features', json={'age': 55, 'female': False}).status_code == 202
    assert clinical(case_id)['age'] == 55
    assert client.post(f'/research/cases/{case_id}/features').status_code == 202
    assert submitted[-1] == (case_id, 55, False)


def test_saved_input_change_hides_result_and_preserves_history(tmp_path, monkeypatch):
    case_id = create_case()
    original = clinical(case_id)
    analysis_id, job_id = uuid4().hex, uuid4().hex
    source = tmp_path / 'source.bin'; source.write_bytes(b'owned lineage fixture')
    mask = tmp_path / 'mask.bin'; mask.write_bytes(b'owned mask fixture')
    paths = {key: str(source) for key in ['t1c', 't1n', 't2w', 't2f']}
    result = {'probability': .25, 'input_sha256': {key: sha256(source) for key in paths}, 'mask_sha256': sha256(mask)}
    with SessionLocal() as db:
        mri = MRI(case_id=case_id, analysis_run_id=analysis_id, sequences_json=json.dumps(paths),
                   segmentation_path=str(mask), segmentation_source='model')
        db.add(mri); db.flush()
        db.add(AnalysisRun(id=analysis_id, case_id=case_id, mri_id=mri.id, state='succeeded', request_json='{}',
                          result_json=json.dumps({**result, 'mask_path': str(mask)})))
        db.commit()
    monkeypatch.setattr(feature_jobs.settings, 'FEATURE_JOBS_DIR', str(tmp_path))
    monkeypatch.setattr(feature_jobs, 'current_bundle', lambda: ({'run_id': 'test-research'}, None))
    directory = tmp_path / str(case_id) / analysis_id / job_id
    directory.mkdir(parents=True)
    state = {'id': job_id, 'case_id': case_id, 'analysis_run_id': analysis_id,
             'state': 'succeeded', 'research_run_id': 'test-research', 'clinical_input': {'age': 50, 'female': True},
             'clinical_input_version': original['version'], 'result': result}
    feature_jobs.save(directory, state)
    before = (directory / 'state.json').read_bytes()
    assert client.get(f'/research/cases/{case_id}/features').json()['data']['result'] == result
    monkeypatch.setattr(feature_jobs, 'current_bundle', lambda: ({'run_id': 'changed-research'}, None))
    changed_model = client.get(f'/research/cases/{case_id}/features').json()['data']
    assert changed_model['stale'] is True and changed_model['result'] is None
    assert 'model version changed' in changed_model['stale_reason']
    assert (directory / 'state.json').read_bytes() == before
    def unavailable_model():
        raise FileNotFoundError('Intentional missing model')
    monkeypatch.setattr(feature_jobs, 'current_bundle', unavailable_model)
    missing = client.get(f'/research/cases/{case_id}/features').json()['data']
    assert missing['stale'] is True and missing['result'] is None
    assert 'unavailable' in missing['stale_reason']
    monkeypatch.setattr(feature_jobs, 'current_bundle', lambda: ({'run_id': 'test-research'}, None))
    client.put(f'/research/cases/{case_id}/clinical-input', json={'age': 51, 'female': True})
    stale = client.get(f'/research/cases/{case_id}/features').json()['data']
    assert stale['stale'] is True and stale['result'] is None
    assert (directory / 'state.json').read_bytes() == before
    # Returning to the same numbers is still a new explicit version.
    client.put(f'/research/cases/{case_id}/clinical-input', json={'age': 50, 'female': True})
    assert client.get(f'/research/cases/{case_id}/features').json()['data']['stale'] is True


def test_patient_change_updates_default_version():
    case_id = create_case()
    original = clinical(case_id)
    with SessionLocal() as db:
        db.get(Patient, original['patient_id']).age = 52
        db.commit()
    changed = clinical(case_id)
    assert changed['source'] == 'associated_patient' and changed['age'] == 52
    assert changed['version'] != original['version']
