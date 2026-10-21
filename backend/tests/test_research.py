import csv
import numpy as np
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.research.dataset import load_dataset
from app.research.federated import aggregate, partitions
from app.research.topsis import fuse, topsis_weights
from app.services import research_service


def test_topsis_dominance_and_equal_fallback():
    np.testing.assert_allclose(topsis_weights([[.9, .8, .1], [.7, .6, .3]]), [1, 0])
    np.testing.assert_allclose(topsis_weights([[.7, .6, .2]] * 3), np.ones(3) / 3)
    # Brier is a cost: lower is preferred when AUC and accuracy tie.
    np.testing.assert_allclose(topsis_weights([[.7, .6, .1], [.7, .6, .4]]), [1, 0])


def test_weighted_fusion_and_parameter_aggregation():
    np.testing.assert_allclose(fuse([[.2, .8], [.8, .2]], [.6, .4]), [.44, .56])
    np.testing.assert_allclose(aggregate([[1, 3], [5, 7]], [.25, .75]), [4, 6])
    with pytest.raises(ValueError):
        fuse([[.2, float('nan')]], [.5, .5])
    with pytest.raises(ValueError):
        aggregate([[1, 3], [5, 7]], [.2, .2])


def test_client_partitions_cover_only_train_and_label_skew():
    labels = np.array([0] * 9 + [1] * 9 + [0, 1])
    train = np.arange(18)
    for groups in partitions(train, labels, 20261006).values():
        joined = np.concatenate(groups)
        assert len(joined) == len(set(joined)) == 18
        assert set(joined) == set(train)
    skew = partitions(train, labels, 20261006)['label_skew']
    assert labels[skew[0]].sum() == 0 and labels[skew[-1]].sum() == len(skew[-1])


def write_tables(root):
    directory = root / 'downloads'
    directory.mkdir()
    clinical = [{'id': i, 'age': 50, 'female': 1, 'idh1/2': label, 'survival': 123}
                for i, label in [('101', '0'), ('102', '1'), ('103', '1'), ('104', ''), ('4', '0')]]
    radiomics = [{'identifier': i, 'mask_label': '2', 'original_firstorder_Mean': '2.5',
                 'diagnostics_mask': '999', 'error.T2w': 'failure' if i == '103' else '-'}
                for i in ['101', '102', '103', '104', '4']]
    for filename, rows in [('1_0_clinical_molecular_data.csv', clinical), ('4_radiomics_preop.csv', radiomics)]:
        with (directory / filename).open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), delimiter=';')
            writer.writeheader()
            writer.writerows(rows)
    return directory


def test_dataset_allowlist_and_patient_exclusions(tmp_path):
    directory = write_tables(tmp_path)
    data = load_dataset(tmp_path)
    assert data.ids == ['101', '102']
    assert data.audit['clinical_features'] == ['age', 'female']
    assert data.feature_names == ['original_firstorder_Mean']
    assert data.radiomics.shape == (2, 3) and np.isnan(data.radiomics[:, 0]).all()
    assert data.audit['unknown_label_ids'] == ['104']
    assert data.audit['error_patient_ids'] == ['103']
    # Repeated regions must never silently become independent patients.
    with (directory / '4_radiomics_preop.csv').open('a', encoding='utf-8') as handle:
        handle.write('101;2;2.5;999;-\n')
    with pytest.raises(ValueError, match='Duplicate'):
        load_dataset(tmp_path)


def test_research_unavailable_and_input_guards(monkeypatch, tmp_path):
    monkeypatch.setattr(research_service.settings, 'RESEARCH_DIR', str(tmp_path))
    with TestClient(app) as client:
        assert client.get('/research/summary').status_code == 503
        assert client.get('/research/patients/999').status_code == 404
        assert client.post('/research/clinical', json={'age': 121, 'female': False}).status_code == 422
