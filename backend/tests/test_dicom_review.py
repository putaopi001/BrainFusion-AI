"""Synthetic archive + isolated SQLite: immutable source/content review records."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest
from app.database import SessionLocal, engine
from app.models.dicom_review import DICOMReadingReview
from app.models.doctor_opinion import DoctorOpinion
from test_dicom_measurements import linked
from test_dicom_series import tag
from test_pacs import archive, case_ids, client


@pytest.fixture(autouse=True)
def signed_review_client(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.services import local_auth as auth
    path = tmp_path / 'review-users.json'
    password = 'SYNTHETIC-review-session-only'
    path.write_text(json.dumps(dict(format_version=1, users=[dict(id='c'*32, username='review-test',
        display_name='SYNTHETIC engineering tester', role='doctor', disabled=False,
        password_hash=auth.hash_password(password))])), encoding='utf-8')
    monkeypatch.setattr(settings, 'LOCAL_AUTH_FILE', str(path))
    client.cookies.clear()
    with auth._lock: auth._sessions.clear(); auth._failures.clear()
    response = client.post('/local-auth/login', json=dict(username='review-test', password=password))
    assert response.status_code == 200, response.text
    client.headers['X-BF-CSRF'] = client.get('/local-auth/session').json()['data']['csrf']
    yield
    client.cookies.clear(); client.headers.pop('X-BF-CSRF', None)
    with auth._lock: auth._sessions.clear(); auth._failures.clear()


@pytest.fixture
def review_source(linked):
    _, endpoint, measurement = linked
    saved = client.post(endpoint, json=measurement)
    assert saved.status_code == 200
    prefix = endpoint.removesuffix('/measurements')
    data = client.get(prefix+'/reading-report').json()['data']
    payload = dict(context=data['context'], content_sha256=data['content_sha256'],
        client_uid='SYNTHETIC-REVIEW', reviewer='SYNTHETIC engineering tester',
        opinion='Protocol check only; not a physician or clinical review.', decision='checked',
        acknowledge_local_record_only=True)
    return linked, prefix, data, payload


def test_immutable_review_retry_history_and_separate_export_version(review_source):
    linked, prefix, before, payload = review_source
    first = client.post(prefix+'/reviews', json=payload)
    assert first.status_code == 200, first.text
    review = first.json()['data']
    assert review['current'] and review['reviewer_authenticated']
    assert review['identity']['username'] == 'review-test'
    assert not review['identity']['professional_credential_verified']
    assert first.headers['cache-control'] == 'no-store'
    assert client.post(prefix+'/reviews', json=payload).json()['data']['id'] == review['id']
    changed = dict(payload, opinion='Different immutable record')
    assert client.post(prefix+'/reviews', json=changed).status_code == 409
    after = client.get(prefix+'/reading-report').json()['data']
    assert before['content_sha256'] == after['content_sha256']
    assert before['export_sha256'] != after['export_sha256']
    assert after['latest_review']['id'] == review['id']
    second = client.post(prefix+'/reviews', json=dict(payload, client_uid='SYNTHETIC-REVISION', decision='needs_revision'))
    assert second.status_code == 200
    after = client.get(prefix+'/reading-report').json()['data']
    assert after['latest_review']['decision'] == 'needs_revision'
    history = client.get(prefix+'/reviews', params={'limit':1}).json()['data']
    assert history['total'] == 2 and history['next_offset'] == 1
    historical = client.get(prefix+'/reviews', params={'limit':1,'offset':1}).json()['data']['items'][0]
    assert historical['id'] == review['id']
    assert historical['reviewed_snapshot']['content_sha256'] == before['content_sha256']
    assert historical['reviewed_snapshot']['measurements'] == before['measurements']
    with SessionLocal() as db:
        assert db.query(DICOMReadingReview).filter_by(case_id=linked[0]).count() == 2


@pytest.mark.parametrize('edit',['distance','opinion','metadata'])
def test_changed_content_marks_history_stale_and_refuses_old_submission(archive, review_source, edit):
    linked, prefix, before, payload = review_source
    first = client.post(prefix+'/reviews', json=payload).json()['data']
    if edit == 'distance':
        item = before['measurements'][0]
        response = client.request('DELETE',prefix+'/measurements/'+str(item['id']),json={'context':before['context']})
        assert response.status_code == 200
    elif edit == 'opinion':
        with SessionLocal() as db:
            db.add(DoctorOpinion(case_id=linked[0],author='SYNTHETIC',content='An independent case note changed'))
            db.commit()
    else:
        archive['series_metadata'][0]['00281050'] = tag(123, 'DS')
    after = client.get(prefix+'/reading-report').json()['data']
    assert after['content_sha256'] != before['content_sha256']
    assert not after['latest_review']['current']
    assert client.post(prefix+'/reviews', json=payload).status_code == 409
    old = client.get(prefix+'/reviews').json()['data']['items'][0]
    assert old['id'] == first['id'] and not old['current']
    assert old['reviewed_snapshot']['measurements'] == before['measurements']


@pytest.mark.parametrize('kind',['blank_name','blank_opinion','no_ack','claim_authenticated','mask','wrong_hash'])
def test_invalid_or_unacknowledged_review_cannot_write(review_source, kind):
    linked, prefix, _, original = review_source
    payload = copy.deepcopy(original)
    if kind == 'blank_name': payload['reviewer'] = '   '
    elif kind == 'blank_opinion': payload['opinion'] = '\n  '
    elif kind == 'no_ack': payload['acknowledge_local_record_only'] = False
    elif kind == 'claim_authenticated': payload['reviewer_authenticated'] = True
    elif kind == 'mask': payload['segmentation_source'] = 'model'
    else: payload['content_sha256'] = 'f'*64
    response = client.post(prefix+'/reviews', json=payload)
    assert response.status_code == (409 if kind == 'wrong_hash' else 422), response.text
    with SessionLocal() as db:
        assert db.query(DICOMReadingReview).filter_by(case_id=linked[0]).count() == 0


def test_concurrent_same_request_commits_once(review_source):
    linked, prefix, _, payload = review_source
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _:client.post(prefix+'/reviews',json=payload),range(2)))
    assert all(result.status_code == 200 for result in results), [r.text for r in results]
    assert len({r.json()['data']['id'] for r in results}) == 1
    with SessionLocal() as db:
        assert db.query(DICOMReadingReview).filter_by(case_id=linked[0]).count() == 1


@pytest.mark.parametrize('length',[4000,4001])
def test_long_review_is_retained_exactly_or_rejected_at_declared_limit(review_source,length):
    _, prefix, _, payload = review_source
    payload['opinion'] = '测'*length
    response = client.post(prefix+'/reviews',json=payload)
    assert response.status_code == (200 if length == 4000 else 422), response.text
    data = client.get(prefix+'/reviews').json()['data']
    if length == 4000:
        assert data['items'][0]['opinion'] == payload['opinion']
    else:
        assert data['total'] == 0


def test_review_requires_case_binding_archive_identity_and_permission(archive, review_source, case_ids):
    linked, prefix, _, payload = review_source
    other = prefix.replace('/cases/'+str(linked[0])+'/', '/cases/'+str(case_ids[1])+'/')
    assert client.post(other+'/reviews',json=payload).status_code == 409
    archive['system_extra']['DatabaseServerIdentifier'] = 'WRONG'
    assert client.post(prefix+'/reviews',json=payload).status_code == 409
    archive['system_extra']['DatabaseServerIdentifier'] = 'SYNTHETIC-A'
    archive['config']['allow_pixel_read'] = False
    archive['path'].write_text(json.dumps(archive['config']),encoding='utf-8')
    assert client.post(prefix+'/reviews',json=payload).status_code == 409


def test_review_snapshot_survives_database_backup_and_restore(review_source,tmp_path):
    _, prefix, _, payload = review_source
    item = client.post(prefix+'/reviews',json=payload).json()['data']
    source = Path(engine.url.database).resolve()
    out = tmp_path/'review-backup'
    subprocess.run([sys.executable,str(Path(__file__).parents[1]/'tools/snapshot_database.py'),
        '--source',str(source),'--output',str(out)],check=True,capture_output=True,text=True)
    def row(path):
        with sqlite3.connect(path) as db:return db.execute('select * from dicom_reading_reviews where id=?',(item['id'],)).fetchone()
    assert row(source) == row(out/'snapshot.db') == row(out/'restored-validation.db')
