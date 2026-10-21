"""Real TCP tests with explicitly SYNTHETIC archive protocol, never Orthanc."""
import base64
import copy
import hashlib
import json
import socket
import os
import subprocess
import sys
import threading
from pathlib import Path
from uuid import uuid4
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest
from app.services.pacs_client import PacsConfig
from app.services.pacs_reconcile import reconcile_archive_instance
from app.services import dicom_custody
from test_dicom_preflight import candidate

INSTANCE_ID='1'*8+'-'+'2'*8+'-'+'3'*8+'-'+'4'*8+'-'+'5'*8
SERIES_ID='a'*8+'-'+'b'*8+'-'+'c'*8+'-'+'d'*8+'-'+'e'*8
STUDY_ID='6'*8+'-'+'7'*8+'-'+'8'*8+'-'+'9'*8+'-'+'0'*8
SECRET='SYNTHETIC-CREDENTIAL-NEVER-LOG'
RAW=b'\0'*128+b'DICM'+b'SYNTHETIC-BYTES-NOT-A-DICOM-COHORT'
BINDING={'study_uid':'2.25.101','series_uid':'2.25.102','sop_uid':'2.25.103',
         'source_sha256':hashlib.sha256(RAW).hexdigest(),'source_bytes':len(RAW)}


@pytest.fixture
def archive():
    fixture={'mode':'normal','calls':[],'system_reads':0,'lookups':0,
             'system':{'Version':'SYNTHETIC-PROTOCOL-ONLY','DatabaseServerIdentifier':'SYNTHETIC-PIN-A',
                       'OverwriteInstances':False,'OverwriteInstancesMode':'Never','IngestTranscoding':'','ReadOnly':False}}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def auth(self):
            expected='Basic '+base64.b64encode(('protocol-user:'+SECRET).encode()).decode()
            return fixture['mode']=='public' or self.headers.get('Authorization')==expected
        def send(self,value,status=200,mime='application/json'):
            body=value if isinstance(value,bytes) else json.dumps(value).encode()
            self.send_response(status);self.send_header('Content-Type',mime)
            self.send_header('Content-Length',str(len(body)))
            if fixture['mode']=='encoded' and mime=='application/dicom':
                self.send_header('Content-Encoding','gzip')
            self.end_headers();self.wfile.write(body)
        def do_GET(self):
            path=urlsplit(self.path).path
            fixture['calls'].append(('GET',path,None))
            if not self.auth():self.send({},401);return
            if path=='/system':
                fixture['system_reads']+=1
                data=copy.deepcopy(fixture['system'])
                if fixture['mode']=='changed_server' and fixture['system_reads']>1:
                    data['DatabaseServerIdentifier']='SYNTHETIC-PIN-B'
                self.send(data)
            elif path=='/instances/'+INSTANCE_ID:
                data={'ID':INSTANCE_ID,'Type':'Instance','MainDicomTags':{'SOPInstanceUID':BINDING['sop_uid']},
                      'ParentSeries':SERIES_ID}
                if fixture['mode']=='parent_path':data['ParentSeries']='../../system'
                if fixture['mode']=='wrong_sop':data['MainDicomTags']['SOPInstanceUID']='2.25.999'
                self.send(data)
            elif path=='/series/'+SERIES_ID:
                data={'ID':SERIES_ID,'Type':'Series','MainDicomTags':{'SeriesInstanceUID':BINDING['series_uid']},
                      'ParentStudy':STUDY_ID}
                if fixture['mode']=='wrong_series':data['MainDicomTags']['SeriesInstanceUID']='2.25.999'
                self.send(data)
            elif path=='/studies/'+STUDY_ID:
                data={'ID':STUDY_ID,'Type':'Study','MainDicomTags':{'StudyInstanceUID':BINDING['study_uid']},
                      'PatientMainDicomTags':{'PatientName':'PRIVATE_NAME_NEVER_LOG'}}
                if fixture['mode']=='wrong_study':data['MainDicomTags']['StudyInstanceUID']='2.25.999'
                self.send(data)
            elif path=='/instances/'+INSTANCE_ID+'/file':
                mode=fixture['mode']
                if mode=='file_404':self.send({},404);return
                if mode=='disconnect':
                    self.connection.shutdown(socket.SHUT_RDWR);self.connection.close();return
                if mode=='redirect':
                    self.send_response(302);self.send_header('Location','https://example.invalid/'+SECRET)
                    self.end_headers();return
                data=RAW[:-1]+b'X' if mode=='changed_bytes' else RAW
                if mode=='wrong_size':data=RAW+b'X'
                self.send(data,mime='text/html' if mode=='file_html' else 'application/dicom')
            else:self.send({},404)
        def do_POST(self):
            path=urlsplit(self.path).path
            raw=self.rfile.read(int(self.headers.get('Content-Length','0')))
            fixture['calls'].append(('POST',path,raw.decode()))
            if not self.auth():self.send({},401);return
            if path!='/tools/lookup':self.send({},403);return
            fixture['lookups']+=1
            mode=fixture['mode']
            if mode=='lookup_404':self.send({},404);return
            if mode=='lookup_empty_body':self.send(b'');return
            data=[] if mode=='absent' else [{'Type':'Instance','ID':INSTANCE_ID,'Path':'/instances/'+INSTANCE_ID}]
            if mode=='ambiguous':data*=2
            if mode=='bad_id':data[0]['ID']='../system'
            if mode=='external_path':data[0]['Path']='https://example.invalid/'+SECRET
            if mode=='wrong_type':data[0]['Type']='Study'
            if mode=='changed_lookup' and fixture['lookups']>1:data=[]
            self.send(data)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    fixture['config']={'format_version':1,'archive_id':'SYNTHETIC-only','base_url':f'http://127.0.0.1:{server.server_port}',
                       'username':'protocol-user','password':SECRET,'allow_pixel_read':True,
                       'expected_database_server_identifier':'SYNTHETIC-PIN-A'}
    yield fixture
    server.shutdown();server.server_close();thread.join(timeout=2)


def reconcile(archive,binding=None):
    result=reconcile_archive_instance(binding or BINDING,PacsConfig.model_validate(archive['config']))
    assert SECRET not in json.dumps(result) and 'PRIVATE_NAME_NEVER_LOG' not in json.dumps(result)
    assert not result['archive_imported_by_tool'] and not result['upload_allowed']
    assert not any(method=='POST' and path!='/tools/lookup' for method,path,_ in archive['calls'])
    return result


def test_matched_existing_checks_hierarchy_bytes_and_identity_twice(archive):
    result=reconcile(archive)
    assert result['state']=='matched_existing' and result['verified_present_at_check'] is True
    assert result['orthanc_instance_id']==INSTANCE_ID and result['source_sha256']==BINDING['source_sha256']
    assert archive['system_reads']==2 and archive['lookups']==2
    assert all(body==BINDING['sop_uid'] for method,_,body in archive['calls'] if method=='POST')
    assert not result['database_identity_cryptographically_verified']


def test_absence_is_observation_only_never_upload_permission(archive):
    archive['mode']='absent'
    result=reconcile(archive)
    assert result['state']=='absent_at_check' and result['verified_present_at_check'] is False
    assert archive['lookups']==2 and not any(path.endswith('/file') for _,path,_ in archive['calls'])


@pytest.mark.parametrize('mode,reason,state',[
    ('public','archive_auth_required','unresolved'),
    ('lookup_404','archive_lookup_unresolved','unresolved'),
    ('lookup_empty_body','invalid_archive_lookup','unresolved'),
    ('ambiguous','ambiguous_archive_uid','conflict'),
    ('bad_id','invalid_archive_resource','unresolved'),
    ('external_path','invalid_archive_lookup','unresolved'),
    ('wrong_type','invalid_archive_lookup','unresolved'),
    ('parent_path','invalid_archive_resource','unresolved'),
    ('wrong_sop','archive_parent_uid_mismatch','conflict'),
    ('wrong_series','archive_parent_uid_mismatch','conflict'),
    ('wrong_study','archive_parent_uid_mismatch','conflict'),
    ('changed_bytes','archive_content_conflict','conflict'),
    ('wrong_size','archive_content_conflict','conflict'),
    ('file_404','archive_file_unresolved','unresolved'),
    ('disconnect','archive_file_unresolved','unresolved'),
    ('redirect','archive_file_unresolved','unresolved'),
    ('encoded','invalid_archive_file','unresolved'),
    ('file_html','invalid_archive_file','unresolved'),
    ('changed_server','archive_identity_mismatch','unresolved'),
    ('changed_lookup','archive_changed_during_check','unresolved'),
])
def test_failed_check_never_means_missing_or_success(archive,mode,reason,state):
    archive['mode']=mode
    result=reconcile(archive)
    assert result['state']==state and result['reason']==reason
    assert result['verified_present_at_check'] is None


@pytest.mark.parametrize('change,reason',[
    ('unpinned','archive_identity_unpinned'),('pixel_disabled','pixel_read_disabled'),
    ('different_pin','archive_identity_mismatch'),('overwrite','archive_overwrite_enabled'),
    ('overwrite_mode','archive_overwrite_enabled'),('transcoding','archive_transcoding_enabled'),
    ('unknown_transcoding','archive_transcoding_enabled'),('unknown_capability','archive_capabilities_unknown')])
def test_private_target_and_retention_policies(archive,change,reason):
    if change=='unpinned':archive['config'].pop('expected_database_server_identifier')
    elif change=='pixel_disabled':archive['config']['allow_pixel_read']=False
    elif change=='different_pin':archive['config']['expected_database_server_identifier']='different'
    elif change=='overwrite':archive['system']['OverwriteInstances']=True
    elif change=='overwrite_mode':archive['system']['OverwriteInstancesMode']='IfChanged'
    elif change=='transcoding':archive['system']['IngestTranscoding']='1.2.840.10008.1.2'
    elif change=='unknown_transcoding':archive['system'].pop('IngestTranscoding')
    else:archive['system'].pop('ReadOnly')
    result=reconcile(archive)
    assert result['state']=='unresolved' and result['reason']==reason and not archive['lookups']


def test_retry_after_connection_loss_reads_existing_without_resend(archive):
    archive['mode']='disconnect'
    assert reconcile(archive)['state']=='unresolved'
    archive['mode']='normal'
    assert reconcile(archive)['state']=='matched_existing'
    assert not any(path=='/instances' for _,path,_ in archive['calls'])


def test_read_only_archive_can_reconcile_existing_without_write(archive):
    archive['system']['ReadOnly']=True
    assert reconcile(archive)['state']=='matched_existing'


def test_real_cli_retained_synthetic_file_retry_persists_both_observations(archive,candidate,tmp_path,monkeypatch):
    # These are genuinely parsed SYNTHETIC Part10 bytes, still not a real cohort.
    path,_,source,review=candidate
    raw=path.read_bytes()
    binding={key:source[key] for key in ['study_uid','series_uid','sop_uid']}
    binding.update(source_sha256=source['sha256'],source_bytes=len(raw))
    monkeypatch.setattr(sys.modules[__name__],'RAW',raw)
    monkeypatch.setattr(sys.modules[__name__],'BINDING',binding)
    store=dicom_custody.QUARANTINE_ROOT/('SYNTHETIC-reconcile-'+uuid4().hex)
    receipt=dicom_custody.retain_candidate(path,source,store,review)
    config=tmp_path/'pacs-private-SYNTHETIC.json'
    config.write_text(json.dumps(archive['config']),encoding='utf-8')
    environment={**os.environ,'PACS_CONFIG_FILE':str(config)}
    tool=Path(__file__).resolve().parents[1]/'tools/reconcile_pacs_candidate.py'
    base=[sys.executable,str(tool),'--store',str(store),'--receipt-id',receipt['receipt_id']]
    first=tmp_path/'first-observation.json'
    archive['mode']='disconnect'
    failed=subprocess.run(base+['--output',str(first)],env=environment,capture_output=True,text=True)
    assert failed.returncode==3 and not failed.stderr and SECRET not in failed.stdout
    first_bytes=first.read_bytes()
    archive['mode']='normal'
    second=tmp_path/'second-observation.json'
    succeeded=subprocess.run(base+['--output',str(second)],env=environment,capture_output=True,text=True)
    assert succeeded.returncode==0 and not succeeded.stderr
    result=json.loads(second.read_text())
    assert result['state']=='matched_existing' and result['candidate_approval_verified'] is False
    assert result['custody_receipt_id']==receipt['receipt_id'] and result['source_sha256']==source['sha256']
    assert first.read_bytes()==first_bytes and json.loads(first_bytes)['state']=='unresolved'
    calls=len(archive['calls'])
    refused=subprocess.run(base+['--output',str(first)],env=environment,capture_output=True,text=True)
    assert refused.returncode!=0 and first.read_bytes()==first_bytes and len(archive['calls'])==calls
    assert dicom_custody.inspect_custody(store)['receipts']==1


def test_cli_bad_receipt_does_not_contact_archive(archive,candidate,tmp_path):
    path,_,source,review=candidate
    store=dicom_custody.QUARANTINE_ROOT/('SYNTHETIC-reconcile-'+uuid4().hex)
    dicom_custody.retain_candidate(path,source,store,review)
    config=tmp_path/'pacs-private-SYNTHETIC.json'
    config.write_text(json.dumps(archive['config']),encoding='utf-8')
    out=tmp_path/'missing-receipt.json'
    tool=Path(__file__).resolve().parents[1]/'tools/reconcile_pacs_candidate.py'
    result=subprocess.run([sys.executable,str(tool),'--store',str(store),'--receipt-id','MISSING',
                           '--output',str(out)],env={**os.environ,'PACS_CONFIG_FILE':str(config)},
                          capture_output=True,text=True)
    assert result.returncode==3 and json.loads(out.read_text())['reason']=='custody_receipt_not_found'
    assert archive['calls']==[] and SECRET not in result.stdout
