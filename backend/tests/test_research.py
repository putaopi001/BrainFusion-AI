import csv
import numpy as np
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.research.dataset import load_dataset
from app.research.federated import aggregate, partitions
from app.research.topsis import fuse, topsis_weights
from app.research.survival import (EndpointContract, concordance_index, cox_ph, kaplan_meier,
                                   public_validation, validate_endpoint)
from app.services import feature_jobs
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


def test_survival_contract_requires_explicit_authorized_common_origin():
    rows = [
        {'pid': 'SYNTHETIC-1', 'days': 2, 'status': 'event', 'origin': 'diagnosis'},
        {'pid': 'SYNTHETIC-2', 'days': 3, 'status': 'censored', 'origin': 'diagnosis'},
        {'pid': 'SYNTHETIC-3', 'days': 4, 'status': 'event', 'origin': 'diagnosis'},
    ]
    contract = EndpointContract('OS', 'pid', 'days', 'status', 'origin', 'diagnosis',
                                'days', 'event', 'censored', True)
    audit = validate_endpoint(rows, contract)
    assert audit['eligible'] is True
    assert (audit['sample_count'], audit['event_count'], audit['censored_count']) == (3, 2, 1)
    assert '_validated_rows' not in public_validation(audit)
    km = kaplan_meier(audit)
    assert km['median_survival'] == 4
    assert [point['time'] for point in km['points']] == [2, 3, 4]
    assert km['points'][1]['events'] == 0 and km['points'][1]['censored_at_time'] == 1
    assert km['points'][0]['at_risk'] == 3 and km['points'][0]['survival'] == pytest.approx(2 / 3)

    mixed = [dict(rows[0]), {**rows[1], 'origin': 'surgery'}, dict(rows[2])]
    rejected = validate_endpoint(mixed, contract)
    assert rejected['eligible'] is False
    assert 'row_1:time_origin_mismatch' in rejected['issues']
    with pytest.raises(ValueError, match='validated and authorized'):
        kaplan_meier(rejected)


def test_survival_contract_rejects_unauthorized_duplicate_invalid_rows():
    rows = [
        {'pid': 'SYNTHETIC-1', 'days': 0, 'status': 'event', 'origin': 'diagnosis'},
        {'pid': 'SYNTHETIC-1', 'days': 2, 'status': 'unknown', 'origin': 'diagnosis'},
    ]
    contract = EndpointContract('OS', 'pid', 'days', 'status', 'origin', 'diagnosis',
                                'days', '1', '0', False)
    audit = validate_endpoint(rows, contract)
    assert audit['eligible'] is False
    assert 'research_use_not_authorized' in audit['issues']
    assert 'row_0:duration_nonpositive_or_nonfinite' in audit['issues']
    assert 'row_1:duplicate_patient' in audit['issues']
    with pytest.raises(ValueError, match='validated and authorized'):
        kaplan_meier(audit)


def test_kaplan_meier_keeps_survival_at_one_before_first_event():
    rows = [
        {'pid': 'SYNTHETIC-CENSOR', 'days': 1, 'status': 'censored', 'origin': 'diagnosis'},
        {'pid': 'SYNTHETIC-EVENT', 'days': 2, 'status': 'event', 'origin': 'diagnosis'},
    ]
    contract = EndpointContract('OS', 'pid', 'days', 'status', 'origin', 'diagnosis',
                                'days', 'event', 'censored', True)
    km = kaplan_meier(validate_endpoint(rows, contract))
    assert km['points'][0]['survival'] == 1
    assert km['points'][0]['ci95_lower'] == km['points'][0]['ci95_upper'] == 1


def test_cox_ph_and_c_index_use_only_authorized_synthetic_rows():
    rng = np.random.default_rng(731)
    count = 160
    feature = rng.normal(size=count)
    event_time = rng.exponential(scale=np.exp(-0.8 * feature))
    censor_time = rng.exponential(scale=1.7, size=count)
    durations = np.minimum(event_time, censor_time) + 0.01
    events = (event_time <= censor_time).astype(int)
    rows = [{'pid': f'SYNTHETIC-{i}', 'duration': float(durations[i]),
             'status': str(events[i]), 'origin': 'synthetic-origin'} for i in range(count)]
    contract = EndpointContract('OS', 'pid', 'duration', 'status', 'origin', 'synthetic-origin',
                                'years', '1', '0', True)
    validation = validate_endpoint(rows, contract)
    fitted = cox_ph(validation, feature[:, None], ['synthetic_signal'], l2=0.05)
    risk = feature * fitted['coefficients']['synthetic_signal']
    c_index = concordance_index(durations, events, risk)

    assert fitted['converged'] is True
    assert fitted['coefficients']['synthetic_signal'] > 0
    assert fitted['individual_predictions_available'] is False
    assert fitted['proportional_hazards_screening']['formal_test'] is False
    assert c_index > 0.65


def test_cox_rejects_blocked_rows_and_unspecified_imputation():
    rows = [{'pid': 'SYNTHETIC-1', 'duration': 1, 'status': '1', 'origin': 'diagnosis'}]
    contract = EndpointContract('OS', 'pid', 'duration', 'status', 'origin', 'diagnosis',
                                'days', '1', '0', False)
    validation = validate_endpoint(rows, contract)
    with pytest.raises(ValueError, match='validated and authorized'):
        cox_ph(validation, np.ones((1, 1)), ['feature'])


def test_individual_survival_api_never_returns_heuristic_months():
    from app.services.survival_service import predict_survival
    result = predict_survival({'intensity': {'max': 1000}, 'shape': {'tumor_fraction': 0.2}}, 72)
    assert result['status'] == 'BLOCKED_BY_DATA'
    assert result['individual_prediction_available'] is False
    assert 'estimated_survival_months' not in result


def test_research_feature_csv_exports_only_current_successful_result(monkeypatch):
    state = {
        'state': 'succeeded', 'stale': False, 'analysis_run_id': 'analysis-synthetic',
        'research_run_id': 'research-synthetic',
        'result': {
            'contract_sha256': 'contract-digest', 'feature_source': 'automatic model mask',
            'device': 'cpu', 'versions': {'pyradiomics': '3.1.0'},
            'protocol': {'id': 'synthetic-protocol', 'radiomics_settings': {'binWidth': 0.02}},
            'input_sha256': {'t1c': 'input-digest'}, 'mask_sha256': 'mask-digest',
            'extraction_seconds': 1.25, 'region_voxel_counts': {'1': 3, '2': 0},
            'selected_features': {'1:original_glcm_Contrast': 0.25, '2:original_shape_Volume': None},
        },
    }
    monkeypatch.setattr(feature_jobs, 'current', lambda case_id, db: state)
    with TestClient(app) as client:
        response = client.get('/research/cases/9001/features.csv')
        assert response.status_code == 200
        assert 'text/csv' in response.headers['content-type']
        assert 'attachment;' in response.headers['content-disposition']
        rows = list(csv.DictReader(response.text.splitlines()))
        assert len(rows) == 2
        assert rows[0]['analysis_run_id'] == 'analysis-synthetic'
        assert rows[0]['mask_sha256'] == 'mask-digest'
        assert rows[0]['feature_name'] == 'original_glcm_Contrast'
        assert 'synthetic-protocol' in rows[0]['radiomics_protocol_json']
        assert rows[1]['value'] == '' and rows[1]['noncomputable_reason'] == 'empty mask region'

    monkeypatch.setattr(feature_jobs, 'current', lambda case_id, db: {**state, 'stale': True})
    with TestClient(app) as client:
        assert client.get('/research/cases/9001/features.csv').status_code == 409
