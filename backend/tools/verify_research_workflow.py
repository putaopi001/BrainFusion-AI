"""Validate persisted research artifacts and real public-data API inputs on CPU."""
import json
import os
import sys
from pathlib import Path
from uuid import uuid4
import numpy as np

ROOT = Path('E:/BrainFusion-Runtime/results/stage4')
ROOT.mkdir(parents=True, exist_ok=True)
DATABASE = ROOT / ('verify_' + uuid4().hex + '.db')
os.environ['DATABASE_URL'] = 'sqlite:///' + DATABASE.as_posix()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.main import app
from app.database import engine


def main():
    with TestClient(app) as client:
        response = client.get('/research/summary')
        assert response.status_code == 200, response.text
        summary = response.json()['data']
        sets = [set(values) for values in summary['split']['patient_ids'].values()]
        assert not any(sets[i] & sets[j] for i in range(3) for j in range(i + 1, 3))
        assert len(set.union(*sets)) == 141
        records = []
        for patient_id in ('4', '13', '16', '17', '19'):
            response = client.get(f'/research/patients/{patient_id}')
            assert response.status_code == 200, response.text
            item = response.json()['data']
            assert not any(patient_id in subset for subset in sets)
            assert item['run_id'] == summary['run_id']
            for method, value in item['probabilities'].items():
                assert np.isfinite(value) and 0 <= value <= 1
                if method != 'fixed':
                    np.testing.assert_allclose(value, summary['development_predictions'][patient_id][method])
            clinical = client.post('/research/clinical', json={'age': int(item['clinical_input']['age']), 'female': bool(item['clinical_input']['female'])})
            assert clinical.status_code == 200
            np.testing.assert_allclose(clinical.json()['data']['probability'], item['probabilities']['clinical'])
            records.append(item)
        assert next(item for item in records if item['source_patient_id'] == '19')['reference_label'] is None
        for method in summary['federated']['methods'].values():
            if 'round_trace' not in method:
                continue
            clients = method['client_patient_ids']
            assert sum(map(len, clients)) == 98 and set().union(*map(set, clients)) == sets[0]
            assert all(abs(sum(item['weights']) - 1) < 1e-10 for item in method['round_trace'])
        assert client.get('/research/patients/999').status_code == 404
        assert client.post('/research/clinical', json={'age': -1, 'female': False}).status_code == 422
    result = {'status': 'passed', 'run_id': summary['run_id'], 'device': 'cpu', 'samples': records,
              'patient_partition': 'passed', 'all_round_weights': 'passed', 'clinical_model': 'passed',
              'reload_probability_comparison': 'passed', 'input_guards': 'passed'}
    (ROOT / 'api_validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Five public-data research predictions, persisted models, partitions and API guards PASS')


if __name__ == '__main__':
    try:
        main()
    finally:
        engine.dispose()
        DATABASE.unlink(missing_ok=True)
