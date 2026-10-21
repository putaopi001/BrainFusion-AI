"""Real SQLite persistence and independent nonunit/flip geometry, isolated DB."""
import copy
import numpy as np
import nibabel as nib
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.mri import MRI
from app.models.annotation import MRIAnnotation

client = TestClient(app)


@pytest.fixture
def measurement_case(tmp_path):
    case_id = client.post('/cases/create', json={'patient_name': 'SYNTHETIC world measurement', 'age': 40, 'gender': 'female', 'description': 'Isolated geometry fixture'}).json()['data']['case_id']
    path = tmp_path / 'reference.nii.gz'
    image = nib.Nifti1Image(np.zeros((6, 6, 6), np.float32), np.diag([-2., -3., 4., 1.]))
    image.header.set_xyzt_units('mm')
    nib.save(image, path)
    with SessionLocal() as db:
        mri = MRI(case_id=case_id, filepath=str(path), segmentation_source='unavailable')
        db.add(mri); db.commit(); mri_id = mri.id
        canvas = MRIAnnotation(mri_id=mri_id, case_id=case_id, view='axial', slice_index=2, tool='line', x=.2, y=.3, width=.1, height=.1)
        db.add(canvas); db.commit(); canvas_id = canvas.id
    data = client.get(f'/mri/{case_id}/measurements').json()['data']
    payload = {'context': data['context'], 'client_uid': 'geometry-fixture', 'reference_sequence': None,
               'view': 'axial', 'points_lps': [[2., 3., 8.], [8., 11., 8.]],
               'view_plane_normal': [0., 0., -1.], 'view_up': [0., -1., 0.]}
    return case_id, mri_id, path, canvas_id, payload


def test_world_mm_save_duplicate_reopen_and_independent_canvas_delete(measurement_case):
    case_id, mri_id, _, canvas_id, payload = measurement_case
    first = client.post(f'/mri/{case_id}/measurements', json=payload)
    assert first.status_code == 200, first.text
    item = first.json()['data']
    assert item['length_mm'] == pytest.approx(10.)
    assert item['points_lps'] == payload['points_lps'] and item['coordinate_contract'] == 'LPS_MM_V1'
    again = client.post(f'/mri/{case_id}/measurements', json=payload)
    assert again.json()['data']['id'] == item['id']
    with TestClient(app) as reopened:
        items = reopened.get(f'/mri/{case_id}/measurements').json()['data']['items']
        assert len(items) == 1 and items[0]['current']
        assert items[0]['length_mm'] == pytest.approx(10.)
    # Canvas bulk deletion cannot erase the new world-coordinate record.
    assert client.delete(f'/mri/{case_id}/annotations').status_code == 200
    assert len(client.get(f'/mri/{case_id}/measurements').json()['data']['items']) == 1
    assert client.delete(f'/mri/{case_id}/measurements/{item["id"]}?mri_id={mri_id}').status_code == 200
    assert client.get(f'/mri/{case_id}/measurements').json()['data']['items'] == []


@pytest.mark.parametrize('change', ['wrong_context', 'outside', 'plane', 'zero', 'directions', 'sequence', 'extra'])
def test_invalid_measurement_rejected_without_record(measurement_case, change):
    case_id, _, _, _, original = measurement_case
    payload = copy.deepcopy(original)
    if change == 'wrong_context': payload['context']['study_revision'] = '0' * 64
    if change == 'outside': payload['points_lps'][1][0] = 999
    if change == 'plane': payload['points_lps'][1][2] += 2
    if change == 'zero': payload['points_lps'][1] = payload['points_lps'][0]
    if change == 'directions': payload['view_plane_normal'] = [0, 0, 0]
    if change == 'sequence': payload['reference_sequence'] = 't1c'
    if change == 'extra': payload['length_mm'] = .78
    response = client.post(f'/mri/{case_id}/measurements', json=payload)
    assert response.status_code == (409 if change == 'wrong_context' else 422), response.text
    assert client.get(f'/mri/{case_id}/measurements').json()['data']['items'] == []


def test_changed_study_and_analysis_preserve_history_and_reject_old_save(measurement_case):
    case_id, mri_id, path, _, payload = measurement_case
    assert client.post(f'/mri/{case_id}/measurements', json=payload).status_code == 200
    changed = copy.deepcopy(payload); changed['points_lps'][1][0] -= 1
    assert client.post(f'/mri/{case_id}/measurements', json=changed).status_code == 409
    image = nib.load(path); data = image.get_fdata(); data[0, 0, 0] = 10
    nib.save(nib.Nifti1Image(data, image.affine, image.header), path)
    current = client.get(f'/mri/{case_id}/measurements').json()['data']
    assert not current['items'][0]['current']
    assert client.post(f'/mri/{case_id}/measurements', json=payload).status_code == 409
    with SessionLocal() as db:
        db.get(MRI, mri_id).analysis_run_id = 'changed-analysis'; db.commit()
    after = client.get(f'/mri/{case_id}/measurements').json()['data']
    assert after['context']['analysis_run_id'] == 'changed-analysis'
    assert not after['items'][0]['current'] and after['items'][0]['context']['analysis_run_id'] is None


def test_world_delete_does_not_delete_canvas_and_other_case_rejected(measurement_case):
    case_id, mri_id, path, canvas_id, payload = measurement_case
    item = client.post(f'/mri/{case_id}/measurements', json=payload).json()['data']
    other_case = client.post('/cases/create', json={'patient_name': 'SYNTHETIC other case', 'age': 40, 'gender': 'female', 'description': 'Isolation fixture'}).json()['data']['case_id']
    with SessionLocal() as db:
        other = MRI(case_id=other_case, filepath=str(path), segmentation_source='unavailable')
        db.add(other); db.commit(); other_mri = other.id
    assert client.delete(f'/mri/{other_case}/measurements/{item["id"]}?mri_id={other_mri}').status_code == 404
    assert client.post(f'/mri/{other_case}/measurements', json=payload).status_code == 409
    assert client.delete(f'/mri/{case_id}/measurements/{item["id"]}?mri_id={mri_id + 1}').status_code == 409
    assert client.delete(f'/mri/{case_id}/measurements/{item["id"]}?mri_id={mri_id}').status_code == 200
    assert any(a['id'] == canvas_id for a in client.get(f'/mri/{case_id}/annotations').json()['data'])


def view_payload(context):
    cameras = {}
    for view, normal, up in [('axial', [0., 0., -1.], [0., -1., 0.]), ('sagittal', [1., 0., 0.], [0., 0., 1.]), ('coronal', [0., -1., 0.], [0., 0., 1.])]:
        cameras[view] = {'focal_point': [6., 6., 8.], 'position': [6 + n * 100 for n in normal],
                         'view_plane_normal': normal, 'view_up': up, 'parallel_scale': 12.}
        cameras[view]['position'] = [v + n * 100 for v, n in zip(cameras[view]['focal_point'], normal)]
    return {'context': context, 'client_uid': 'view-fixture', 'sequence': None, 'segmentation_visible': False,
            'cameras': cameras, 'window_ranges': {'legacy': [{'lower': 0., 'upper': 100.}] * 3}}


def test_explicit_view_versions_deduplicate_and_preserve_history(measurement_case):
    from app.models.world_measurement import MRIViewState
    case_id, mri_id, _, _, original = measurement_case
    payload = view_payload(original['context'])
    response = client.post(f'/mri/{case_id}/view-state', json=payload)
    assert response.status_code == 200, response.text
    first = response.json()['data']
    assert client.post(f'/mri/{case_id}/view-state', json=payload).json()['data']['id'] == first['id']
    changed = copy.deepcopy(payload); changed['cameras']['axial']['parallel_scale'] = 15.
    assert client.post(f'/mri/{case_id}/view-state', json=changed).status_code == 409
    changed['client_uid'] = 'view-fixture-new'
    second = client.post(f'/mri/{case_id}/view-state', json=changed).json()['data']
    assert second['id'] != first['id']
    assert client.get(f'/mri/{case_id}/view-state').json()['data']['saved'] == second
    with SessionLocal() as db:
        assert db.query(MRIViewState).filter_by(mri_id=mri_id).count() == 2
        db.get(MRI, mri_id).analysis_run_id = 'new-analysis'; db.commit()
    historical = client.get(f'/mri/{case_id}/view-state').json()['data']['saved']
    assert not historical['current'] and historical['state'] == second['state']
    assert client.post(f'/mri/{case_id}/view-state', json=changed).status_code == 409


@pytest.mark.parametrize('change', ['camera_missing', 'normal', 'window', 'scale', 'sequence'])
def test_invalid_view_state_rejected_without_saved_version(measurement_case, change):
    case_id, _, _, _, original = measurement_case
    payload = view_payload(original['context'])
    if change == 'camera_missing': del payload['cameras']['coronal']
    if change == 'normal': payload['cameras']['axial']['view_up'] = [0, 0, 1]
    if change == 'window': payload['window_ranges']['legacy'][0]['upper'] = 0
    if change == 'scale': payload['cameras']['axial']['parallel_scale'] = 0
    if change == 'sequence': payload['sequence'] = 't1c'
    response = client.post(f'/mri/{case_id}/view-state', json=payload)
    assert response.status_code == 422, response.text
    assert client.get(f'/mri/{case_id}/view-state').json()['data']['saved'] is None
