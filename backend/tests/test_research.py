import csv
import hashlib
import json
from pathlib import Path
import numpy as np
import nibabel as nib
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
from app.database import SessionLocal
from app.models.analysis_run import AnalysisRun
from app.models.case import Case
from app.models.mri import MRI
from app.services.local_auth import require_doctor
from app.core.config import settings


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


def test_survival_api_exposes_blocked_status_and_validated_synthetic_km_cox():
    contract = {
        'endpoint': 'OS', 'patient_id': 'pid', 'duration': 'days', 'event': 'status',
        'time_origin': 'origin', 'expected_time_origin': 'diagnosis', 'time_unit': 'days',
        'event_value': 'event', 'censored_value': 'censored', 'research_use_authorized': True,
    }
    rows = [
        {'pid': f'SYNTHETIC-{index}', 'days': index + 1,
         'status': 'event' if index < 6 else 'censored', 'origin': 'diagnosis'}
        for index in range(8)
    ]
    with TestClient(app) as client:
        status = client.get('/research/survival/status')
        assert status.status_code == 200
        assert status.json()['data']['research_status'] == 'BLOCKED_BY_DATA'
        assert status.json()['data']['individual_predictions_available'] is False
        assert status.json()['data']['api_scope'] == 'synthetic_engineering_only'

        denied = client.post('/research/survival/kaplan-meier', json={
            'dataset_scope': 'synthetic_engineering',
            'contract': {**contract, 'research_use_authorized': False}, 'rows': rows,
        })
        assert denied.status_code == 409
        assert 'research_use_not_authorized' in denied.json()['detail']['validation']['issues']

        non_synthetic = client.post('/research/survival/kaplan-meier', json={
            'dataset_scope': 'synthetic_engineering', 'contract': contract,
            'rows': [{**rows[0], 'pid': 'unapproved-record'}, *rows[1:]],
        })
        assert non_synthetic.status_code == 403

        km = client.post('/research/survival/kaplan-meier', json={
            'dataset_scope': 'synthetic_engineering', 'contract': contract, 'rows': rows,
        })
        assert km.status_code == 200
        assert km.json()['data']['sample_count'] == 8
        assert km.json()['data']['event_count'] == 6
        assert km.json()['data']['scope'] == 'research summary; not an individual prediction'

        cox = client.post('/research/survival/cox', json={
            'dataset_scope': 'synthetic_engineering', 'contract': contract, 'rows': rows,
            'features': [[float(i), float((i * i) % 7)] for i in range(8)],
            'feature_names': ['synthetic_a', 'synthetic_b'], 'l2': 0.1,
        })
        assert cox.status_code == 200
        assert set(cox.json()['data']['coefficients']) == {'synthetic_a', 'synthetic_b'}
        assert cox.json()['data']['individual_predictions_available'] is False


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


def test_cox_ph_schoenfeld_screen_handles_tied_event_times():
    rows = [
        {'pid': f'SYNTHETIC-TIE-{i}', 'duration': float(t), 'status': str(e),
         'origin': 'synthetic-origin'}
        for i, (t, e) in enumerate([(1, 1), (1, 1), (2, 1), (3, 1), (3, 1), (4, 0)])
    ]
    contract = EndpointContract('OS', 'pid', 'duration', 'status', 'origin', 'synthetic-origin',
                                'days', '1', '0', True)
    validation = validate_endpoint(rows, contract)
    features = np.array([[0.0], [1.0], [0.5], [2.0], [1.5], [-0.5]])
    fitted = cox_ph(validation, features, ['synthetic_tied_signal'], l2=0.1)
    assert fitted['converged'] is True
    assert fitted['proportional_hazards_screening']['features']['synthetic_tied_signal']


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


def _nifti_bytes(data, affine):
    return nib.Nifti1Image(data, affine).to_bytes()


def test_segmentation_evaluation_api_is_authorized_space_checked_and_idempotent(monkeypatch, tmp_path):
    import uuid
    from app.research.dataset import sha256

    root = tmp_path / 'uploads'
    root.mkdir()
    monkeypatch.setattr(settings, 'UPLOAD_DIR', str(root))
    case_id, run_id = 9807, uuid.uuid4().hex
    run_dir = root / f'case_{case_id}' / run_id
    run_dir.mkdir(parents=True)
    affine = np.diag([1.5, 1.0, 2.0, 1.0])
    image_data = np.zeros((5, 5, 5), np.float32)
    mask_data = np.zeros((5, 5, 5), np.uint8)
    mask_data[1:3, 1:3, 1:3] = 3
    paths = {}
    for sequence in ('t1c', 't1n', 't2w', 't2f'):
        path = run_dir / f'{sequence}.nii.gz'
        nib.save(nib.Nifti1Image(image_data, affine), path)
        paths[sequence] = str(path)
    mask_path = run_dir / 'prediction.nii.gz'
    nib.save(nib.Nifti1Image(mask_data, affine), mask_path)
    hashes = {key: sha256(Path(value)) for key, value in paths.items()}
    mask_hash = sha256(mask_path)
    db = SessionLocal()
    try:
        case = Case(id=case_id, description='synthetic evaluation fixture', status='analyzed')
        mri = MRI(id=case_id, case_id=case_id, status='analyzed', input_source='nifti-upload',
                  sequences_json=json.dumps(paths), analysis_run_id=run_id,
                  segmentation_path=str(mask_path), segmentation_source='model')
        run = AnalysisRun(id=run_id, case_id=case_id, mri_id=case_id, state='succeeded',
                          request_json=json.dumps({'sequences': paths, 'output_dir': str(run_dir)}),
                          result_json=json.dumps({'model': 'SYNTHETIC-TEST-MODEL', 'mask_path': str(mask_path),
                                                  'mask_sha256': mask_hash, 'input_sha256': hashes}))
        db.add_all([case, mri, run])
        db.commit()
    finally:
        db.close()

    app.dependency_overrides[require_doctor] = lambda: {
        'user': {'role': 'doctor'}, 'role': 'doctor',
        'authentication_method': 'synthetic-test-session', 'professional_credential_verified': False,
    }
    try:
        reference = mask_data.copy()
        reference[3, 1, 1] = 3
        payload = _nifti_bytes(reference, affine)
        fields = {'dataset_version': 'SYNTHETIC-SEG-EVAL-v1', 'annotation_id': 'SYNTHETIC-LABEL-1',
                  'authorization_receipt': 'synthetic-only-authorization', 'research_use_authorized': 'true'}
        with TestClient(app) as client:
            before = client.get(f'/research/cases/{case_id}/analysis/{run_id}/segmentation-evaluation')
            assert before.status_code == 200
            assert before.json()['data']['status'] == 'NOT_AVAILABLE'
            denied = client.post(f'/research/cases/{case_id}/analysis/{run_id}/segmentation-evaluation',
                                 data={**fields, 'research_use_authorized': 'false'},
                                 files={'reference_mask': ('reference.nii', payload, 'application/octet-stream')})
            assert denied.status_code == 403
            url = f'/research/cases/{case_id}/analysis/{run_id}/segmentation-evaluation'
            first = client.post(url, data=fields,
                                files={'reference_mask': ('reference.nii', payload, 'application/octet-stream')})
            assert first.status_code == 201, first.text
            result = first.json()['data']
            assert result['scope'] == 'synthetic_engineering'
            assert result['professional_credential_verified'] is False
            assert result['annotation_ref'] == hashlib.sha256(b'SYNTHETIC-LABEL-1').hexdigest()
            assert 'annotation_id' not in result and 'authorization_receipt' not in result
            assert result['units']['hd95'] == 'mm'
            assert result['regions']['ET']['dice'] < 1
            assert result['regions']['ET']['hd95_mm'] > 0
            second = client.post(url, data=fields,
                                 files={'reference_mask': ('reference.nii', payload, 'application/octet-stream')})
            assert second.status_code == 201
            assert second.json()['data']['evaluation_id'] == result['evaluation_id']
            state = client.get(url)
            assert state.json()['data']['reference_annotation_available'] is True
            assert state.json()['data']['record']['reference_mask_sha256'] == hashlib.sha256(payload).hexdigest()
            evaluation_dir = next((root / 'seg_eval').glob(f'{case_id}-*'))
            saved_record = next(evaluation_dir.glob('*.json')).read_text(encoding='utf-8')
            assert 'SYNTHETIC-LABEL-1' not in saved_record and 'synthetic-only-authorization' not in saved_record
            exported = client.get(url + '.csv')
            assert exported.status_code == 200 and 'hd95_mm' in exported.text
            assert len(list(evaluation_dir.glob('*.json'))) == 1
            shifted_affine = affine.copy(); shifted_affine[0, 3] = 9
            misaligned = _nifti_bytes(reference, shifted_affine)
            rejected = client.post(url, data={**fields, 'annotation_id': 'SYNTHETIC-MISALIGNED'},
                                   files={'reference_mask': ('reference.nii', misaligned, 'application/octet-stream')})
            assert rejected.status_code == 422 and 'affine' in rejected.text
            assert len(list(evaluation_dir.glob('*.json'))) == 1
    finally:
        app.dependency_overrides.pop(require_doctor, None)


def test_segmentation_evaluation_rejects_out_of_runtime_and_misaligned_reference(monkeypatch, tmp_path):
    import uuid
    from app.research.dataset import sha256

    root = tmp_path / 'uploads'
    root.mkdir()
    monkeypatch.setattr(settings, 'UPLOAD_DIR', str(root))
    case_id, run_id = 9808, uuid.uuid4().hex
    run_dir = root / f'case_{case_id}' / run_id
    run_dir.mkdir(parents=True)
    affine = np.eye(4)
    data = np.zeros((4, 4, 4), np.float32)
    mask = np.zeros_like(data, dtype=np.uint8)
    paths = {}
    for sequence in ('t1c', 't1n', 't2w', 't2f'):
        path = run_dir / f'{sequence}.nii.gz'
        nib.save(nib.Nifti1Image(data, affine), path)
        paths[sequence] = str(path)
    outside = tmp_path / 'outside.nii.gz'
    nib.save(nib.Nifti1Image(data, affine), outside)
    mask_path = run_dir / 'mask.nii.gz'
    nib.save(nib.Nifti1Image(mask, affine), mask_path)
    hashes = {key: sha256(Path(value)) for key, value in paths.items()}
    db = SessionLocal()
    try:
        db.add_all([
            Case(id=case_id, description='synthetic path fixture', status='analyzed'),
            MRI(id=case_id, case_id=case_id, status='analyzed', sequences_json=json.dumps(paths),
                analysis_run_id=run_id, segmentation_path=str(mask_path), segmentation_source='model'),
            AnalysisRun(id=run_id, case_id=case_id, mri_id=case_id, state='succeeded',
                        request_json=json.dumps({'sequences': {**paths, 't1c': str(outside)}, 'output_dir': str(run_dir)}),
                        result_json=json.dumps({'model': 'SYNTHETIC-TEST-MODEL', 'mask_path': str(mask_path),
                                                'mask_sha256': sha256(mask_path), 'input_sha256': hashes})),
        ])
        db.commit()
    finally:
        db.close()
    app.dependency_overrides[require_doctor] = lambda: {'user': {'role': 'doctor'}, 'role': 'doctor'}
    try:
        with TestClient(app) as client:
            response = client.get(f'/research/cases/{case_id}/analysis/{run_id}/segmentation-evaluation')
            assert response.status_code == 409
            assert 'upload runtime' in response.text
    finally:
        app.dependency_overrides.pop(require_doctor, None)


def test_segmentation_evaluation_requires_local_doctor_session():
    with TestClient(app) as client:
        response = client.get('/research/cases/1/analysis/missing/segmentation-evaluation')
        assert response.status_code == 401
