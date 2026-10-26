import hashlib
import json

import nibabel as nib
import numpy as np
from fastapi.testclient import TestClient

from app.api import upenn_sub002_research as research
from app.main import app
from app.services.local_auth import require_doctor


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_read_only_upenn_sub002_manifest_and_files(tmp_path, monkeypatch):
    inputs, result, evidence = (tmp_path / name for name in ('inputs', 'result', 'evidence'))
    for directory in (inputs, result, evidence):
        directory.mkdir()
    monkeypatch.setattr(research.settings, 'UPENN_SUB002_INPUT_DIR', str(inputs))
    monkeypatch.setattr(research.settings, 'UPENN_SUB002_RESULT_DIR', str(result))
    monkeypatch.setattr(research.settings, 'UPENN_SUB002_EVIDENCE_DIR', str(evidence))
    monkeypatch.setattr(research, 'EXPECTED_INPUTS', {})
    input_rows = {}
    for key in ('t1c', 't1n', 't2w', 't2f'):
        path = inputs / f'{key}.nii.gz'
        image = nib.Nifti1Image(np.ones((4, 4, 4), dtype=np.float32), np.diag([1, 1, 1, 1]))
        image.header.set_xyzt_units('mm')
        nib.save(image, path)
        input_rows[key] = (path.name, _sha(path))
    monkeypatch.setattr(research, 'EXPECTED_INPUTS', input_rows)
    mask = result / 'prediction.nii.gz'
    mask_image = nib.Nifti1Image(np.zeros((4, 4, 4), dtype=np.uint8), np.diag([1, 1, 1, 1]))
    mask_image.header.set_xyzt_units('mm')
    nib.save(mask_image, mask)
    monkeypatch.setattr(research, 'PREDICTION_SHA', _sha(mask))
    overlay = result / 'tri-planar-overlay.png'
    overlay.write_bytes(b'run-overlay')
    monkeypatch.setattr(research, 'RUN_OVERLAY_SHA', _sha(overlay))
    spatial = result / 'spatial-qc.json'
    spatial.write_text(json.dumps({'status': 'PASS', 'shape_match': True, 'affine_match': True,
                                   'prediction_shape': [4, 4, 4], 'spacing_mm': [1, 1, 1], 'orientation': ['R', 'A', 'S']}))
    monkeypatch.setattr(research, 'SPATIAL_QC_SHA', _sha(spatial))
    run = result / research.RUN_EVIDENCE
    run.write_text(json.dumps({'mask_sha256': research.PREDICTION_SHA,
                               'input_sha256': {key: item[1] for key, item in input_rows.items()},
                               'model': 'synthetic fixture', 'revision': 'test', 'checkpoint_sha256': 'a' * 64,
                               'device': 'cpu', 'purpose': 'SYNTHETIC_TEST', 'reference_mask_used_for_inference': False,
                               'volumes': {key: {'ml': 0.0} for key in ('WT', 'TC', 'ET')}}))
    monkeypatch.setattr(research, 'RUN_EVIDENCE_SHA', _sha(run))
    metrics_path = evidence / 'segmentation-metrics.json'
    metrics_path.write_text(json.dumps({'claim_scope': 'synthetic only', 'training_overlap_status': 'unknown',
                                        'expert_review_status': 'not applicable', 'metrics': {key: {'dice': 1.0}
                                        for key in ('WT', 'TC', 'ET')},
                                        'files': {'official_local_reference': {'sha256': 'b' * 64}}}))
    monkeypatch.setattr(research, 'METRICS_SHA', _sha(metrics_path))
    metrics_csv = evidence / 'segmentation-metrics.csv'
    metrics_csv.write_text('region,dice\nWT,1.0\n')
    monkeypatch.setattr(research, 'METRICS_CSV_SHA', _sha(metrics_csv))
    review_overlay = evidence / 'segmentation-overlay-review.png'
    review_overlay.write_bytes(b'review-overlay')
    monkeypatch.setattr(research, 'OVERLAY_SHA', _sha(review_overlay))
    app.dependency_overrides[require_doctor] = lambda: {'id': 'synthetic-doctor', 'role': 'doctor'}
    try:
        with TestClient(app) as client:
            response = client.get('/api/research/upenn-sub002/manifest')
            assert response.status_code == 200
            payload = response.json()['data']
            assert payload['case_link_status'] == 'UNLINKED_RESEARCH_CASE'
            assert payload['reference_agreement']['status'] == 'PUBLIC_REFERENCE_AGREEMENT'
            assert payload['prediction']['sha256'] == research.PREDICTION_SHA
            assert client.get(payload['prediction']['url']).content == mask.read_bytes()
            assert client.get('/api/research/upenn-sub002/files/../../secrets').status_code == 404
    finally:
        app.dependency_overrides.pop(require_doctor, None)


def test_upenn_sub002_viewer_is_disabled_without_runtime_configuration(monkeypatch, tmp_path):
    missing = tmp_path / 'not-configured'
    monkeypatch.setattr(research.settings, 'UPENN_SUB002_INPUT_DIR', '')
    monkeypatch.setattr(research.settings, 'UPENN_SUB002_RESULT_DIR', str(missing))
    monkeypatch.setattr(research.settings, 'UPENN_SUB002_EVIDENCE_DIR', str(missing))
    app.dependency_overrides[require_doctor] = lambda: {'id': 'synthetic-doctor', 'role': 'doctor'}
    try:
        with TestClient(app) as client:
            assert client.get('/api/research/upenn-sub002/manifest').status_code == 404
    finally:
        app.dependency_overrides.pop(require_doctor, None)
