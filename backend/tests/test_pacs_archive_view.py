"""Read-only Stage7 archive viewing contracts. No real Orthanc requests."""
import hashlib

import pytest
from fastapi import HTTPException

from app.api import pacs
from app.services.pacs_client import PacsConfig

STUDY = '1.2.840.999.11'
SERIES = '1.2.840.999.12'
INSTANCE = '1.2.840.999.13'
FINGERPRINT = 'a' * 64
METADATA_HASH = 'b' * 64


def config(pixel_read=True):
    return PacsConfig(format_version=1, archive_id='stage7-orthanc',
        base_url='http://127.0.0.1:18142', username='synthetic-user',
        password='SYNTHETIC-password', allow_pixel_read=pixel_read,
        expected_database_server_identifier='SYNTHETIC-server-id')


class Archive:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None


def test_archive_manifest_is_explicitly_unlinked_and_uses_archive_frame_route(monkeypatch):
    cfg = config()
    monkeypatch.setattr(pacs, 'load_config', lambda: cfg)
    monkeypatch.setattr(pacs, 'ReconciliationClient', lambda value: Archive(value))
    source = {'format': 'dicom-series-view-manifest-v1', 'study_uid': STUDY,
        'series_uid': SERIES, 'archive_id': cfg.archive_id, 'metadata_sha256': METADATA_HASH,
        'archive_fingerprint': cfg.endpoint_fingerprint, 'instance_count': 1,
        'pixel_read_enabled': True, 'archive_server_identity_pinned': True,
        'geometry': {}, 'instances': [{'instance_uid': INSTANCE,
            'metadata_sha256': METADATA_HASH, 'metadata': {'7FE00010': {'vr': 'OW', 'BulkDataURI': 'upstream'}}}]}
    monkeypatch.setattr(pacs, 'series_manifest', lambda *_: source)

    result = pacs.view_manifest(STUDY, SERIES)['data']

    assert result['archive_only'] is True
    assert result['source_case_id'] is None
    assert result['transport_enabled'] is True
    assert result['saved_dicom_annotations_available'] is False
    assert result['dicom_view_state_available'] is False
    assert result['segmentation_overlay_available'] is False
    bulk_uri = result['instances'][0]['metadata']['7FE00010']['BulkDataURI']
    assert bulk_uri.startswith(f'/pacs/archive/studies/{STUDY}/series/{SERIES}/instances/{INSTANCE}/frames/1?')
    assert f'archive_fingerprint={cfg.endpoint_fingerprint}' in bulk_uri


def test_archive_frame_rechecks_source_revision_and_returns_no_store(monkeypatch):
    cfg = config()
    monkeypatch.setattr(pacs, 'load_config', lambda: cfg)
    monkeypatch.setattr(pacs, 'ReconciliationClient', lambda value: Archive(value))
    item = {'00080018': {'Value': [INSTANCE]}}
    monkeypatch.setattr(pacs, 'checked_metadata', lambda *_: (item, {'safe': True}))
    monkeypatch.setattr(pacs, 'metadata_revision', lambda _: METADATA_HASH)
    monkeypatch.setattr(pacs, 'frame_bytes', lambda *args: b'synthetic-frame-bytes')
    monkeypatch.setattr(pacs, 'multipart_response', lambda body: (body, 'multipart/related; type="application/octet-stream"'))

    response = pacs.archive_frame(STUDY, SERIES, INSTANCE, 1, METADATA_HASH, cfg.endpoint_fingerprint)

    assert response.status_code == 200
    assert response.body == b'synthetic-frame-bytes'
    assert response.headers['cache-control'] == 'no-store'


def test_archive_frame_rejects_stale_fingerprint_before_archive_access(monkeypatch):
    cfg = config()
    monkeypatch.setattr(pacs, 'load_config', lambda: cfg)
    monkeypatch.setattr(pacs, 'ReconciliationClient', lambda *_: pytest.fail('must not contact archive'))

    with pytest.raises(HTTPException) as error:
        pacs.archive_frame(STUDY, SERIES, INSTANCE, 1, METADATA_HASH, hashlib.sha256(b'stale').hexdigest())
    assert error.value.status_code == 409
