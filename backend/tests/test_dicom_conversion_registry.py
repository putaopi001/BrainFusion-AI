"""Case-bound registry/API tests; conversion registration uses isolated synthetic fixtures."""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.database import SessionLocal
from app.main import app
from app.models.case import Case
from app.models.patient import Patient
from app.models.pacs import PACSStudyLink
from app.services.dicom_conversion import convert_and_verify
from app.services.dicom_conversion_registry import load_index, inspect_entry, INSPECTION_LOCK, register_verified_version
from app.services.dicom_conversion_jobs import create_job, run_job, retry_job, list_jobs
from app.services.dicom_input_plan import PlanError
from app.services.pacs_client import PacsConfig
from test_dicom_conversion import files_fixture


def test_listing_jobs_when_runtime_parent_is_missing_is_empty_and_read_only(tmp_path, monkeypatch):
    index = tmp_path / 'not-created' / 'local' / 'dicom-conversions.json'
    monkeypatch.setattr(settings, 'DICOM_CONVERSION_INDEX_FILE', str(index))

    assert list_jobs() == []
    assert not index.parent.exists()


@pytest.fixture
def registered(tmp_path, monkeypatch):
    proposal, snapshots, files, _ = files_fixture(tmp_path)
    with SessionLocal() as db:
        patient = Patient(name='SYNTHETIC registry test', age=40, gender='other')
        db.add(patient); db.flush(); patient_id = patient.id
        case = Case(patient_id=patient.id, description='SYNTHETIC registry', status='created')
        db.add(case); db.flush(); case_id = case.id
        config = PacsConfig(format_version=1, archive_id=proposal['archive_id'], base_url='http://127.0.0.1:9898',
                            username='protocol-only', password='test', expected_database_server_identifier='SYNTHETIC')
        study = proposal['assignments'][0]['study_uid']
        db.add(PACSStudyLink(case_id=case_id, archive_id=config.archive_id, study_uid=study,
                            endpoint_fingerprint=config.endpoint_fingerprint, metadata_sha256='0'*64, metadata_json='{}'))
        db.commit()
    proposal.update(case_id=case_id, archive_fingerprint=config.endpoint_fingerprint)
    # Test protocol branch; generated pixels remain synthetic, never a real cohort.
    proposal['data_role'] = snapshots['data_role'] = 'dicom-metadata-snapshot'
    for row in snapshots['series']:
        row.update(source_case_id=case_id, archive_fingerprint=config.endpoint_fingerprint)
    folder = tmp_path / 'converted'; convert_and_verify(proposal, snapshots, files, folder)
    proposal_path = tmp_path/'proposal.json'; proposal_path.write_text(json.dumps(proposal), encoding='utf-8')
    snapshots_path = tmp_path/'snapshots.json'; snapshots_path.write_text(json.dumps(snapshots), encoding='utf-8')
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    row = {'version_id':'test-version', 'case_id':case_id, 'archive_id':config.archive_id,
           'archive_fingerprint':config.endpoint_fingerprint, 'study_uid':study, 'version_dir':str(folder),
           'report_sha256':sha(folder/'conversion-report.json'), 'proposal_path':str(proposal_path),
           'proposal_sha256':sha(proposal_path), 'snapshots_path':str(snapshots_path), 'snapshots_sha256':sha(snapshots_path)}
    index = tmp_path/'index.json'; index.write_text(json.dumps({'format':'dicom-conversion-index-v1','entries':[row]}), encoding='utf-8')
    monkeypatch.setattr(settings,'DICOM_CONVERSION_INDEX_FILE',str(index))
    import app.api.pacs as api
    monkeypatch.setattr(api,'load_config',lambda:config)
    yield {'case_id':case_id,'index':index,'row':row,'config':config,'proposal':proposal,'folder':folder,'files':files}
    with SessionLocal() as db:
        db.query(PACSStudyLink).filter_by(case_id=case_id).delete()
        db.query(Case).filter_by(id=case_id).delete(); db.query(Patient).filter_by(id=patient_id).delete(); db.commit()


def test_registry_writer_adds_verified_derivative_idempotently_and_rejects_bad_source(registered):
    item=registered
    args=('test-version-2',item['case_id'],item['config'].archive_id,
          item['config'].endpoint_fingerprint,item['row']['study_uid'],item['folder'],
          item['folder'].parent/'proposal.json',item['folder'].parent/'snapshots.json')
    first=register_verified_version(*args)
    assert first=={'status':'registered','version_id':'test-version-2',
                   'model_input_eligible':False,'current_mri_replaced':False}
    assert [row.version_id for row in load_index()]==['test-version','test-version-2']
    repeated=register_verified_version(*args)
    assert repeated['status']=='already_registered' and len(load_index())==2
    before=item['index'].read_bytes()
    bad=item['folder'].parent/'bad-proposal.json'
    proposal=dict(item['proposal']); proposal['archive_id']='wrong-archive'
    bad.write_text(json.dumps(proposal),encoding='utf-8')
    with pytest.raises(PlanError):
        register_verified_version('invalid-version',item['case_id'],item['config'].archive_id,
            item['config'].endpoint_fingerprint,item['row']['study_uid'],item['folder'],
            bad,item['folder'].parent/'snapshots.json')
    assert item['index'].read_bytes()==before
    assert not register_verified_version(*args)['model_input_eligible']



def test_registry_writer_rejects_a_concurrent_process_without_changing_index(registered):
    item=registered
    ready=item['folder'].parent/'registry-lock-ready.txt'
    child_code="""import sys,time
from pathlib import Path
from app.services.dicom_conversion_registry import _exclusive_index_file_lock
with _exclusive_index_file_lock(Path(sys.argv[1])):
    Path(sys.argv[2]).write_text('locked',encoding='utf-8')
    time.sleep(20)
"""
    backend=Path(__file__).resolve().parents[1]
    child=subprocess.Popen([sys.executable,'-B','-c',child_code,str(item['index']),str(ready)],
                          cwd=backend,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        for _ in range(200):
            if ready.exists(): break
            if child.poll() is not None:
                raise AssertionError('Registry lock holder exited before acquisition')
            time.sleep(0.025)
        assert ready.exists(), 'Registry lock holder did not report readiness'
        before=item['index'].read_bytes()
        with pytest.raises(PlanError,match='正在登记'):
            register_verified_version('cross-process-version',item['case_id'],item['config'].archive_id,
                item['config'].endpoint_fingerprint,item['row']['study_uid'],item['folder'],
                item['folder'].parent/'proposal.json',item['folder'].parent/'snapshots.json')
        assert item['index'].read_bytes()==before
    finally:
        child.terminate()
        child.communicate(timeout=5)


def test_list_and_inspection_never_expose_paths_or_activate_existing_case(registered):
    item = registered; client = TestClient(app)
    with SessionLocal() as db: before = (db.get(Case,item['case_id']).status, db.query(PACSStudyLink).count())
    response = client.get(f"/pacs/cases/{item['case_id']}/conversions")
    assert response.headers['cache-control']=='no-store'
    data = response.json()['data']; assert data['state']=='registered' and not data['current_mri_replaced']
    assert data['items'][0]['integrity_status']=='not_rechecked'
    assert str(item['folder']) not in response.text
    checked = client.get(f"/pacs/cases/{item['case_id']}/conversions/test-version/inspection")
    assert checked.headers['cache-control']=='no-store'
    report = checked.json()['data']; assert report['status']=='verified_readonly'
    assert not report['model_input_eligible'] and not report['live_archive_reconciled']
    assert 'nifti_path' not in checked.text and 'snapshot_path' not in checked.text
    with SessionLocal() as db: assert before==(db.get(Case,item['case_id']).status, db.query(PACSStudyLink).count())
    missing = client.get(f"/pacs/cases/{item['case_id']}/conversions/other/inspection")
    assert missing.status_code==404 and missing.headers['cache-control']=='no-store'
    assert client.post(f"/pacs/cases/{item['case_id']}/conversions", json=item['row']).status_code==405


def test_current_case_or_archive_mismatch_precedes_file_inspection(registered, monkeypatch):
    import app.api.pacs as api
    item=registered;client=TestClient(app)
    monkeypatch.setattr(api,'inspect_entry',lambda *_args:pytest.fail('Must reject before file inspection'))
    monkeypatch.setattr(api,'load_config',lambda:item['config'].model_copy(update={'archive_id':'changed'}))
    report=client.get(f"/pacs/cases/{item['case_id']}/conversions/test-version/inspection").json()['data']
    assert report['status']=='stale' and not report['model_input_eligible']
    assert client.get('/pacs/cases/999999999/conversions').status_code==404


def test_index_change_during_inspection_invalidates_response(registered, monkeypatch):
    import app.api.pacs as api
    def changing(entry):
        registered['index'].write_text(json.dumps({'format':'dicom-conversion-index-v1','entries':[]}),encoding='utf-8')
        return {'status':'verified_readonly','reason':None}
    monkeypatch.setattr(api,'inspect_entry',changing)
    report=TestClient(app).get(f"/pacs/cases/{registered['case_id']}/conversions/test-version/inspection").json()['data']
    assert report['status']=='stale' and report['reason']=='conversion_binding_changed_during_inspection'


@pytest.mark.parametrize('mode',['bad_sha','synthetic','busy'])
def test_registered_invalid_source_or_busy_keeps_model_disabled(registered,mode):
    item=registered; entry=load_index()[0]
    if mode=='busy':
        assert INSPECTION_LOCK.acquire(blocking=False)
        try:
            response=TestClient(app).get(f"/pacs/cases/{item['case_id']}/conversions/test-version/inspection")
            assert response.status_code==409 and response.headers['cache-control']=='no-store'
        finally:INSPECTION_LOCK.release()
        return
    if mode=='bad_sha':entry=entry.model_copy(update={'proposal_sha256':'0'*64})
    else:
        proposal=item['proposal'];proposal['data_role']='synthetic-fixture'
        path=item['index'].parent/'proposal.json';path.write_text(json.dumps(proposal),encoding='utf-8')
        entry=entry.model_copy(update={'proposal_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    report=inspect_entry(entry)
    assert report['status']=='invalid' and not report['model_input_eligible']


@pytest.mark.parametrize('mode',['duplicate','unknown','private_json','nonfinite','wrong_drive'])
def test_invalid_server_index_redacted(registered,mode):
    item=registered;row=item['row'];value={'format':'dicom-conversion-index-v1','entries':[row]}
    if mode=='duplicate':value['entries'].append(row.copy())
    elif mode=='unknown':row['secret_patient_name']='DO_NOT_EXPOSE'
    elif mode=='wrong_drive':row['version_dir']='C:/DO_NOT_EXPOSE'
    elif mode=='nonfinite':row['case_id']=float('nan')
    if mode=='private_json':item['index'].write_text('{"format":"DO_NOT_EXPOSE","format":"duplicate"}',encoding='utf-8')
    else:item['index'].write_text(json.dumps(value),encoding='utf-8')
    response=TestClient(app).get(f"/pacs/cases/{item['case_id']}/conversions")
    assert response.status_code==503 and response.headers['cache-control']=='no-store'
    assert 'DO_NOT_EXPOSE' not in response.text


def test_missing_server_index_returns_explicit_no_version(registered,monkeypatch):
    monkeypatch.setattr(settings,'DICOM_CONVERSION_INDEX_FILE',str(registered['index'].parent/'absent.json'))
    response=TestClient(app).get(f"/pacs/cases/{registered['case_id']}/conversions")
    assert response.json()['data']['state']=='not_registered' and response.json()['data']['items']==[]


def test_source_endpoint_permissions_busy_and_binding_change(registered,monkeypatch):
    import app.api.pacs as api
    item=registered;client=TestClient(app)
    url=f"/pacs/cases/{item['case_id']}/conversions/test-version/source-check"
    response=client.get(url)
    assert response.headers['cache-control']=='no-store' and response.json()['data']['reason']=='pixel_read_disabled'
    assert not response.json()['data']['model_input_eligible'] and not response.json()['data']['live_archive_reconciled']
    assert str(item['folder']) not in response.text
    assert client.get(f"/pacs/cases/{item['case_id']}/conversions/absent/source-check").status_code==404
    assert INSPECTION_LOCK.acquire(blocking=False)
    try:assert client.get(url).status_code==409
    finally:INSPECTION_LOCK.release()
    def changed(entry,config):
        item['index'].write_text(json.dumps({'format':'dicom-conversion-index-v1','entries':[]}),encoding='utf-8')
        return {'status':'matched_at_check','live_archive_reconciled':True,'message':'SYNTHETIC callback'}
    monkeypatch.setattr(api,'check_archive_entry',changed)
    data=client.get(url).json()['data']
    assert data['status']=='stale' and not data['live_archive_reconciled'] and not data['model_input_eligible']


@pytest.mark.parametrize('module', ['app.api.pacs', 'app.main'])
def test_missing_required_dicom_parser_fails_before_database_initialization(module, tmp_path):
    database=tmp_path/'never-created.db'
    script = '''
import importlib.abc,sys,os
from pathlib import Path
class NoDicom(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname == 'pydicom' or fullname.startswith('pydicom.'):
            raise ModuleNotFoundError('Required parser deliberately unavailable', name='pydicom')
sys.meta_path.insert(0,NoDicom())
os.environ['DATABASE_URL']='sqlite:///'+sys.argv[2]
try:
    importlib.import_module(sys.argv[1])
except RuntimeError as error:
    assert 'Required dependency pydicom is missing' in str(error)
    assert 'requirements-core.txt' in str(error)
else:
    raise AssertionError('A required parser was silently treated as optional')
assert not Path(sys.argv[2]).exists()
print('Missing required parser rejected before business database initialization')
'''
    result = subprocess.run([sys.executable, '-B', '-c', script, module, str(database)],capture_output=True,text=True,timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_installed_parser_matches_core_contract_and_exposes_conversion_routes():
    import pydicom
    from app.api.pacs import router
    requirement=(Path(__file__).resolve().parents[1]/'requirements-core.txt').read_text(encoding='utf-8')
    assert f'pydicom=={pydicom.__version__}' in requirement
    assert any(route.path.endswith('/conversions') for route in router.routes)



def _queued_job(tmp_path, item, job_id, version_id=None):
    source_file = tmp_path / (job_id + '-source-files.json')
    source_file.write_text(json.dumps(item['files']), encoding='utf-8')
    return create_job(item['row']['proposal_path'], item['row']['snapshots_path'], source_file,
                      tmp_path / (job_id + '-output'), version_id, job_id)


def test_persistent_conversion_job_succeeds_and_keeps_paths_private(registered, tmp_path):
    item = registered
    job_id = 'a' * 32
    created = _queued_job(tmp_path, item, job_id)
    assert created['state'] == 'queued' and created['model_input_eligible'] is False
    assert 'inputs' not in created and 'output_base' not in created
    input_path = item['index'].parent / 'dicom-conversion-jobs' / job_id / 'inputs' / 'proposal.json'
    assert input_path.is_file(), 'Persisted input paths must resolve after staging rename'

    result = run_job(job_id)
    assert result['state'] == 'succeeded'
    assert result['registered'] is False
    assert result['model_input_eligible'] is False and result['current_mri_replaced'] is False
    assert result['inference_performed'] is False
    assert list_jobs(item['case_id'])[0]['job_id'] == job_id


def test_conversion_job_records_failure_and_retries_into_fresh_attempt_directory(registered, tmp_path):
    item = registered
    job_id = 'b' * 32
    _queued_job(tmp_path, item, job_id)
    job_path = item['index'].parent / 'dicom-conversion-jobs' / job_id / 'job.json'
    row = json.loads(job_path.read_text(encoding='utf-8'))
    proposal_path = Path(row['inputs']['proposal']['path'])
    original = proposal_path.read_bytes()
    proposal_path.write_bytes(original + b' ')

    failed = run_job(job_id)
    assert failed['state'] == 'failed' and failed['reason'] == 'conversion_job_input_changed'
    proposal_path.write_bytes(original)
    queued = retry_job(job_id, item['case_id'], expected_attempt=1)
    assert queued['state'] == 'queued' and queued['attempt'] == 2
    succeeded = run_job(job_id)
    assert succeeded['state'] == 'succeeded' and succeeded['attempt'] == 2
    assert succeeded['registered'] is False
    output = tmp_path / ('bf-' + job_id[:12] + '-a2')
    assert output.is_dir() and (output / 'conversion-report.json').is_file()
    assert succeeded['model_input_eligible'] is False and succeeded['current_mri_replaced'] is False


def test_conversion_job_detects_changed_persisted_inputs_and_recovers_interrupted_state(registered, tmp_path):
    item = registered
    job_id = 'c' * 32
    _queued_job(tmp_path, item, job_id)
    job_path = item['index'].parent / 'dicom-conversion-jobs' / job_id / 'job.json'
    row = json.loads(job_path.read_text(encoding='utf-8'))
    proposal_path = Path(row['inputs']['proposal']['path'])
    proposal_path.write_bytes(proposal_path.read_bytes() + b' ')
    rejected = run_job(job_id)
    assert rejected['state'] == 'failed' and rejected['reason'] == 'conversion_job_input_changed'

    row = json.loads(job_path.read_text(encoding='utf-8'))
    row.update(state='running', reason=None)
    job_path.write_text(json.dumps(row), encoding='utf-8')
    recovered = list_jobs(item['case_id'])[0]
    assert recovered['state'] == 'interrupted'
    retry = retry_job(job_id, item['case_id'], expected_attempt=1)
    assert retry['state'] == 'queued' and retry['attempt'] == 2









def test_conversion_job_api_is_case_scoped_and_retry_requires_doctor(registered, tmp_path, monkeypatch):
    import app.api.pacs as api
    item = registered
    job_id = 'd' * 32
    _queued_job(tmp_path, item, job_id)
    job_path = item['index'].parent / 'dicom-conversion-jobs' / job_id / 'job.json'
    row = json.loads(job_path.read_text(encoding='utf-8'))
    row.update(state='failed', reason='synthetic_failure', finished_utc='2026-10-18T00:00:00Z')
    job_path.write_text(json.dumps(row), encoding='utf-8')

    client = TestClient(app)
    url = f"/pacs/cases/{item['case_id']}/conversion-jobs"
    unauthenticated = client.post(f"{url}/{job_id}/retry", json={'expected_attempt': 1})
    assert unauthenticated.status_code == 401

    response = client.get(url)
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    jobs = response.json()['data']['items']
    assert len(jobs) == 1 and jobs[0]['job_id'] == job_id and jobs[0]['state'] == 'failed'
    assert str(item['folder']) not in response.text and 'output_base' not in response.text
    assert client.get('/pacs/cases/999999999/conversion-jobs').status_code == 404

    identity = {'id': 'e' * 32, 'username': 'synthetic-doctor', 'display_name': 'SYNTHETIC doctor',
                'role': 'doctor', 'professional_credential_verified': False}
    from app.services.local_auth import require_doctor
    app.dependency_overrides[require_doctor] = lambda: identity
    scheduled = []
    monkeypatch.setattr(api.dicom_conversion_jobs, 'submit_job', lambda candidate: scheduled.append(candidate))
    try:
        retried = client.post(f"{url}/{job_id}/retry", json={'expected_attempt': 1})
        assert retried.status_code == 200 and retried.headers['cache-control'] == 'no-store'
        data = retried.json()['data']
        assert data['state'] == 'queued' and data['attempt'] == 2 and data['reviewer_authenticated']
        assert data['professional_credential_verified'] is False and data['model_input_eligible'] is False
        assert data['current_mri_replaced'] is False and data['inference_performed'] is False
        assert scheduled == [job_id]
        stale = client.post(f"{url}/{job_id}/retry", json={'expected_attempt': 1})
        assert stale.status_code == 409
    finally:
        app.dependency_overrides.pop(require_doctor, None)
