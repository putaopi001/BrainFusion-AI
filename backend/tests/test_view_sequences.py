"""Verify sequence identity, common physical grid and true intensity selection."""
import io
import json

import nibabel as nib
import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.mri import MRI

client = TestClient(app)
KEYS = ['t1c', 't1n', 't2w', 't2f']


@pytest.fixture
def sequences(tmp_path):
    created = client.post('/cases/create', json={'patient_name': 'SYNTHETIC sequence geometry',
                            'age': 50, 'gender': 'female', 'description': 'Isolated four-sequence geometry fixture'})
    assert created.status_code == 200 and created.json()['data'], created.text
    case_id = created.json()['data']['case_id']
    affine = np.diag([-1., -1., 1., 1.]); affine[:3, 3] = [10, 20, 30]
    base = np.arange(60, dtype=np.float32).reshape(3, 4, 5)
    paths = {}
    for i, key in enumerate(KEYS):
        path = tmp_path / (key + '.nii.gz')
        nib.save(nib.Nifti1Image(base + i * 100, affine), path)
        paths[key] = str(path)
    mask = tmp_path / 'mask.nii.gz'
    labels = np.zeros(base.shape, np.uint8); labels[1, 2, 3] = 3
    nib.save(nib.Nifti1Image(labels, affine), mask)
    with SessionLocal() as db:
        mri = MRI(case_id=case_id, filepath=paths['t2f'], sequences_json=json.dumps(paths),
                  segmentation_path=str(mask), segmentation_source='uploaded')
        db.add(mri); db.commit(); mri_id = mri.id
    return case_id, mri_id, paths, affine


@pytest.mark.parametrize('view,index', [('axial', 3), ('coronal', 2), ('sagittal', 1)])
def test_same_position_mask_and_distinct_selected_intensities(sequences, view, index):
    case_id, _, _, _ = sequences
    metas, voxels, pngs = [], [], []
    for key in KEYS:
        r = client.get(f'/mri/{case_id}/volume', params={'sequence': key})
        assert r.status_code == 200, r.text
        meta = r.json()['data']; assert meta['sequence'] == key
        assert meta['available_sequences'] == KEYS
        assert meta['coordinate_contract'] == 'LPS_DISPLAY_V1'
        metas.append(meta)
        voxel = client.get(f'/mri/{case_id}/voxel', params={'sequence': key, 'view': view, 'index': index, 'nx': .5, 'ny': .5}).json()['data']
        assert voxel['sequence'] == key
        voxels.append(voxel)
        png = client.get(f'/mri/{case_id}/slice/{view}/{index}', params={'sequence': key, 'ww': 500, 'wl': 250})
        assert png.status_code == 200
        pngs.append(np.asarray(Image.open(io.BytesIO(png.content))))
    assert all(m['shape'] == [5, 4, 3] and m['spacing'] == [1., 1., 1.] for m in metas)
    assert all(v['voxel'] == voxels[0]['voxel'] for v in voxels)
    assert [v['value'] - voxels[0]['value'] for v in voxels] == [0, 100, 200, 300]
    assert all(not np.array_equal(pngs[0], p) for p in pngs[1:])
    default = client.get(f'/mri/{case_id}/volume').json()['data']
    assert default['sequence'] == 't2f'
    overlay = client.get(f'/mri/{case_id}/mask/{view}/{index}')
    assert overlay.status_code == 200
    assert np.asarray(Image.open(io.BytesIO(overlay.content))).shape[:2] == pngs[0].shape


def test_missing_or_changed_geometry_rejected_without_resampling(sequences):
    case_id, _, paths, affine = sequences
    assert client.get(f'/mri/{case_id}/volume', params={'sequence': 'unknown'}).status_code == 422
    changed = affine.copy(); changed[0, 3] += 1
    nib.save(nib.Nifti1Image(np.ones((3, 4, 5), np.float32), changed), paths['t1n'])
    for endpoint in ['volume', 'slice/axial/2', 'voxel']:
        params = {'sequence': 't1n'}
        if endpoint == 'voxel': params.update(view='axial', index=2, nx=.5, ny=.5)
        r = client.get(f'/mri/{case_id}/{endpoint}', params=params)
        assert r.status_code == 422 and 'affine' in r.json()['detail']
    assert np.array_equal(nib.load(paths['t1n']).affine, changed)


def test_legacy_single_volume_is_not_mislabeled_as_flair(sequences):
    case_id, mri_id, _, _ = sequences
    with SessionLocal() as db:
        db.get(MRI, mri_id).sequences_json = None; db.commit()
    result = client.get(f'/mri/{case_id}/volume').json()['data']
    assert result['sequence'] is None and result['available_sequences'] == []
    assert client.get(f'/mri/{case_id}/volume', params={'sequence': 't2f'}).status_code == 422


def test_cornerstone_original_bytes_and_version_guard(sequences):
    from pathlib import Path
    case_id, mri_id, paths, affine = sequences
    for key in KEYS:
        metadata = client.get(f'/mri/{case_id}/volume', params={'sequence': key}).json()['data']
        response = client.get(metadata['nifti_url'])
        assert response.status_code == 200
        assert response.content == Path(paths[key]).read_bytes()
        assert response.headers['cache-control'] == 'no-store'
    assert client.get(f'/mri/{case_id}/nifti?mri_id={mri_id + 1}&revision=old').status_code == 409
    assert client.get(f'/mri/{case_id}/nifti?mri_id={mri_id}&revision=old').status_code == 409
    changed = affine.copy(); changed[0, 3] += 1
    nib.save(nib.Nifti1Image(np.ones((3, 4, 5), np.float32), changed), paths['t1n'])
    assert client.get(f'/mri/{case_id}/nifti?mri_id={mri_id}&sequence=t1n&revision=old').status_code == 422
