"""Actual localhost HTTP and real synthetic Part10 conversion, never Orthanc."""
import base64,copy,hashlib,json,subprocess,sys,threading,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest
from app.services.dicom_conversion import convert_and_verify
from app.services.dicom_conversion_source import check_conversion_sources
from app.services.pacs_client import PacsConfig
from test_dicom_conversion import files_fixture

SECRET='SYNTHETIC-SERVER-SECRET-DO-NOT-EXPOSE'
def resource_id(uid):
    value=hashlib.sha1(uid.encode()).hexdigest()
    return '-'.join(value[i:i+8] for i in range(0,40,8))


@pytest.fixture
def source_archive(tmp_path):
    proposal,snapshots,files,_=files_fixture(tmp_path,negative=True,scaled=True)
    series={row['series_uid']:row for row in snapshots['series']}
    metadata={row['instance_uid']:row['metadata'] for item in series.values() for row in item['instances']}
    uid_by_id={resource_id(uid):uid for uid in metadata}
    series_by_id={resource_id(uid):uid for uid in series}
    study=proposal['assignments'][0]['study_uid'];study_id=resource_id(study)
    fixture={'mode':'normal','calls':[],'file_reads':{},'system_reads':0,'metadata_reads':0,
             'system':{'Version':'SYNTHETIC-PROTOCOL-ONLY','DatabaseServerIdentifier':'SYNTHETIC-PIN',
                       'OverwriteInstances':False,'OverwriteInstancesMode':'Never','IngestTranscoding':'','ReadOnly':False}}
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'
        def log_message(self,*_args):pass
        def reply(self,value,status=200,mime='application/json'):
            body=value if isinstance(value,bytes) else json.dumps(value).encode()
            self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)))
            self.end_headers();self.wfile.write(body)
        def authorized(self):
            expected='Basic '+base64.b64encode(('test-user:'+SECRET).encode()).decode()
            return self.headers.get('Authorization')==expected
        def do_GET(self):
            path=urlsplit(self.path).path;fixture['calls'].append(('GET',path))
            if not self.authorized():self.reply({},401);return
            if path=='/system':
                fixture['system_reads']+=1;data=copy.deepcopy(fixture['system'])
                if fixture['mode']=='changed_pin' and fixture['system_reads']>4:data['DatabaseServerIdentifier']='CHANGED'
                self.reply(data);return
            if path.startswith('/dicom-web/'):
                key=path.split('/series/')[1].split('/')[0]; rows=copy.deepcopy(series[key]['instances'])
                if fixture['mode']=='metadata_stale':rows[0]['metadata']['00281050']={'vr':'DS','Value':[123]}
                if fixture['mode']=='late_metadata' and fixture['file_reads']:
                    rows[0]['metadata']['00281050']={'vr':'DS','Value':[123]}
                values=[row['metadata'] for row in rows]
                if path.endswith('/metadata'):fixture['metadata_reads']+=1
                if fixture['mode']=='extra_uid' and path.endswith('/instances'):
                    extra=copy.deepcopy(values[0]);extra['00080018']['Value']=['2.25.9999999'];values.append(extra)
                self.reply(values,mime='application/dicom+json');return
            resource=path.split('/')[2]
            if path.startswith('/instances/'):
                uid=uid_by_id[resource]; item=metadata[uid];parent=item['0020000E']['Value'][0]
                if path.endswith('/file'):
                    fixture['file_reads'][uid]=fixture['file_reads'].get(uid,0)+1
                    if fixture['mode']=='file_missing':self.reply({},404);return
                    raw=Path(files[uid]['path']).read_bytes()
                    if fixture['mode']=='drip':
                        self.send_response(200);self.send_header('Content-Type','application/dicom');self.send_header('Content-Length',str(len(raw)));self.end_headers()
                        try:
                            for byte in raw:
                                self.wfile.write(bytes([byte]));self.wfile.flush();time.sleep(.01)
                        except (BrokenPipeError,ConnectionResetError):pass
                        return
                    if fixture['mode']=='bytes_conflict' or (fixture['mode']=='second_pass_bytes' and fixture['file_reads'][uid]>1):
                        raw=raw[:-1]+bytes([raw[-1]^1])
                    self.reply(raw,mime='application/dicom');return
                self.reply({'ID':resource,'Type':'Instance','MainDicomTags':{'SOPInstanceUID':uid},'ParentSeries':resource_id(parent)});return
            if path.startswith('/series/'):
                uid=series_by_id[resource]
                self.reply({'ID':resource,'Type':'Series','MainDicomTags':{'SeriesInstanceUID':uid},'ParentStudy':study_id});return
            if path.startswith('/studies/'):
                self.reply({'ID':resource,'Type':'Study','MainDicomTags':{'StudyInstanceUID':study},'PatientMainDicomTags':{'PatientName':'PRIVATE_NEVER_EXPOSE'}});return
            self.reply({},404)
        def do_POST(self):
            path=urlsplit(self.path).path;uid=self.rfile.read(int(self.headers.get('Content-Length','0'))).decode()
            fixture['calls'].append(('POST',path))
            if not self.authorized():self.reply({},401);return
            assert path=='/tools/lookup'  # Read-only UID lookup, never import.
            resource=resource_id(uid)
            self.reply([] if fixture['mode']=='absent' else [{'ID':resource,'Type':'Instance','Path':'/instances/'+resource}])
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    config=PacsConfig(format_version=1,archive_id=proposal['archive_id'],base_url=f'http://127.0.0.1:{server.server_port}',
                      username='test-user',password=SECRET,allow_pixel_read=True,expected_database_server_identifier='SYNTHETIC-PIN')
    proposal['archive_fingerprint']=config.endpoint_fingerprint
    for row in snapshots['series']:row['archive_fingerprint']=config.endpoint_fingerprint
    directory=tmp_path/'version';convert_and_verify(proposal,snapshots,files,directory)
    sha=hashlib.sha256((directory/'conversion-report.json').read_bytes()).hexdigest()
    fixture.update(config=config,proposal=proposal,snapshots=snapshots,files=files,directory=directory,sha=sha)
    yield fixture
    server.shutdown();server.server_close();thread.join(timeout=2)


def checked(fixture):
    result=check_conversion_sources(fixture['directory'],fixture['sha'],fixture['proposal'],fixture['snapshots'],fixture['config'])
    assert SECRET not in json.dumps(result) and 'PRIVATE_NEVER_EXPOSE' not in json.dumps(result)
    assert not result['model_input_eligible'] and not result['current_mri_replaced'] and not result['archive_written']
    assert not result['reviewer_authenticated'] and not result['database_identity_cryptographically_verified']
    assert not any(method=='POST' and path!='/tools/lookup' for method,path in fixture['calls'])
    return result


def test_two_pass_whole_conversion_actual_HTTP_readonly_and_originals_unchanged(source_archive):
    fixture=source_archive
    before={path:Path(path).read_bytes() for path in [row['path'] for row in fixture['files'].values()]}
    result=checked(fixture)
    assert result['status']=='matched_at_check' and result['live_archive_reconciled']
    assert result['archive_observation_scope']=='synthetic_protocol_only' and result['instances_checked']==12
    assert result['raw_byte_passes']==2 and set(fixture['file_reads'].values())=={2}
    assert result['total_raw_bytes_observed']==sum(len(raw) for raw in before.values())*2
    assert fixture['metadata_reads']==24  # Two internal metadata reads, 4 roles, 3 stages.
    assert {path:Path(path).read_bytes() for path in before}==before


@pytest.mark.parametrize('mode,reason',[
    ('metadata_stale','conversion_archive_metadata_stale'),('extra_uid','series_instance_set_mismatch'),
    ('bytes_conflict','archive_content_conflict'),('second_pass_bytes','archive_content_conflict'),
    ('late_metadata','conversion_archive_metadata_stale'),('changed_pin','archive_identity_mismatch'),
    ('absent','conversion_archive_instance_missing'),('file_missing','archive_file_unresolved')])
def test_source_change_or_missing_never_reuses_local_success(source_archive,mode,reason):
    source_archive['mode']=mode
    result=checked(source_archive)
    assert result['status'] in ('stale','unavailable') and result['reason']==reason
    assert result['live_archive_reconciled'] is False
    if mode in ('metadata_stale','extra_uid'):assert not source_archive['file_reads']


@pytest.mark.parametrize('mode,reason',[
    ('target','conversion_archive_target_mismatch'),('pixels','pixel_read_disabled'),('pin','archive_identity_unpinned')])
def test_target_permissions_and_pin_checked_before_network(source_archive,mode,reason):
    config=source_archive['config']
    change={'archive_id':'other'} if mode=='target' else {'allow_pixel_read':False} if mode=='pixels' else {'expected_database_server_identifier':None}
    if mode=='pin':
        # Update current plan context to this unpinned config; still refuses before network.
        changed=config.model_copy(update=change)
        source_archive['proposal']['archive_fingerprint']=changed.endpoint_fingerprint
        for row in source_archive['snapshots']['series']:row['archive_fingerprint']=changed.endpoint_fingerprint
    source_archive['config']=config.model_copy(update=change)
    result=checked(source_archive)
    assert result['reason']==reason and not source_archive['calls']


def test_deadline_refuses_before_first_archive_request(source_archive,monkeypatch):
    import app.services.dicom_conversion_source as service
    monkeypatch.setattr(service,'MAX_CHECK_SECONDS',0)
    result=checked(source_archive)
    assert result['reason']=='conversion_source_check_timeout' and not source_archive['calls']


def test_deadline_interrupts_actual_slow_byte_stream(source_archive,monkeypatch):
    import app.services.dicom_conversion_source as service
    monkeypatch.setattr(service,'MAX_CHECK_SECONDS',2)
    source_archive['mode']='drip';started=time.monotonic()
    result=checked(source_archive)
    assert result['reason']=='conversion_source_check_timeout' and not result['live_archive_reconciled']
    assert time.monotonic()-started<4 and source_archive['file_reads']


def test_real_cli_private_config_saved_receipt_no_overwrite(source_archive,tmp_path):
    fixture=source_archive;paths={}
    for key,value in [('proposal',fixture['proposal']),('snapshots',fixture['snapshots']),('pacs',fixture['config'].model_dump(mode='json'))]:
        if key=='pacs':value['password']=SECRET
        path=tmp_path/(key+'.json');path.write_text(json.dumps(value),encoding='utf-8');paths[key]=path
    tool=Path(__file__).resolve().parents[1]/'tools/check_dicom_conversion_source.py';output=tmp_path/'receipt.json'
    args=[sys.executable,str(tool),'--proposal',str(paths['proposal']),'--snapshots',str(paths['snapshots']),
          '--pacs-config',str(paths['pacs']),'--version-dir',str(fixture['directory']),'--report-sha256',fixture['sha'],'--output',str(output)]
    result=subprocess.run(args,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    assert SECRET not in result.stdout+result.stderr
    assert json.loads(output.read_text(encoding='utf-8'))['status']=='matched_at_check'
    assert subprocess.run(args,capture_output=True,text=True).returncode==2


def test_registered_source_check_route_reconciles_without_activating_model(source_archive,tmp_path,monkeypatch):
    """Exercise registry, case/archive binding, route, and live read-only check together."""
    import app.api.pacs as api
    from fastapi.testclient import TestClient
    from app.core.config import settings
    from app.database import SessionLocal
    from app.main import app
    from app.models.case import Case
    from app.models.patient import Patient
    from app.models.pacs import PACSStudyLink
    from app.services.dicom_conversion import convert_and_verify

    fixture=source_archive
    proposal=copy.deepcopy(fixture['proposal']);snapshots=copy.deepcopy(fixture['snapshots'])
    with SessionLocal() as db:
        patient=Patient(name='SYNTHETIC source route test',age=40,gender='other')
        db.add(patient);db.flush();patient_id=patient.id
        case=Case(patient_id=patient.id,description='SYNTHETIC source route',status='created')
        db.add(case);db.flush();case_id=case.id
        study=proposal['assignments'][0]['study_uid']
        db.add(PACSStudyLink(case_id=case_id,archive_id=fixture['config'].archive_id,
            study_uid=study,endpoint_fingerprint=fixture['config'].endpoint_fingerprint,
            metadata_sha256='0'*64,metadata_json='{}'))
        db.commit()

    proposal.update(case_id=case_id,data_role='dicom-metadata-snapshot')
    snapshots['data_role']='dicom-metadata-snapshot'
    for row in snapshots['series']:
        row.update(source_case_id=case_id,archive_id=fixture['config'].archive_id,
                   archive_fingerprint=fixture['config'].endpoint_fingerprint)
    directory=tmp_path/'registered-route-version'
    convert_and_verify(proposal,snapshots,fixture['files'],directory)
    proposal_path=tmp_path/'registered-route-proposal.json'
    snapshots_path=tmp_path/'registered-route-snapshots.json'
    proposal_path.write_text(json.dumps(proposal),encoding='utf-8')
    snapshots_path.write_text(json.dumps(snapshots),encoding='utf-8')
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    entry={'version_id':'registered-route-version','case_id':case_id,
        'archive_id':fixture['config'].archive_id,
        'archive_fingerprint':fixture['config'].endpoint_fingerprint,'study_uid':study,
        'version_dir':str(directory),'report_sha256':sha(directory/'conversion-report.json'),
        'proposal_path':str(proposal_path),'proposal_sha256':sha(proposal_path),
        'snapshots_path':str(snapshots_path),'snapshots_sha256':sha(snapshots_path)}
    index=tmp_path/'registered-route-index.json'
    index.write_text(json.dumps({'format':'dicom-conversion-index-v1','entries':[entry]}),encoding='utf-8')
    monkeypatch.setattr(settings,'DICOM_CONVERSION_INDEX_FILE',str(index))
    monkeypatch.setattr(api,'load_config',lambda:fixture['config'])

    candidate_hashes={uid:hashlib.sha256(Path(record['path']).read_bytes()).hexdigest()
                      for uid,record in fixture['files'].items()}
    with SessionLocal() as db:
        before=(db.get(Case,case_id).status,db.query(PACSStudyLink).filter_by(case_id=case_id).count())
    url=f"/pacs/cases/{case_id}/conversions/registered-route-version/source-check"
    response=TestClient(app).get(url)
    data=response.json()['data']
    assert response.status_code==200 and response.headers['cache-control']=='no-store'
    assert data['status']=='matched_at_check' and data['live_archive_reconciled']
    assert data['instances_checked']==12 and data['raw_byte_passes']==2
    assert not data['model_input_eligible'] and not data['current_mri_replaced']
    assert not data['reviewer_authenticated'] and not data['archive_written']
    assert SECRET not in response.text and 'PRIVATE_NEVER_EXPOSE' not in response.text
    assert not any(method=='POST' and path!='/tools/lookup' for method,path in fixture['calls'])
    assert fixture['file_reads'] and set(fixture['file_reads'].values())=={2}
    assert candidate_hashes=={uid:hashlib.sha256(Path(record['path']).read_bytes()).hexdigest()
                              for uid,record in fixture['files'].items()}
    with SessionLocal() as db:
        after=(db.get(Case,case_id).status,db.query(PACSStudyLink).filter_by(case_id=case_id).count())
        db.query(PACSStudyLink).filter_by(case_id=case_id).delete()
        db.query(Case).filter_by(id=case_id).delete()
        db.query(Patient).filter_by(id=patient_id).delete();db.commit()
    assert after==before
