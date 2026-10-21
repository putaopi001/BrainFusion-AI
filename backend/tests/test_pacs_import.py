"""Synthetic classic MR + actual local HTTP protocol; no real archive/cohort."""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fastapi.testclient import TestClient
import pydicom
import pytest

from app.main import app
from app.core.config import settings
from app.services import pacs_import as service
from app.services.dicom_viewing_derivative import prepare_series, PROFILE
from test_dicom_conversion import files_fixture

client=TestClient(app)
SECRET='SYNTHETIC-IMPORT-ONLY'


@pytest.fixture
def archive(tmp_path,monkeypatch):
    fixture=dict(stored={},posts=0,entered=threading.Event(),release=threading.Event(),mode='normal')
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_): pass
        def reply(self,status,value,binary=False):
            raw=value if binary else json.dumps(value).encode()
            self.send_response(status);self.send_header('Content-Type','application/octet-stream' if binary else 'application/json')
            self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def authorized(self):
            token='Basic '+base64.b64encode(('synthetic:'+SECRET).encode()).decode()
            if self.headers.get('Authorization')!=token:
                self.reply(401,{});return False
            return True
        def do_GET(self):
            if not self.authorized():return
            if self.path=='/system':self.reply(200,dict(Version='1.13.0',DatabaseServerIdentifier=fixture.get('identity','SYNTHETIC-IMPORT-ARCHIVE')))
            elif self.path.endswith('/file'):
                value=fixture['stored'].get(self.path.split('/')[2])
                self.reply(200,value if fixture['mode']!='bad_readback' else b'wrong bytes',True)
            else:self.reply(404,{})
        def do_POST(self):
            if not self.authorized():return
            fixture['posts']+=1
            raw=self.rfile.read(int(self.headers['Content-Length']))
            if fixture['mode']=='hold' and fixture['posts']==1:
                fixture['entered'].set();fixture['release'].wait(5)
            if fixture.get('fail_on')==fixture['posts']:
                self.reply(500,{'message':SECRET});return
            ds=pydicom.dcmread(io.BytesIO(raw))
            key=hashlib.sha1(str(ds.SOPInstanceUID).encode()).hexdigest()
            key='-'.join(key[i:i+8] for i in range(0,40,8))
            status='AlreadyStored' if key in fixture['stored'] else 'Success'
            fixture['stored'].setdefault(key,raw)
            self.reply(200,dict(ID=key,Status=status))
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    config=tmp_path/'pacs.json'
    config.write_text(json.dumps(dict(format_version=1,archive_id='synthetic',base_url=f'http://127.0.0.1:{server.server_port}',
        username='synthetic',password=SECRET,expected_database_server_identifier='SYNTHETIC-IMPORT-ARCHIVE')),encoding='utf-8')
    monkeypatch.setattr(settings,'PACS_CONFIG_FILE',str(config))
    monkeypatch.setattr(settings,'PACS_IMPORT_REGISTRY_FILE',str(tmp_path/'registry.json'))
    monkeypatch.setattr(settings,'PACS_IMPORT_JOBS_DIR',str(tmp_path/'jobs'))
    monkeypatch.setattr(service,'DATA_ROOT',tmp_path/'derived')
    yield fixture
    fixture['release'].set();server.shutdown();server.server_close();thread.join(2)


@pytest.fixture
def registered(tmp_path,archive):
    _,_,files,_=files_fixture(tmp_path)
    source=tmp_path/'source';source.mkdir()
    for index,record in enumerate(list(files.values())[:3]):shutil.copy2(record['path'],source/f'{index}.dcm')
    directory=tmp_path/'derived'/'synthetic'
    manifest=prepare_series(source,directory,'SYNTHETIC-ONLY')
    report=dict(profile=PROFILE,status='prepared_and_verified',license_url='https://creativecommons.org/licenses/by/4.0/',
                ai_activation=False,clinical_deidentification_certified=False,collection_doi='SYNTHETIC-NO-SOURCE')
    service.write_json(directory/'preparation-report.json',report)
    review=tmp_path/'synthetic-review.txt';review.write_text('Synthetic fixture only, no clinical review',encoding='utf-8')
    row=dict(candidate_id='a'*64,label='SYNTHETIC fixture',directory=str(directory),review_record=str(review),
             manifest_sha256=service.digest((directory/'derivative-manifest.json').read_bytes()),
             report_sha256=service.digest((directory/'preparation-report.json').read_bytes()),review_sha256=service.digest(review.read_bytes()),
             instance_count=3,study_uid=manifest['study_uid'],series_uid=manifest['series_uid'],collection_doi='SYNTHETIC-NO-SOURCE',license_url=report['license_url'])
    service.write_json(Path(settings.PACS_IMPORT_REGISTRY_FILE),dict(format_version=1,items=[row]))
    archive['row']=row;archive['directory']=directory
    return row


def submit(row):return client.post('/pacs/imports/'+row['candidate_id'],json={'acknowledge_reviewed_local_viewing_only':True})


def test_real_protocol_upload_readback_duplicate_and_persistent_status(archive,registered):
    first=submit(registered)
    assert first.status_code==200,first.text
    assert first.json()['data']['state']=='succeeded' and first.json()['data']['stored_new']==3
    second=submit(registered).json()['data']
    assert second['verified']==3 and second['already_stored']==3 and second['stored_new']==0
    assert len(archive['stored'])==3 and archive['posts']==6
    response=client.get('/pacs/import-candidates')
    assert response.json()['data']['items'][0]['latest_import']==second
    assert str(archive['directory']) not in response.text and SECRET not in response.text
    assert response.headers['cache-control']=='no-store'
    service.recover_interrupted()
    assert client.get('/pacs/imports/'+registered['candidate_id']).json()['data']==second


@pytest.mark.parametrize('change,reason',[('bytes','import_file_changed'),('review','import_review_changed'),('report','import_candidate_changed')])
def test_changed_pinned_material_refuses_before_any_upload(archive,registered,change,reason):
    directory=archive['directory']
    path=next((directory/'instances').glob('*.dcm')) if change=='bytes' else Path(registered['review_record']) if change=='review' else directory/'preparation-report.json'
    path.write_bytes(path.read_bytes()+b'changed')
    response=submit(registered)
    assert response.status_code==409 and response.json()['detail']['reason']==reason
    assert archive['posts']==0 and not list(Path(settings.PACS_IMPORT_JOBS_DIR).glob('*/state.json'))


def test_partial_failure_retries_with_dedup_and_no_secret_error(archive,registered):
    archive['fail_on']=2
    failed=submit(registered)
    assert failed.json()['data']['state']=='failed' and failed.json()['data']['verified']==1
    assert SECRET not in failed.text
    archive.pop('fail_on')
    retried=submit(registered).json()['data']
    assert retried['state']=='succeeded' and retried['already_stored']==1 and retried['stored_new']==2
    assert len(list(Path(settings.PACS_IMPORT_JOBS_DIR).glob('*/state.json')))==2


def test_archive_readback_corruption_never_reports_success(archive,registered):
    archive['mode']='bad_readback'
    state=submit(registered).json()['data']
    assert state['state']=='failed' and state['verified']==0 and state['error_reason']=='import_stored_bytes_mismatch'


def test_overlapping_requests_share_running_job_and_os_lock(archive,registered):
    archive['mode']='hold'
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(submit,registered)
        assert archive['entered'].wait(3)
        duplicate=submit(registered)
        assert duplicate.status_code==200 and duplicate.json()['data']['state']=='running'
        assert archive['posts']==1
        # Recovery while a real lock is held cannot mark the active job interrupted.
        service.recover_interrupted()
        assert service.current(registered['candidate_id'])['state']=='running'
        archive['release'].set()
        finished=future.result(timeout=5).json()['data']
    assert finished['id']==duplicate.json()['data']['id'] and finished['state']=='succeeded'
    assert archive['posts']==3


def test_interrupted_job_is_explicit_and_retry_preserves_receipt(archive,registered):
    completed=submit(registered).json()['data']
    path=Path(settings.PACS_IMPORT_JOBS_DIR)/completed['id']/'state.json'
    state=json.loads(path.read_text());state['state']='running';service.write_json(path,state)
    service.recover_interrupted()
    recovered=client.get('/pacs/imports/'+registered['candidate_id']).json()['data']
    assert recovered['state']=='failed' and recovered['error_reason']=='import_interrupted'
    assert recovered['verified']==3
    assert submit(registered).json()['data']['already_stored']==3


def test_unknown_candidate_ack_and_browser_path_injection_are_rejected(archive,registered):
    assert client.post('/pacs/imports/'+'b'*64,json={'acknowledge_reviewed_local_viewing_only':True}).status_code==404
    assert client.post('/pacs/imports/'+registered['candidate_id'],json={'acknowledge_reviewed_local_viewing_only':False}).status_code==422
    assert client.post('/pacs/imports/'+registered['candidate_id'],json={'acknowledge_reviewed_local_viewing_only':True,'directory':'E:/other'}).status_code==422
    assert archive['posts']==0


@pytest.mark.skipif(os.name!='nt',reason='Actual Windows file sharing regression')
def test_atomic_receipt_update_tolerates_real_windows_reader_handle(tmp_path):
    path=tmp_path/'state.json'
    service.write_json(path,{'verified':1})
    entered=threading.Event()
    def writer():
        entered.set();service.write_json(path,{'verified':2})
    with ThreadPoolExecutor(max_workers=1) as pool:
        with path.open('rb') as reader:
            future=pool.submit(writer)
            assert entered.wait(1)
            time.sleep(.05)
            assert json.loads(reader.read())=={'verified':1}
            assert not future.done()
        future.result(timeout=2)
    assert service.read_json(path)=={'verified':2}


def test_corrupt_receipt_is_retained_without_crashing_recovery_or_claiming_success(archive,registered):
    path=Path(settings.PACS_IMPORT_JOBS_DIR)/'invalid'/'state.json'
    path.parent.mkdir(parents=True);path.write_bytes(b'{"state":false}')
    with pytest.warns(UserWarning,match='receipt unreadable'):
        service.recover_interrupted()
    response=client.get('/pacs/imports/'+registered['candidate_id'])
    assert response.status_code==409 and response.json()['detail']['reason']=='import_state_invalid'
    assert path.read_bytes()==b'{"state":false}' and archive['posts']==0
