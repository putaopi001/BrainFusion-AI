"""Use five existing successful segmentations; no inference or training rerun."""
import json
import os
from pathlib import Path
import sys
import time
import numpy as np

ROOT = Path('E:/BrainFusion-Runtime/results/stage6')
ROOT.mkdir(parents=True, exist_ok=True)
os.environ['DATABASE_URL'] = 'sqlite:///E:/BrainFusion-Runtime/results/stage2/workflow.db'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.main import app
from app.research.dataset import load_dataset


def main():
    workflow = json.loads(Path('E:/BrainFusion-Runtime/results/stage2/workflow_validation.json').read_text(encoding='utf-8'))
    dataset = load_dataset('E:/BrainFusion-Data/WAW-GliomAI-v3')
    records = []
    with TestClient(app) as client:
        for sample in workflow['samples']:
            case_id, source_id = sample['case_id'], str(sample['sample_id'])
            before = client.get(f'/cases/{case_id}/detail').json()['data']
            clinical, _ = dataset.matrices([source_id])
            inputs = {'age': int(clinical[0, 0]), 'female': bool(clinical[0, 1])}
            response = client.post(f'/research/cases/{case_id}/features', json=inputs)
            assert response.status_code == 202, response.text
            job = response.json()['data']
            if job['state'] != 'succeeded':
                assert client.post(f'/research/cases/{case_id}/features', json=inputs).status_code == 409
            deadline = time.monotonic() + 200
            while job['state'] in ('queued', 'running') and time.monotonic() < deadline:
                time.sleep(.5)
                job = client.get(f'/research/cases/{case_id}/features').json()['data']
            assert job['state'] == 'succeeded', job
            assert job['analysis_run_id'] == before['mri']['analysis_run_id']
            assert job['result']['feature_source'] == 'automatic model mask'
            assert job['result']['device'] == 'cpu'
            assert len(job['result']['selected_features']) == 20
            for value in job['result']['probabilities'].values():
                assert np.isfinite(value) and 0 <= value <= 1
            cached = client.post(f'/research/cases/{case_id}/features', json=inputs).json()['data']
            assert cached['id'] == job['id'] and cached['cache_hit']
            after = client.get(f'/cases/{case_id}/detail').json()['data']
            assert after['mri']['doctor_verified'] == before['mri']['doctor_verified']
            assert after['mri']['verified_run_id'] == before['mri']['verified_run_id']
            assert after['report'] == before['report']
            reference = client.get(f'/research/patients/{source_id}').json()['data']
            records.append({'source_patient_id': source_id, 'case_id': case_id, 'job': job,
                            'reference_mask_probabilities': reference['probabilities'],
                            'reference_label': reference['reference_label'],
                            'existing_report_and_confirmation': 'preserved', 'cache': 'passed'})
            (ROOT / 'automatic_validation.json').write_text(json.dumps({'status': 'in_progress', 'samples': records}, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'Automatic-mask features {source_id}, case {case_id}: CPU extraction, version, prediction, cache PASS', flush=True)
    result = {'status': 'passed', 'gpu_used': False, 'new_segmentation_or_training': False,
              'scope': 'five engineering cases; transfer from reference-trained model, not independent performance', 'samples': records}
    (ROOT / 'automatic_validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
