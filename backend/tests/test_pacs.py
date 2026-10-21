"""Synthetic HTTP protocol fixture + real isolated SQLite. Not Orthanc or real DICOM."""
import base64
import copy
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.database import SessionLocal
from app.models.pacs import PACSStudyLink
from app.models.mri import MRI
from app.services import pacs_client

client = TestClient(app)
STUDY, SERIES, INSTANCE, FRAME = '1.2.840.999.1', '1.2.840.999.2', '1.2.840.999.3', '1.2.840.999.4'
SECRET = 'SYNTHETIC-protocol-secret'


def test_docker_host_gateway_requires_explicit_opt_in(monkeypatch):
    config = dict(format_version=1, archive_id='synthetic-docker-host',
                  base_url='http://host.docker.internal:8042', username='local-user',
                  password='SYNTHETIC-only-secret')
    loopback_config = {**config, 'base_url': 'http://127.0.0.1:8042'}
    monkeypatch.setattr(settings, 'PACS_ALLOW_DOCKER_HOST', False)
    with pytest.raises(ValidationError):
        pacs_client.PacsConfig.model_validate(config)
    assert pacs_client.PacsConfig.model_validate(loopback_config).base_url == 'http://127.0.0.1:8042'
    monkeypatch.setattr(settings, 'PACS_ALLOW_DOCKER_HOST', True)
    assert pacs_client.PacsConfig.model_validate(config).base_url == 'http://host.docker.internal:8042'
    assert pacs_client.PacsConfig.model_validate(loopback_config).base_url == 'http://host.docker.internal:8042'
    with pytest.raises(ValidationError):
        pacs_client.PacsConfig.model_validate({**config, 'base_url': 'http://arbitrary-host.invalid:8042'})


def tag(value, vr='UI'):
    return {'vr': vr, 'Value': value if isinstance(value, list) else [value]}


@pytest.fixture
def archive(tmp_path, monkeypatch):
    fixture = {'mode': 'normal', 'requests': [], 'studies': [{'0020000D': tag(STUDY), '00080061': tag(['MR', 'CT'], 'CS'),
               '00100010': {'vr': 'PN', 'Value': [{'Alphabetic': 'DO NOT FORWARD'}]},
               '00100020': tag('DO NOT FORWARD ID', 'LO'), '00080020': tag('20000101', 'DA')}]}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Do not log authorization or upstream paths.

        def do_GET(self):
            uri = urlsplit(self.path); query = parse_qs(uri.query)
            fixture['requests'].append({'path': uri.path, 'query': query, 'authenticated': bool(self.headers.get('Authorization')),
                                        'cookie': self.headers.get('Cookie'), 'forwarded': self.headers.get('X-Forwarded-Host'), 'accept': self.headers.get('Accept')})
            expected = 'Basic ' + base64.b64encode(('protocol-user:' + SECRET).encode()).decode()
            if fixture['mode'] != 'public' and self.headers.get('Authorization') != expected:
                self.send_response(401); self.end_headers(); return
            if uri.path == '/system':
                body = json.dumps({'Version': 'SYNTHETIC-PROTOCOL-ONLY', 'PluginsEnabled': True,
                                   **fixture.get('system_extra', {})}).encode()
                mime = 'application/json'
            elif uri.path.endswith('/frames/1') and 'frame_body' in fixture:
                body, mime = fixture['frame_body'], fixture['frame_type']
                self.send_response(fixture.get('frame_status',200)); self.send_header('Content-Type',mime)
                self.end_headers(); self.wfile.write(body); return
            else:
                if fixture['mode'] == 'redirect':
                    self.send_response(302); self.send_header('Location', 'https://example.invalid/' + SECRET); self.end_headers(); return
                if fixture['mode'] == 'missing':
                    self.send_response(404); self.end_headers(); return
                if fixture['mode'] == 'empty':
                    self.send_response(204); self.end_headers(); return
                if uri.path.endswith('/series/' + SERIES + '/metadata') and 'series_metadata' in fixture:
                    fixture['series_metadata_reads'] = fixture.get('series_metadata_reads',0)+1
                    data = copy.deepcopy(fixture['series_metadata'])
                    if fixture.get('series_mode')=='changed_geometry' and fixture['series_metadata_reads']>1:
                        data[0]['00281050']=tag(100,'DS')
                elif uri.path.endswith('/metadata') and 'metadata' in fixture:
                    data = copy.deepcopy(fixture['metadata'])
                elif uri.path.endswith('/instances'):
                    data = copy.deepcopy(fixture.get('series_instances')) if 'series_instances' in fixture else [{'0020000D': tag(STUDY), '0020000E': tag(SERIES), '00080018': tag(INSTANCE),
                             '00080016': tag('1.2.840.10008.5.1.4.1.1.4'), '00200052': tag(FRAME), '00200013': tag(2, 'IS')}]
                    fixture['series_instance_reads']=fixture.get('series_instance_reads',0)+1
                    if fixture.get('series_mode')=='changed_instance_set' and fixture['series_instance_reads']>1:
                        data=data[:-1]
                elif uri.path.endswith('/series'):
                    data = [{'0020000D': tag(STUDY), '0020000E': tag(SERIES), '00080060': tag('MR', 'CS')}]
                else:
                    data = copy.deepcopy(fixture['studies'])
                    if query.get('StudyInstanceUID', [STUDY])[0] != STUDY:
                        data = []
                if fixture['mode'] == 'mismatch': data[0]['0020000D'] = tag('1.2.3.999')
                if fixture['mode'] == 'bad_uid': data[0]['0020000D'] = tag('1.02.3')
                if fixture['mode'] == 'duplicate': data *= 2
                if fixture['mode'] == 'missing_uid': del data[0]['0020000D']
                body = b'not JSON: ' + SECRET.encode() if fixture['mode'] == 'bad_json' else json.dumps(data).encode()
                mime = 'text/html' if fixture['mode'] == 'html' else 'application/dicom+json'
            self.send_response(200); self.send_header('Content-Type', mime); self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    path = tmp_path / 'pacs-config.json'
    config = {'format_version': 1, 'archive_id': 'synthetic-protocol-only', 'base_url': f'http://127.0.0.1:{server.server_port}',
              'username': 'protocol-user', 'password': SECRET}
    path.write_text(json.dumps(config), encoding='utf-8')
    monkeypatch.setattr(settings, 'PACS_CONFIG_FILE', str(path))
    fixture.update(path=path, config=config, server=server)
    yield fixture
    server.shutdown(); server.server_close(); thread.join(timeout=2)


@pytest.fixture
def case_ids():
    return [client.post('/cases/create', json={'patient_name': 'SYNTHETIC PACS fixture', 'age': 40, 'gender': 'female', 'description': 'Protocol test only'}).json()['data']['case_id'] for _ in range(2)]


def test_unconfigured_is_explicit_no_fake_archive(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, 'PACS_CONFIG_FILE', str(tmp_path / 'absent.json'))
    health = client.get('/pacs/status')
    assert health.json()['data']['state'] == 'unconfigured'
    assert not health.json()['data']['read_available'] and not health.json()['data']['dicom_view_available']
    assert health.headers['cache-control'] == 'no-store'
    unavailable = client.get('/pacs/studies')
    assert unavailable.status_code == 503 and unavailable.headers['cache-control'] == 'no-store'


def test_real_tcp_protocol_query_parent_identity_and_credential_isolation(archive):
    health = client.get('/pacs/status').json()['data']
    assert health['read_available'] and not health['import_available'] and not health['ai_bridge_available']
    response = client.get('/pacs/studies', headers={'Authorization': 'browser-not-forwarded', 'Cookie': 'DO NOT FORWARD', 'X-Forwarded-Host': 'remote.invalid'})
    assert response.status_code == 200, response.text
    row = response.json()['data']['items'][0]
    assert row['modalities'] == ['MR', 'CT']
    assert SECRET not in response.text and 'DO NOT FORWARD' not in response.text and 'protocol-user' not in response.text
    series = client.get(f'/pacs/studies/{STUDY}/series').json()['data']['items'][0]
    assert series['series_uid'] == SERIES and series['study_uid'] == STUDY
    instance = client.get(f'/pacs/studies/{STUDY}/series/{SERIES}/instances').json()['data']['items'][0]
    assert instance['instance_uid'] == INSTANCE and instance['frame_of_reference_uid'] == FRAME
    assert all(r['cookie'] is None and r['forwarded'] is None for r in archive['requests'])
    assert archive['requests'][-1]['query']['includefield'] == ['00200052']
    assert all(r['authenticated'] for r in archive['requests'] if r['path'] != '/system')


def test_configured_server_pin_rejects_same_origin_changed_server(archive):
    archive['config']['expected_database_server_identifier'] = 'SYNTHETIC-A'
    archive['system_extra'] = {'DatabaseServerIdentifier': 'SYNTHETIC-B'}
    archive['path'].write_text(json.dumps(archive['config']), encoding='utf-8')
    response = client.get('/pacs/studies')
    assert response.status_code == 409 and response.json()['detail']['reason'] == 'archive_identity_mismatch'
    assert not client.get('/pacs/status').json()['data']['read_available']
    assert all(r['path'] == '/system' for r in archive['requests'])


@pytest.mark.parametrize('pixels,pinned,available', [(False, False, False), (True, False, False),
                                                   (False, True, False), (True, True, True)])
def test_viewing_status_reports_guarded_capability_without_claiming_ai_or_browser_import(archive, pixels, pinned, available):
    archive['config']['allow_pixel_read'] = pixels
    if pinned:
        archive['config']['expected_database_server_identifier'] = 'SYNTHETIC-PINNED'
        archive['system_extra'] = {'DatabaseServerIdentifier': 'SYNTHETIC-PINNED'}
    archive['path'].write_text(json.dumps(archive['config']), encoding='utf-8')
    response = client.get('/pacs/status')
    value = response.json()['data']
    assert value['read_available'] is True
    assert value['dicom_view_available'] is available
    assert value['pixel_read_enabled'] is pixels
    assert value['import_available'] is False and value['ai_bridge_available'] is False
    assert ('已启用受支持序列' in value['message']) is available
    assert SECRET not in response.text and 'protocol-user' not in response.text


def test_same_origin_new_pin_does_not_overwrite_old_case_link(archive, case_ids):
    archive['config']['expected_database_server_identifier'] = 'SYNTHETIC-A'
    archive['system_extra'] = {'DatabaseServerIdentifier': 'SYNTHETIC-A'}
    archive['path'].write_text(json.dumps(archive['config']), encoding='utf-8')
    case_id = case_ids[0]
    first = client.post(f'/pacs/cases/{case_id}/links', json={'study_uid': STUDY, 'acknowledge_case_match': True})
    assert first.status_code == 200, first.text
    archive['config']['expected_database_server_identifier'] = 'SYNTHETIC-B'
    archive['system_extra']['DatabaseServerIdentifier'] = 'SYNTHETIC-B'
    archive['path'].write_text(json.dumps(archive['config']), encoding='utf-8')
    retry = client.post(f'/pacs/cases/{case_id}/links', json={'study_uid': STUDY, 'acknowledge_case_match': True})
    assert retry.status_code == 409 and retry.json()['detail']['reason'] == 'mapping_conflict'
    with SessionLocal() as db:
        row = db.query(PACSStudyLink).filter_by(archive_id=archive['config']['archive_id'], study_uid=STUDY).one()
        assert row.case_id == case_id
        old = pacs_client.PacsConfig.model_validate({**archive['config'], 'expected_database_server_identifier': 'SYNTHETIC-A'})
        assert row.endpoint_fingerprint == old.endpoint_fingerprint
    # Leave no mapping shared with subsequent synthetic fixture tests.
    with SessionLocal() as db:
        db.query(PACSStudyLink).filter_by(archive_id=archive['config']['archive_id'], study_uid=STUDY).delete()
        db.commit()


def test_legacy_origin_fingerprint_preserved_until_pin_explicitly_added(archive):
    original = pacs_client.PacsConfig.model_validate(archive['config'])
    assert original.endpoint_fingerprint == hashlib.sha256(original.base_url.encode()).hexdigest()
    pinned = pacs_client.PacsConfig.model_validate({**archive['config'], 'expected_database_server_identifier': 'SYNTHETIC-A'})
    assert pinned.endpoint_fingerprint != original.endpoint_fingerprint


@pytest.mark.parametrize('uid', ['../system', '1.2?url=https://remote', '1.02.3', '1.2.*', '9' * 65, ''])
def test_invalid_uid_does_not_reach_archive(archive, uid):
    response = client.get('/pacs/studies', params={'study_uid': uid})
    assert response.status_code == 422
    assert archive['requests'] == []


@pytest.mark.parametrize('mode,reason', [('public', 'archive_auth_required'), ('redirect', 'upstream_error'),
    ('bad_json', 'invalid_metadata'), ('html', 'invalid_metadata'), ('bad_uid', 'invalid_metadata'),
    ('missing_uid', 'invalid_metadata'), ('duplicate', 'duplicate_uid'), ('missing', 'not_found')])
def test_invalid_upstream_no_credential_body_leak(archive, mode, reason):
    archive['mode'] = mode
    response = client.get('/pacs/studies')
    assert response.status_code in (404, 502, 503), response.text
    assert response.json()['detail']['reason'] == reason
    assert SECRET not in response.text and 'https://example.invalid' not in response.text
    assert not client.get('/pacs/status').json()['data']['read_available']


def test_qido_204_and_pagination_contract(archive):
    archive['mode'] = 'empty'
    assert client.get('/pacs/studies').json()['data']['items'] == []
    archive['mode'] = 'normal'
    response = client.get('/pacs/studies?limit=1&offset=7').json()['data']
    assert response['next_offset'] == 8
    assert archive['requests'][-1]['query']['offset'] == ['7']
    assert client.get('/pacs/studies?limit=101').status_code == 422
    assert client.get('/pacs/studies?offset=-1').status_code == 422


def test_wrong_parent_uid_rejected(archive):
    archive['mode'] = 'mismatch'
    response = client.get(f'/pacs/studies/{STUDY}/series')
    assert response.status_code == 502 and response.json()['detail']['reason'] == 'uid_mismatch'


@pytest.mark.parametrize('change', ['remote', 'dns', 'embedded', 'path', 'blank_password', 'extra', 'invalid_json'])
def test_invalid_server_configuration_is_redacted(archive, change):
    config = copy.deepcopy(archive['config'])
    if change == 'remote': config['base_url'] = 'http://192.168.1.1:8042'
    if change == 'dns': config['base_url'] = 'http://localhost:8042'
    # Synthetic URL credentials are assembled at runtime; keep the source scan strict.
    if change == 'embedded': config['base_url'] = 'http://' + 'secret:password' + '@127.0.0.1:8042'
    if change == 'path': config['base_url'] += '/dicom-web'
    if change == 'blank_password': config['password'] = ''
    if change == 'extra': config['browser_password'] = SECRET
    archive['path'].write_text(SECRET if change == 'invalid_json' else json.dumps(config), encoding='utf-8')
    response = client.get('/pacs/studies')
    assert response.status_code == 503 and SECRET not in response.text
    assert response.json()['detail']['reason'] == 'invalid_config'
    assert archive['requests'] == []


def test_body_budget_refuses_oversized_metadata(archive, monkeypatch):
    monkeypatch.setattr(pacs_client, 'MAX_JSON_BYTES', 120)
    response = client.get('/pacs/studies')
    assert response.status_code == 502 and response.json()['detail']['reason'] == 'metadata_too_large'


def test_persisted_mapping_retry_conflict_and_original_mri_untouched(archive, case_ids):
    a, b = case_ids
    payload = {'study_uid': STUDY, 'acknowledge_case_match': True}
    with SessionLocal() as db:
        old_mris = [(m.id, m.case_id, m.filepath, m.analysis_run_id) for m in db.query(MRI).all()]
    first = client.post(f'/pacs/cases/{a}/links', json=payload)
    assert first.status_code == 200, first.text
    saved = first.json()['data']
    assert client.post(f'/pacs/cases/{a}/links', json=payload).json()['data']['id'] == saved['id']
    assert client.post(f'/pacs/cases/{b}/links', json=payload).status_code == 409
    with TestClient(app) as reopened:
        rows = reopened.get(f'/pacs/cases/{a}/links').json()['data']['items']
        assert rows == [saved]
    with SessionLocal() as db:
        row = db.get(PACSStudyLink, saved['id'])
        assert hashlib.sha256(row.metadata_json.encode()).hexdigest() == row.metadata_sha256
        assert 'DO NOT FORWARD' not in row.metadata_json
        assert old_mris == [(m.id, m.case_id, m.filepath, m.analysis_run_id) for m in db.query(MRI).all()]
        # Simulate config endpoint identity change; retry cannot overwrite the old archive binding.
        row.endpoint_fingerprint = '0' * 64; db.commit()
    assert not client.get(f'/pacs/cases/{a}/links').json()['data']['items'][0]['archive_matches_config']
    assert client.post(f'/pacs/cases/{a}/links', json=payload).status_code == 409


def test_no_link_for_missing_case_study_or_unconfirmed_selection(archive, case_ids):
    a = case_ids[0]
    assert client.post(f'/pacs/cases/{a}/links', json={'study_uid': STUDY, 'acknowledge_case_match': False}).status_code == 422
    assert client.post('/pacs/cases/999999/links', json={'study_uid': STUDY, 'acknowledge_case_match': True}).status_code == 404
    assert client.post(f'/pacs/cases/{a}/links', json={'study_uid': '1.2.3.404', 'acknowledge_case_match': True}).status_code == 404
    assert client.get(f'/pacs/cases/{a}/links').json()['data']['items'] == []


def test_connection_unavailable_explicit_not_empty_archive(archive):
    config = copy.deepcopy(archive['config']); config['base_url'] = 'http://127.0.0.1:1'
    archive['path'].write_text(json.dumps(config), encoding='utf-8')
    assert client.get('/pacs/status').json()['data']['state'] == 'unavailable'
    assert client.get('/pacs/studies').status_code == 503


def test_wrong_server_password_never_exposes_credentials(archive):
    config = copy.deepcopy(archive['config']); config['password'] = 'SYNTHETIC-wrong-secret'
    archive['path'].write_text(json.dumps(config), encoding='utf-8')
    response = client.get('/pacs/studies')
    assert response.status_code == 503 and response.json()['detail']['reason'] == 'authentication_failed'
    assert 'SYNTHETIC-wrong-secret' not in response.text and SECRET not in response.text


def test_malformed_modality_attribute_is_explicit_upstream_failure(archive):
    archive['studies'][0]['00080061'] = ['not a DICOM attribute']
    response = client.get('/pacs/studies')
    assert response.status_code == 502 and response.json()['detail']['reason'] == 'invalid_metadata'
