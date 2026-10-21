"""Real password/cookie/CSRF checks on an isolated local account configuration."""
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.services import local_auth as auth
from app.models.dicom_review import DICOMReadingReview
from app.database import SessionLocal
from test_dicom_review import review_source
from test_dicom_measurements import linked
from test_pacs import archive, case_ids

PASSWORD='SYNTHETIC-only-strong-password'
@pytest.fixture
def account_config(tmp_path,monkeypatch):
    path=tmp_path/'local-users.json'
    users=[dict(id='a'*32,username='doctor-test',display_name='SYNTHETIC engineering tester',role='doctor',disabled=False,password_hash=auth.hash_password(PASSWORD)),
           dict(id='b'*32,username='research-test',display_name='SYNTHETIC research tester',role='researcher',disabled=False,password_hash=auth.hash_password(PASSWORD))]
    path.write_text(json.dumps(dict(format_version=1,users=users)),encoding='utf-8')
    monkeypatch.setattr(settings,'LOCAL_AUTH_FILE',str(path))
    with auth._lock:auth._sessions.clear();auth._failures.clear()
    yield path
    with auth._lock:auth._sessions.clear();auth._failures.clear()

def login(client,name='doctor-test'):
    r=client.post('/local-auth/login',json=dict(username=name,password=PASSWORD))
    assert r.status_code==200,r.text
    return client.get('/local-auth/session').json()['data']

def test_cookie_session_logout_expiry_and_no_password_echo(account_config):
    c=TestClient(app)
    r=c.post('/local-auth/login',json=dict(username='doctor-test',password=PASSWORD))
    assert r.status_code==200 and PASSWORD not in r.text
    cookie=r.headers['set-cookie'].lower();assert 'httponly' in cookie and 'samesite=strict' in cookie
    s=c.get('/local-auth/session');assert s.headers['cache-control']=='no-store'
    state=s.json()['data'];assert state['user']['role']=='doctor' and state['csrf']
    assert 'password_hash' not in s.text and auth.COOKIE not in s.text
    token=c.cookies.get(auth.COOKIE)
    assert c.post('/local-auth/logout',headers={'X-BF-CSRF':state['csrf']}).status_code==200
    c.cookies.set(auth.COOKIE,token)
    assert c.get('/local-auth/session').json()['data']['user'] is None
    state=login(c)
    with auth._lock:
        for row in auth._sessions.values():row['expires']=0
    assert c.get('/local-auth/session').json()['data']['user'] is None

def test_origin_csrf_researcher_and_name_spoof_cannot_review(account_config,linked):
    _,measurement,_=linked;prefix=measurement.removesuffix('/measurements')
    c=TestClient(app);data=c.get(prefix+'/reading-report').json()['data']
    payload=dict(context=data['context'],content_sha256=data['content_sha256'],client_uid='AUTH-BOUND',reviewer='SYNTHETIC engineering tester',
        opinion='Engineering only',decision='checked',acknowledge_local_record_only=True)
    assert c.post(prefix+'/reviews',json=payload).status_code==401
    state=login(c,'research-test')
    assert c.post(prefix+'/reviews',json=payload,headers={'X-BF-CSRF':state['csrf']}).status_code==403
    state=login(c)
    assert c.post(prefix+'/reviews',json=payload).status_code==403
    assert c.post(prefix+'/reviews',json=payload,headers={'X-BF-CSRF':state['csrf'],'Origin':'http://untrusted.invalid'}).status_code==403
    assert c.post(prefix+'/reviews',json=dict(payload,reviewer='Forged doctor'),headers={'X-BF-CSRF':state['csrf']}).status_code==403
    r=c.post(prefix+'/reviews',json=payload,headers={'X-BF-CSRF':state['csrf']})
    assert r.status_code==200,r.text
    row=r.json()['data'];assert row['reviewer_authenticated'] is True
    assert row['identity']['username']=='doctor-test' and not row['identity']['professional_credential_verified']
    assert c.post(prefix+'/reviews',json=payload,headers={'X-BF-CSRF':state['csrf']}).json()['data']['id']==row['id']
    # An unverified old row remains unverified; no migration/backfill fabricates an actor.
    with SessionLocal() as db:
        stored=db.query(DICOMReadingReview).filter_by(id=row['id']).one()
        content=json.loads(stored.snapshot_json);content.pop('review_actor')
        stored.snapshot_json=json.dumps(content);db.commit()
    history=c.get(prefix+'/reviews').json()['data']['items'][0]
    assert history['reviewer_authenticated'] is False and history['identity'] is None

def test_configuration_change_revokes_existing_session_and_private_validation(account_config):
    c=TestClient(app);state=login(c)
    content=json.loads(account_config.read_text(encoding='utf-8'));content['users'][0]['disabled']=True
    account_config.write_text(json.dumps(content),encoding='utf-8')
    assert c.get('/local-auth/session').json()['data']['user'] is None
    assert c.post('/local-auth/login',json=dict(username='doctor-test',password=PASSWORD)).status_code==401
    for body in [dict(username='doctor-test',password={'must-not-echo':PASSWORD}),dict(username='doctor-test',password=PASSWORD,forged_secret=PASSWORD)]:
        r=c.post('/local-auth/login',json=body);assert r.status_code==422 and PASSWORD not in r.text

def test_unknown_account_bad_password_throttling_and_missing_config(account_config):
    c=TestClient(app)
    for i in range(5):
        r=c.post('/local-auth/login',json=dict(username='unknown',password=PASSWORD));assert r.status_code==401
    r=c.post('/local-auth/login',json=dict(username='doctor-test',password=PASSWORD))
    assert r.status_code==429 and r.headers['retry-after']=='60'
    account_config.unlink()
    assert c.get('/local-auth/session').json()['data']['configured'] is False
    assert c.post('/local-auth/login',json=dict(username='doctor-test',password=PASSWORD)).status_code==503

def test_salted_hash_and_correct_verification():
    a,b=auth.hash_password(PASSWORD),auth.hash_password(PASSWORD)
    assert a!=b and auth.verify_password(PASSWORD,a)
    assert not auth.verify_password('SYNTHETIC-other-password',a)
    assert not auth.verify_password(PASSWORD,'invalid')
