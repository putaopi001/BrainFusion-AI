"""Synthetic web workflow tests: case binding, checked plans, original capture and cleanup."""
import copy
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import dicom_web_plan as web
from app.services.dicom_conversion import source_dataset
from app.services.dicom_input_plan import ROLES, validate_plan
from test_dicom_conversion import files_fixture
from test_dicom_input_plan import inputs


def _context():
    return SimpleNamespace(archive_id='synthetic-archive', endpoint_fingerprint='1' * 64,
        allow_pixel_read=True, expected_database_server_identifier='SYNTHETIC-pinned')


class FakeArchive:
    def __init__(self, config, byte_files=None):
        self.config = config
        self.byte_files = byte_files or {}
        self.http = SimpleNamespace(stream=self.stream)
        self.lookups = []

    def __enter__(self): return self
    def __exit__(self, *_): return None
    def _check_system(self, *_): return None
    def _json(self, *_a, **_k): return {'DatabaseServerIdentifier': 'SYNTHETIC-pinned'}
    def lookup_instance(self, uid):
        self.lookups.append(uid)
        return uid if uid in self.byte_files else None

    @contextmanager
    def stream(self, method, path, **_kwargs):
        uid = path.rsplit('/', 2)[-2]
        content = self.byte_files[uid]
        response = SimpleNamespace(status_code=200,
            headers={'content-type':'application/dicom','content-encoding':'identity'})
        response.iter_raw = lambda chunk_size: iter(content[i:i+chunk_size] for i in range(0, len(content), chunk_size))
        yield response


def _prepared(monkeypatch, tmp_path):
    proposal, bundle = inputs()
    case_id = 41
    config = _context()
    proposal.update(case_id=case_id, archive_id=config.archive_id,
                    archive_fingerprint=config.endpoint_fingerprint, data_role='dicom-metadata-snapshot')
    bundle['data_role'] = proposal['data_role']
    for snapshot in bundle['series']:
        snapshot.update(source_case_id=case_id, archive_id=config.archive_id,
                        archive_fingerprint=config.endpoint_fingerprint)
    for assignment in proposal['assignments']:
        assignment['evidence']['reviewer_reference'] = 'synthetic-doctor'
    plan = validate_plan(proposal, bundle)
    root = tmp_path / 'plans'
    root.mkdir()
    draft_id = hashlib.sha256(str(tmp_path).encode()).hexdigest()[:32]
    folder = root / draft_id
    folder.mkdir()
    values = {'proposal.json': proposal, 'snapshots.json': bundle,
              'evidence.json': {'basis':'local_manual_review','reference':'SYNTHETIC-fixture-only'}}
    hashes = {}
    for name, value in values.items():
        raw = json.dumps(value, ensure_ascii=False).encode()
        (folder / name).write_bytes(raw)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    record = {'format':'dicom-web-plan-v1','draft_id':draft_id,'case_id':case_id,
        'study_uid':proposal['assignments'][0]['study_uid'],'creator_id':'synthetic-doctor',
        'created_utc':'2026-10-18T00:00:00+00:00','expires_at':web.time.time()+600,
        'plan_revision':plan['plan_revision'],'hashes':hashes}
    (folder/'draft.json').write_text(json.dumps(record),encoding='utf-8')
    monkeypatch.setattr(web,'_root',lambda create=False:root)
    identity={'id':'synthetic-doctor','user':{'role':'doctor'}}
    return proposal,bundle,plan,record,folder,root,identity,config


def test_preview_reads_case_scoped_manifests_and_persists_hash_bound_declaration(tmp_path, monkeypatch):
    proposal,bundle,_,_,_,root,identity,config=_prepared(monkeypatch,tmp_path)
    # Preview writes a fresh draft after deriving all four manifests from the archive.
    shutil = __import__('shutil')
    shutil.rmtree(root / ('a'*32),ignore_errors=True)
    manifest_by_uid={row['series_uid']:row for row in bundle['series']}
    monkeypatch.setattr(web,'BudgetClient',lambda *_:FakeArchive(config))
    monkeypatch.setattr(web,'_source_snapshot',lambda _archive,case,study,series:
        copy.deepcopy(manifest_by_uid[series]))
    monkeypatch.setattr(web,'_same_context',lambda *_:None)
    result=web.preview(41,web.Preview(study_uid=proposal['assignments'][0]['study_uid'],
        assignments=[{'role':row['role'],'series_uid':row['series_uid']} for row in proposal['assignments']],
        evidence_basis='local_manual_review',evidence_text='SYNTHETIC.protocol.v1'),identity,config,lambda:config)
    draft=root/result['draft_id']
    record=json.loads((draft/'draft.json').read_text())
    assert result['metadata_geometry_contract_passed'] and result['source_bytes_captured'] is False
    assert result['model_input_eligible'] is False and result['inference_performed'] is False
    assert set(record['hashes'])=={'proposal.json','snapshots.json','evidence.json'}
    evidence=json.loads((draft/'evidence.json').read_text())
    assert evidence['reference']=='SYNTHETIC.protocol.v1' and 'path' not in evidence
    assert not list(draft.glob('*.dcm'))


def test_preview_persists_explicit_resampling_policy_and_reports_source_grids(tmp_path,monkeypatch):
    proposal,bundle=inputs('spacing')
    config=_context();case_id=41
    proposal.update(case_id=case_id,archive_id=config.archive_id,
                    archive_fingerprint=config.endpoint_fingerprint,data_role='dicom-metadata-snapshot')
    bundle['data_role']=proposal['data_role']
    for snapshot in bundle['series']:
        snapshot.update(source_case_id=case_id,archive_id=config.archive_id,
                        archive_fingerprint=config.endpoint_fingerprint)
    manifest_by_uid={row['series_uid']:row for row in bundle['series']}
    root=tmp_path/'resampling-plans';root.mkdir()
    monkeypatch.setattr(web,'_root',lambda create=False:root)
    monkeypatch.setattr(web,'BudgetClient',lambda *_:FakeArchive(config))
    monkeypatch.setattr(web,'_source_snapshot',lambda _archive,case,study,series:
        copy.deepcopy(manifest_by_uid[series]))
    monkeypatch.setattr(web,'_same_context',lambda *_:None)
    identity={'id':'synthetic-doctor','user':{'role':'doctor'}}
    result=web.preview(41,web.Preview(study_uid=proposal['assignments'][0]['study_uid'],
        assignments=[{'role':row['role'],'series_uid':row['series_uid']} for row in proposal['assignments']],
        evidence_basis='local_manual_review',evidence_text='SYNTHETIC.protocol.v1',
        resample_to_t1c_1mm=True),identity,config,lambda:config)
    draft=root/result['draft_id']
    saved=json.loads((draft/'proposal.json').read_text(encoding='utf-8'))
    assert result['resampling_applied'] is True
    assert result['resampling']['reference_role']=='t1c'
    assert result['dimensions']==[3,2,3] and result['spacing_xyz_mm']==[1,1,1]
    assert result['source_geometries']['t1c']['spacing_xyz_mm']==[1.2,1.0,1.0]
    assert saved['resampling']==result['resampling']
    assert result['model_input_eligible'] is False and result['inference_performed'] is False


def test_create_captures_only_verified_archive_bytes_and_is_idempotent(tmp_path,monkeypatch):
    _,bundle,plan,record,folder,_,identity,config=_prepared(monkeypatch,tmp_path)
    _,_,files,_=files_fixture(tmp_path)
    byte_files={uid:Path(item['path']).read_bytes() for uid,item in files.items()}
    archive=FakeArchive(config,byte_files)
    monkeypatch.setattr(web,'BudgetClient',lambda *_:archive)
    monkeypatch.setattr(web,'_check_manifests',lambda *_:None)
    monkeypatch.setattr(web,'_same_context',lambda *_:None)
    monkeypatch.setattr(web,'source_dataset',source_dataset)
    result=web.create(41,web.Create(draft_id=record['draft_id'],plan_revision=record['plan_revision'],acknowledge_roles=True),identity,config,lambda:config)
    assert result['state']=='queued' and result['registered'] is False
    assert result['model_input_eligible'] is False and result['inference_performed'] is False
    assert len(archive.lookups)==sum(len(row['instances']) for row in plan['sources'].values())
    job=json.loads((web.jobs._job_file(record['draft_id'])).read_text())
    source_map=json.loads(Path(job['inputs']['source_files']['path']).read_text())
    assert set(source_map)==set(archive.lookups)
    assert all(Path(row['path']).is_file() and hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()==row['sha256'] for row in source_map.values())
    assert str(folder) not in json.dumps(result)
    repeated=web.create(41,web.Create(draft_id=record['draft_id'],plan_revision=record['plan_revision'],acknowledge_roles=True),identity,config,lambda:config)
    assert repeated['already_created'] is True and repeated['job_id']==result['job_id']
    import shutil
    shutil.rmtree(web.jobs._root()/record['draft_id'],ignore_errors=True)
    shutil.rmtree(folder,ignore_errors=True)


def test_create_removes_partial_capture_and_never_queues_when_dicom_mismatch(tmp_path,monkeypatch):
    _,bundle,plan,record,folder,_,identity,config=_prepared(monkeypatch,tmp_path)
    _,_,files,_=files_fixture(tmp_path)
    byte_files={uid:Path(item['path']).read_bytes() for uid,item in files.items()}
    monkeypatch.setattr(web,'BudgetClient',lambda *_:FakeArchive(config,byte_files))
    monkeypatch.setattr(web,'_check_manifests',lambda *_:None)
    monkeypatch.setattr(web,'_same_context',lambda *_:None)
    monkeypatch.setattr(web,'source_dataset',lambda *_: (_ for _ in ()).throw(web.fail('synthetic_mismatch','Synthetic mismatch')))
    payload=web.Create(draft_id=record['draft_id'],plan_revision=record['plan_revision'],acknowledge_roles=True)
    with pytest.raises(ValueError): web.create(41,payload,identity,config,lambda:config)
    assert not (web.jobs._root()/record['draft_id']/'job.json').exists()
    assert not list(folder.glob('capture-*'))




def test_preview_api_requires_doctor_csrf_case_link_and_rejects_client_paths(tmp_path, monkeypatch):
    import json as json_module
    from fastapi.testclient import TestClient
    from app.core.config import settings
    from app.database import SessionLocal
    from app.models.case import Case
    from app.models.patient import Patient
    from app.models.pacs import PACSStudyLink
    from app.services import local_auth
    from app.services.pacs_client import PacsConfig
    import app.api.pacs as api
    from app.main import app

    account_file=tmp_path/'users.json'
    password='SYNTHETIC-only-strong-password'
    users=[{'id':'a'*32,'username':'doctor-web','display_name':'SYNTHETIC doctor','role':'doctor','disabled':False,'password_hash':local_auth.hash_password(password)},
           {'id':'b'*32,'username':'research-web','display_name':'SYNTHETIC researcher','role':'researcher','disabled':False,'password_hash':local_auth.hash_password(password)}]
    account_file.write_text(json_module.dumps({'format_version':1,'users':users}),encoding='utf-8')
    monkeypatch.setattr(settings,'LOCAL_AUTH_FILE',str(account_file))
    with local_auth._lock: local_auth._sessions.clear(); local_auth._failures.clear()
    config=PacsConfig(format_version=1,archive_id='SYNTHETIC-web',base_url='http://127.0.0.1:9898',
        username='protocol-only',password='test',expected_database_server_identifier='SYNTHETIC',allow_pixel_read=True)
    with SessionLocal() as db:
        patient=Patient(name='SYNTHETIC web plan',age=40,gender='other');db.add(patient);db.flush();patient_id=patient.id
        case=Case(patient_id=patient.id,description='SYNTHETIC web plan',status='created');db.add(case);db.flush();case_id=case.id
        db.add(PACSStudyLink(case_id=case_id,archive_id=config.archive_id,study_uid='2.25.88',
            endpoint_fingerprint=config.endpoint_fingerprint,metadata_sha256='0'*64,metadata_json='{}'));db.commit()
    monkeypatch.setattr(api,'load_config',lambda:config)
    monkeypatch.setattr(api.dicom_web_plan,'preview',lambda case,payload,identity,config,verify:{
        'draft_id':'e'*32,'plan_revision':'f'*64,'metadata_geometry_contract_passed':True,
        'resampling_applied':False,
        'source_bytes_captured':False,'model_input_eligible':False,'current_mri_replaced':False,
        'inference_performed':False})
    body={'study_uid':'2.25.88','assignments':[{'role':role,'series_uid':'2.25.'+str(i+100)} for i,role in enumerate(ROLES)],
        'evidence_basis':'local_manual_review','evidence_text':'SYNTHETIC.protocol.v1'}
    client=TestClient(app)
    url=f"/pacs/cases/{case_id}/conversion-plans/preview"
    try:
        assert client.post(url,json=body).status_code==401
        response=client.post('/local-auth/login',json={'username':'research-web','password':password})
        state=client.get('/local-auth/session').json()['data']
        assert client.post(url,json=body,headers={'X-BF-CSRF':state['csrf']}).status_code==403
        response=client.post('/local-auth/login',json={'username':'doctor-web','password':password})
        state=client.get('/local-auth/session').json()['data']
        assert client.post(url,json=body,headers={'X-BF-CSRF':'wrong'}).status_code==403
        response=client.post(url,json={**body,'source_path':'E:/client/path'},headers={'X-BF-CSRF':state['csrf']})
        assert response.status_code==422,response.text
        response=client.post(url,json=body,headers={'X-BF-CSRF':state['csrf']})
        assert response.status_code==200,response.text
        data=response.json()['data']
        assert data['draft_id']=='e'*32 and data['source_bytes_captured'] is False
        assert data['model_input_eligible'] is False and data['inference_performed'] is False
        assert 'E:/client/path' not in response.text and response.headers['cache-control']=='no-store'
    finally:
        with local_auth._lock: local_auth._sessions.clear(); local_auth._failures.clear()
        with SessionLocal() as db:
            db.query(PACSStudyLink).filter_by(case_id=case_id).delete()
            db.query(Case).filter_by(id=case_id).delete()
            db.query(Patient).filter_by(id=patient_id).delete();db.commit()

