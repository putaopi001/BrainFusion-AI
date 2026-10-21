"""Synthetic inputs, isolated DB/accounts; prepared-job start is never clinical acceptance."""
import json
from concurrent.futures import Future
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.case import Case
from app.models.mri import MRI
from app.services import dicom_conversion_jobs as jobs
from test_dicom_conversion_registry import registered, _queued_job
from test_local_auth import account_config, login


@pytest.fixture
def prepared(registered, tmp_path, monkeypatch):
    import app.api.pacs as api
    config = registered['config'].model_copy(update={'allow_pixel_read': True})
    monkeypatch.setattr(api, 'load_config', lambda: config)
    job_id = 'e' * 32
    _queued_job(tmp_path, registered, job_id)
    return {**registered, 'job_id': job_id, 'config': config,
            'url': f"/pacs/cases/{registered['case_id']}/conversion-jobs/{job_id}/start"}


def test_start_uses_actual_cookie_csrf_and_worker_without_activating(prepared, account_config, monkeypatch):
    item = prepared
    client = TestClient(app)
    payload = {'expected_attempt': 1}
    assert client.post(item['url'], json=payload).status_code == 401
    state = login(client, 'research-test')
    assert client.post(item['url'], json=payload, headers={'X-BF-CSRF': state['csrf']}).status_code == 403
    state = login(client)
    assert client.post(item['url'], json=payload, headers={'X-BF-CSRF': 'wrong'}).status_code == 403
    assert client.post(item['url'], json={**payload, 'source_files': 'E:/must-not-be-accepted'},
                       headers={'X-BF-CSRF': state['csrf']}).status_code == 422
    original_submit = jobs.submit_job
    futures = []
    def submit(job_id):
        future = original_submit(job_id)
        futures.append(future)
        return future
    monkeypatch.setattr(jobs, 'submit_job', submit)
    with SessionLocal() as db:
        before = db.get(Case, item['case_id']).status, db.query(MRI).count()
    response = client.post(item['url'], json=payload, headers={'X-BF-CSRF': state['csrf']})
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store'
    data = response.json()['data']
    assert data['attempt'] == 1 and data['state'] == 'queued' and data['reviewer_authenticated']
    assert not data['model_input_eligible'] and not data['current_mri_replaced'] and not data['inference_performed']
    assert str(item['folder']) not in response.text and 'source_files' not in response.text
    assert len(futures) == 1
    result = futures[0].result(timeout=15)
    assert result['state'] == 'succeeded' and not result['inference_performed']
    assert result['all_voxels_compared'] == 72
    with SessionLocal() as db:
        assert before == (db.get(Case, item['case_id']).status, db.query(MRI).count())


@pytest.mark.parametrize('mode,expected', [('wrong_case', 404), ('stale', 409), ('running', 409),
    ('changed_input', 409), ('missing_input', 409), ('archive_changed', 409), ('read_disabled', 409), ('missing', 404)])
def test_start_rejects_stale_or_unbound_jobs_before_scheduling(prepared, account_config, monkeypatch, mode, expected):
    import app.api.pacs as api
    item = prepared
    path = jobs._job_file(item['job_id'])
    row = json.loads(path.read_text(encoding='utf-8'))
    if mode == 'wrong_case': row['case_id'] += 100000
    if mode == 'running': row['state'] = 'running'
    if mode == 'stale': row['attempt'] = 2
    if mode == 'changed_input':
        target = Path(row['inputs']['proposal']['path'])
        target.write_bytes(target.read_bytes() + b' ')
    if mode == 'missing_input': Path(row['inputs']['snapshots']['path']).unlink()
    if mode == 'archive_changed':
        monkeypatch.setattr(api, 'load_config', lambda: item['config'].model_copy(update={'archive_id': 'different'}))
    if mode == 'read_disabled':
        monkeypatch.setattr(api, 'load_config', lambda: item['config'].model_copy(update={'allow_pixel_read': False}))
    path.write_text(json.dumps(row), encoding='utf-8')
    monkeypatch.setattr(jobs, 'submit_job', lambda *_a, **_k: pytest.fail('Rejected job must not schedule'))
    client = TestClient(app)
    state = login(client)
    url = item['url'].replace(item['job_id'], 'f' * 32) if mode == 'missing' else item['url']
    before = path.read_bytes()
    response = client.post(url, json={'expected_attempt': 1}, headers={'X-BF-CSRF': state['csrf']})
    assert response.status_code == expected, response.text
    assert path.read_bytes() == before


def test_queue_deduplicates_one_attempt_and_allows_retry_before_old_future_callback(prepared, monkeypatch):
    calls = []
    class Executor:
        def submit(self, *args, **kwargs):
            future = Future()
            calls.append((future, args, kwargs))
            return future
    monkeypatch.setattr(jobs, '_JOB_EXECUTOR', Executor())
    item = prepared
    first = jobs.submit_job(item['job_id'])
    assert jobs.submit_job(item['job_id']) is first and len(calls) == 1
    path = jobs._job_file(item['job_id'])
    row = json.loads(path.read_text(encoding='utf-8'))
    row['state'] = 'failed'
    path.write_text(json.dumps(row), encoding='utf-8')
    jobs.retry_job(item['job_id'], item['case_id'], 1)
    second = jobs.submit_job(item['job_id'])
    assert second is not first and len(calls) == 2
    assert calls[0][2]['expected_attempt'] == 1 and calls[1][2]['expected_attempt'] == 2
    first.set_result(None)
    assert jobs.submit_job(item['job_id']) is second
    second.set_result(None)


def test_path_guard_failure_is_persisted_and_stale_worker_does_not_run(prepared):
    item = prepared
    path = jobs._job_file(item['job_id'])
    row = json.loads(path.read_text(encoding='utf-8'))
    row['output_base'] = 'E:/' + ('long-path/' * 35) + 'output'
    path.write_text(json.dumps(row), encoding='utf-8')
    result = jobs.run_job(item['job_id'], expected_attempt=1)
    assert result['state'] == 'failed' and result['reason'] == 'conversion_output_path_too_long'
    jobs.retry_job(item['job_id'], item['case_id'], 1)
    with pytest.raises(jobs.PlanError) as error:
        jobs.run_job(item['job_id'], expected_attempt=1)
    assert error.value.reason == 'conversion_job_stale'
    assert jobs._read_job(item['job_id'])['state'] == 'queued'


def test_cli_prepare_only_persists_inputs_without_running_model_or_converter(registered, tmp_path, monkeypatch, capsys):
    from tools import convert_dicom_model_input as cli
    source = tmp_path / 'cli-source-files.json'
    source.write_text(json.dumps(registered['files']), encoding='utf-8')
    monkeypatch.setattr(cli, 'run_job', lambda *_a: pytest.fail('Prepare-only must not run conversion'))
    result = cli.main(['--proposal', registered['row']['proposal_path'], '--snapshots', registered['row']['snapshots_path'],
        '--source-files', str(source), '--output-dir', str(tmp_path / 'web-output'), '--job-id', '9' * 32, '--prepare-only'])
    assert result == 0
    data = json.loads(capsys.readouterr().out)
    assert data['job']['state'] == 'queued' and data['inference_performed'] is False
    assert not (tmp_path / 'web-output').exists()
