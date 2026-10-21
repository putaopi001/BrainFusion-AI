"""Synthetic TCP archive + isolated DB; report remains independent of AI."""
import pytest

from app.api import pacs
from app.database import SessionLocal
from app.models.mri import MRI
from app.models.report import Report
from app.models.doctor_opinion import DoctorOpinion
from test_dicom_measurements import linked
from test_pacs import archive, case_ids, client


def test_summary_stable_source_and_physical_measurement_without_model_report(linked):
    case_id, endpoint, payload = linked
    with SessionLocal() as db:
        before = (db.query(MRI).count(), db.query(Report).count())
    report_url = endpoint.replace('/measurements', '/reading-report')
    empty = client.get(report_url)
    assert empty.status_code == 200, empty.text
    assert empty.headers['cache-control'] == 'no-store'
    data = empty.json()['data']
    assert data['measurements'] == [] and data['ai_analysis_included'] is False
    assert data['case_id'] == case_id and data['context'] == payload['context']
    assert client.get(report_url).json()['data']['content_sha256'] == data['content_sha256']
    item = client.post(endpoint, json=payload).json()['data']
    result = client.get(report_url).json()['data']
    assert result['content_sha256'] != data['content_sha256']
    assert result['measurements'] == [item] and item['length_mm'] == pytest.approx(2, abs=1e-8)
    assert client.get(f'/reports/{case_id}').status_code == 404
    with SessionLocal() as db:
        assert before == (db.query(MRI).count(), db.query(Report).count())
    client.request('DELETE', endpoint+'/'+str(item['id']), json={'context':payload['context']})
    assert client.get(report_url).json()['data']['content_sha256'] == data['content_sha256']


def test_old_source_measurements_excluded_and_opinion_changes_revision(archive, linked):
    _, endpoint, payload = linked
    client.post(endpoint, json=payload)
    from test_dicom_series import tag
    archive['series_metadata'][0]['00281050'] = tag(123, 'DS')
    report_url = endpoint.replace('/measurements', '/reading-report')
    result = client.get(report_url).json()['data']
    assert result['measurements'] == [] and result['excluded_historical_measurements'] == 1
    assert result['context'] != payload['context']
    old = result['content_sha256']
    saved = client.put(f'/cases/{linked[0]}/doctor-opinion', json={'author':'SYNTHETIC reviewer', 'content':'SYNTHETIC case note'})
    assert saved.status_code == 200, saved.text
    result = client.get(report_url).json()['data']
    assert result['content_sha256'] != old
    assert result['doctor_opinion']['content'] == 'SYNTHETIC case note'
    assert result['doctor_opinion_scope'] == 'case_level_not_series_version_review'


def test_report_rejects_wrong_case_retracted_permission_and_changed_archive(archive, linked, case_ids):
    _, endpoint, _ = linked
    url = endpoint.replace('/measurements', '/reading-report')
    assert client.get(url.replace('/cases/'+str(linked[0])+'/', '/cases/'+str(case_ids[1])+'/')).status_code == 409
    archive['system_extra']['DatabaseServerIdentifier'] = 'WRONG'
    assert client.get(url).status_code == 409
    archive['system_extra']['DatabaseServerIdentifier'] = 'SYNTHETIC-A'
    archive['config']['allow_pixel_read'] = False
    import json
    archive['path'].write_text(json.dumps(archive['config']), encoding='utf-8')
    assert client.get(url).status_code == 409


def test_report_rejects_edits_during_assembly(linked, monkeypatch):
    _, endpoint, _ = linked
    response = client.put(f'/cases/{linked[0]}/doctor-opinion',
        json={'author':'SYNTHETIC reviewer', 'content':'SYNTHETIC before read'})
    assert response.status_code == 200
    original = pacs.dicom_report.snapshot
    calls = []
    def changing(*args):
        data = original(*args)
        calls.append(True)
        if len(calls) == 1:
            # Another transaction commits after the first report snapshot.
            with SessionLocal() as writer:
                opinion = writer.query(DoctorOpinion).filter_by(case_id=linked[0]).one()
                opinion.content = 'SYNTHETIC edit committed during assembly'
                writer.commit()
        return data
    monkeypatch.setattr(pacs.dicom_report, 'snapshot', changing)
    response = client.get(endpoint.replace('/measurements', '/reading-report'))
    assert response.status_code == 409
    assert response.json()['detail']['reason'] == 'dicom_report_changed'
