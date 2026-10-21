import hashlib
import json
import pytest
from fastapi.testclient import TestClient
from app.database import SessionLocal
from app.main import app
from app.models.pacs import PACSStudyLink
from test_dicom_conversion_registry import registered

def test_role_review_authenticates_version_and_never_activates(registered, monkeypatch):
    import app.api.pacs as api
    from app.models.mri import MRI
    from app.services import dicom_conversion_role_review as role_review
    from app.services.dicom_conversion_registry import load_index
    from app.services.local_auth import require_doctor
    item=registered;proposal=item['proposal'];proposal['data_role']='dicom-metadata-snapshot'
    pp=item['index'].parent/'proposal.json';pp.write_text(json.dumps(proposal),encoding='utf-8')
    row=dict(item['row'],proposal_sha256=hashlib.sha256(pp.read_bytes()).hexdigest())
    item['index'].write_text(json.dumps({'format':'dicom-conversion-index-v1','entries':[row]}),encoding='utf-8')
    entry=load_index()[0];view=role_review.describe(entry)
    assert view['review_allowed'] and [x['role'] for x in view['assignments']]==['t1c','t1n','t2w','t2f']
    client=TestClient(app)
    with SessionLocal() as db:before=(db.query(MRI).filter_by(case_id=item['case_id']).count(),db.query(PACSStudyLink).filter_by(case_id=item['case_id']).count())
    body={'decision':'approve','plan_revision':view['plan_revision'],'assignment_set_sha256':view['assignment_set_sha256'],'confirm_roles':True}
    url=f"/pacs/cases/{item['case_id']}/conversions/test-version/role-review"
    assert client.post(url,json=body).status_code==401
    monkeypatch.setattr(api,'check_archive_entry',lambda *_:{'status':'matched_at_check','data_role':'dicom-metadata-snapshot',
        'plan_revision':view['plan_revision'],'report_sha256':entry.report_sha256,'archive_id':entry.archive_id,
        'archive_fingerprint':entry.archive_fingerprint,'completed_utc':'2026-10-17T00:00:00+00:00','instances_checked':12,'raw_byte_passes':2})
    identity={'user':{'id':'a'*32,'username':'review-doctor','display_name':'SYNTHETIC reviewer','role':'doctor'},'authentication_method':'test_dependency_override'}
    app.dependency_overrides[require_doctor]=lambda:identity
    try:
        response=client.post(url,json=body);assert response.status_code==200,response.text
        data=response.json()['data'];assert data['review_status']=='approved' and data['reviewer_authenticated']
        assert not data['professional_credential_verified'] and not data['model_input_eligible'] and not data['current_mri_replaced']
        history=client.get(url).json()['data']['history']
        assert len(history)==1 and history[0]['reviewer']['id']=='a'*32 and history[0]['decision']=='approve'
        assert str(item['folder']) not in client.get(url).text
    finally:app.dependency_overrides.pop(require_doctor,None)
    with SessionLocal() as db:after=(db.query(MRI).filter_by(case_id=item['case_id']).count(),db.query(PACSStudyLink).filter_by(case_id=item['case_id']).count())
    assert before==after


def test_synthetic_fixture_cannot_receive_role_approval(registered,monkeypatch):
    from fastapi import HTTPException
    from app.services import dicom_conversion_role_review as role_review
    from app.services.dicom_conversion_registry import load_index
    entry=load_index()[0]
    monkeypatch.setattr(role_review,'describe',lambda _:{'plan_revision':'0'*64,'assignment_set_sha256':'1'*64,'review_allowed':False})
    identity={'user':{'id':'b'*32,'username':'review-doctor','display_name':'SYNTHETIC reviewer','role':'doctor'}}
    with pytest.raises(HTTPException) as exc:
        role_review.record(entry,'approve','0'*64,'1'*64,identity)
    assert exc.value.detail['reason']=='synthetic_conversion_not_reviewable'
    assert not (registered['index'].parent/'dicom-conversion-role-reviews.json').exists()

def test_stale_role_digest_fails_before_archive_read(registered,monkeypatch):
    import app.api.pacs as api
    from app.services.local_auth import require_doctor
    item=registered;identity={'user':{'id':'c'*32,'username':'review-doctor','display_name':'SYNTHETIC reviewer','role':'doctor'}}
    app.dependency_overrides[require_doctor]=lambda:identity
    monkeypatch.setattr(api,'check_archive_entry',lambda *_:pytest.fail('stale confirmation must not read archive'))
    try:
        url=f"/pacs/cases/{item['case_id']}/conversions/test-version/role-review"
        r=TestClient(app).post(url,json={'decision':'approve','plan_revision':'0'*64,'assignment_set_sha256':'1'*64,'confirm_roles':True})
        assert r.status_code==409 and r.json()['detail']['reason']=='conversion_role_review_stale'
        assert not (item['index'].parent/'dicom-conversion-role-reviews.json').exists()
    finally:app.dependency_overrides.pop(require_doctor,None)




