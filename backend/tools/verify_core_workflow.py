"""Exercise actual uploads, subprocess inference, viewing and version guards."""
import json
import os
import time
from contextlib import ExitStack
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ROOT = Path('E:/BrainFusion-Runtime/results/stage2')
ROOT.mkdir(parents=True, exist_ok=True)
os.environ['DATABASE_URL'] = 'sqlite:///' + (ROOT / 'workflow.db').as_posix()
from fastapi.testclient import TestClient
from app.main import app
from app.services.segmentation_metrics import evaluate

DATA = Path('E:/BrainFusion-Data/WAW-GliomAI-v3/sample')


def wait(client, case_id):
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        response = client.get(f'/analysis/{case_id}')
        assert response.status_code == 200, response.text
        run = response.json()['data']
        if run['state'] in ('succeeded', 'failed'):
            assert run['state'] == 'succeeded', run
            return run
        time.sleep(1)
    raise TimeoutError('Analysis exceeded five minutes')


def main():
    records = []
    with TestClient(app) as client:
        for sample_id in (4, 13, 16, 17, 19):
            patient = client.post('/patients/', json={'name': f'Engineering sample {sample_id}', 'age': 50, 'gender': 'other'})
            assert patient.status_code == 200, patient.text
            case = client.post('/cases/create', json={'patient_id': patient.json()['data']['id'], 'description': 'Real-data engineering validation'})
            assert case.status_code == 200, case.text
            case_id = case.json()['data']['case_id']
            with ExitStack() as stack:
                files = {seq: (f'{seq}.nii.gz', stack.enter_context((DATA / 'images/gliomai_preop_scans_renamed' / str(sample_id) / f'{sample_id}_0_brain_{seq}.nii.gz').open('rb')), 'application/gzip') for seq in ('t1c', 't1n', 't2w', 't2f')}
                uploaded = client.post(f'/studies/{case_id}', files=files)
                assert uploaded.status_code == 200, uploaded.text
            started = client.post(f'/analysis/{case_id}')
            assert started.status_code == 202, started.text
            assert client.post(f'/analysis/{case_id}').status_code == 409
            run = wait(client, case_id)
            detail = client.get(f'/cases/{case_id}/detail').json()['data']
            assert detail['prediction'] is None
            assert detail['report']['analysis_run_id'] == run['id']
            assert client.post(f'/mri/{case_id}/verify', params={'run_id': 'stale'}).status_code == 409
            assert client.post(f'/mri/{case_id}/verify', params={'run_id': run['id']}).status_code == 200
            meta = client.get(f'/mri/{case_id}/volume')
            assert meta.status_code == 200, meta.text
            assert meta.json()['data']['shape'] == [155, 240, 240]
            overlay = client.get(f'/mri/{case_id}/segmentation')
            assert overlay.status_code == 200, overlay.text
            metrics = evaluate(Path(run['result']['mask_path']), DATA / 'reference_masks/preop_masks' / str(sample_id) / f'{sample_id}_0_tumor_mask_pre.nii.gz')
            records.append({'sample_id': sample_id, 'case_id': case_id, 'run': run, 'metrics': metrics, 'volume_metadata': meta.json()['data']})
            (ROOT / 'workflow_validation.json').write_text(json.dumps({'status': 'in_progress', 'samples': records}, indent=2), encoding='utf-8')
            print(f'Sample {sample_id}: upload, inference, report, geometry and verification PASS', flush=True)
        # Re-analysis invalidates previous confirmation and report immediately.
        old_id = run['id']
        assert client.post(f'/analysis/{case_id}').status_code == 202
        detail = client.get(f'/cases/{case_id}/detail').json()['data']
        assert not detail['mri']['doctor_verified']
        assert detail['report'] is None
        assert client.post(f'/mri/{case_id}/verify', params={'run_id': old_id}).status_code == 409
        new_run = wait(client, case_id)
        assert new_run['id'] != old_id
        assert len(client.get(f'/analysis/{case_id}/history').json()['data']) == 2
    (ROOT / 'workflow_validation.json').write_text(json.dumps({'status': 'passed', 'samples': records, 'reanalysis_guards': 'passed'}, indent=2), encoding='utf-8')
    print('All five real-data workflows and re-analysis guards PASS')


if __name__ == '__main__':
    main()
