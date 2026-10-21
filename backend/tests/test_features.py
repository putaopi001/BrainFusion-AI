import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.linear_model import LogisticRegression
from app.main import app
from app.research.feature_contract import selected_features, feature_matrix
from app.services import feature_jobs


def test_unselected_missing_features_preserve_selected_model_output():
    x = np.array([[9, -2, 1], [2, -1, 3], [1, 1, 2], [4, 2, 5]], dtype=float)
    y = np.array([0, 0, 1, 1])
    pipeline = make_pipeline(SimpleImputer(keep_empty_features=True), StandardScaler(), SelectKBest(f_classif, k=1), LogisticRegression())
    pipeline.fit(x, y)
    bundle = {'feature_names': ['original_firstorder_Mean'], 'models': {'reference_mask_radiomics': pipeline}}
    selected = selected_features(bundle)
    assert selected == ['2:original_firstorder_Mean']
    matrix = feature_matrix(bundle, {selected[0]: .5})
    np.testing.assert_allclose(pipeline.predict_proba(matrix), pipeline.predict_proba([[999, .5, -999]]))
    with pytest.raises(ValueError, match='contract'):
        feature_matrix(bundle, {'3:original_firstorder_Mean': .5})
    with pytest.raises(ValueError, match='Nonfinite'):
        feature_matrix(bundle, {selected[0]: float('inf')})


def test_stale_compatibility_gate_blocks_model_transfer(tmp_path, monkeypatch):
    summary = {'run_id': 'test', 'artifact_sha256': {'models.joblib': 'expected'}}
    selector = SimpleNamespace(get_support=lambda **kwargs: np.array([0]))
    bundle = {'feature_names': ['original_firstorder_Mean'], 'data_sha256': {},
              'models': {'reference_mask_radiomics': SimpleNamespace(named_steps={'selectkbest': selector})}}
    worker = tmp_path / 'python.exe'
    worker.write_bytes(b'test worker')
    (tmp_path / 'source.json').write_text('{}')
    monkeypatch.setattr(feature_jobs.settings, 'RADIOMICS_PYTHON', str(worker))
    audit = {'status': 'passed', 'research_run_id': 'test', 'model_sha256': 'changed'}
    path = tmp_path / 'compatibility.json'
    path.write_text(json.dumps(audit), encoding='utf-8')
    monkeypatch.setattr(feature_jobs.settings, 'RADIOMICS_COMPATIBILITY', str(path))
    with pytest.raises(ValueError, match='stale'):
        feature_jobs.compatibility(summary, bundle)


def make_state(tmp_path, monkeypatch, state='running'):
    monkeypatch.setattr(feature_jobs.settings, 'FEATURE_JOBS_DIR', str(tmp_path))
    directory = tmp_path / '1' / ('a' * 32) / ('b' * 32)
    directory.mkdir(parents=True)
    job = {'id': 'b' * 32, 'case_id': 1, 'analysis_run_id': 'a' * 32, 'state': state, 'result': {'old': True}, 'error': None}
    feature_jobs.save(directory, job)
    return directory


def test_interrupted_feature_jobs_are_failed_without_result(tmp_path, monkeypatch):
    directory = make_state(tmp_path, monkeypatch)
    feature_jobs.recover_interrupted()
    result = json.loads((directory / 'state.json').read_text())
    assert result['state'] == 'failed' and result['result'] is None
    assert 'restarted' in result['error']


def test_worker_failure_does_not_return_prediction(tmp_path, monkeypatch):
    directory = make_state(tmp_path, monkeypatch, 'queued')
    (directory / 'request.json').write_text('{}')
    def fail(*args, **kwargs):
        raise RuntimeError('Intentional extraction failure')
    monkeypatch.setattr(feature_jobs.subprocess, 'run', fail)
    feature_jobs.execute(directory)
    result = json.loads((directory / 'state.json').read_text())
    assert result['state'] == 'failed' and result['result'] is None


def test_current_analysis_hides_old_feature_results(tmp_path, monkeypatch):
    make_state(tmp_path, monkeypatch, 'succeeded')
    monkeypatch.setattr(feature_jobs, 'latest_mri', lambda *args: SimpleNamespace(analysis_run_id='c' * 32))
    assert feature_jobs.current(1, None) is None


def test_feature_api_input_guards():
    with TestClient(app) as client:
        assert client.get('/research/cases/999999/features').status_code == 404
        assert client.post('/research/cases/999999/features', json={'age': 121, 'female': False}).status_code == 422
