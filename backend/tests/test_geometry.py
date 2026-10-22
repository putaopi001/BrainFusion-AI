import io
import nibabel as nib
import numpy as np
import pytest
from PIL import Image
from app.services.mri_service import load_volume, extract_slice, render_mask_png
from app.services.segmentation_metrics import evaluate, region_volumes, validate_mask
from app.services.study_validation import validate_sequences
from app.services.mri_service import ensure_segmentation_mask, get_volume_metadata
from types import SimpleNamespace


def test_ras_and_lps_render_the_same_anatomical_voxels(tmp_path):
    data = np.arange(3 * 4 * 5, dtype=np.float32).reshape(3, 4, 5)
    original = nib.Nifti1Image(data, np.diag([-2, -3, 4, 1]))
    lps = tmp_path / 'lps.nii.gz'
    ras = tmp_path / 'ras.nii.gz'
    nib.save(original, lps)
    nib.save(nib.as_closest_canonical(original), ras)
    first, spacing, _ = load_volume(lps)
    second, _, _ = load_volume(ras)
    np.testing.assert_array_equal(first, second)
    assert spacing == [4, 3, 2]
    np.testing.assert_array_equal(extract_slice(first, 'axial', 2), data[:, :, 2].T)
    np.testing.assert_array_equal(extract_slice(first, 'coronal', 1), data[:, 1, :].T[::-1])
    np.testing.assert_array_equal(extract_slice(first, 'sagittal', 1), data[1, :, :].T[::-1])


def test_mask_affine_and_labels_are_validated(tmp_path):
    reference = nib.Nifti1Image(np.zeros((3, 4, 5), np.uint8), np.eye(4))
    with pytest.raises(ValueError, match='affine'):
        validate_mask(nib.Nifti1Image(np.zeros(reference.shape, np.uint8), np.diag([2, 1, 1, 1])), reference)
    with pytest.raises(ValueError, match='labels'):
        validate_mask(nib.Nifti1Image(np.full(reference.shape, 9, np.uint8), np.eye(4)), reference)


def test_metrics_physical_volume_and_empty_regions(tmp_path):
    data = np.zeros((3, 4, 5), np.uint8)
    data[1, 1, 1] = 3
    path = tmp_path / 'mask.nii.gz'
    nib.save(nib.Nifti1Image(data, np.diag([-2, -3, 4, 1])), path)
    assert region_volumes(path) == {'WT': .024, 'TC': .024, 'ET': .024}
    result = evaluate(path, path)
    assert all(r['dice'] == 1 and r['precision'] == 1 and r['recall'] == 1 and r['hd95_mm'] == 0
               for r in result['regions'].values())
    empty = tmp_path / 'empty.nii.gz'
    nib.save(nib.Nifti1Image(np.zeros_like(data), np.diag([-2, -3, 4, 1])), empty)
    both_empty = evaluate(empty, empty)['regions']['WT']
    assert both_empty['empty_rule'] == 'both_empty'
    assert both_empty['precision'] is None and both_empty['recall'] is None
    assert both_empty['hd95_status'] == 'not_available' and 'both regions' in both_empty['hd95_reason'].lower()
    false_positive = evaluate(path, empty)['regions']['WT']
    assert false_positive['hd95_mm'] is None and false_positive['precision'] == 0 and false_positive['recall'] is None
    assert false_positive['hd95_status'] == 'not_available' and 'One region' in false_positive['hd95_reason']
    false_negative = evaluate(empty, path)['regions']['WT']
    assert false_negative['precision'] is None and false_negative['recall'] == 0
    rgba = np.asarray(Image.open(io.BytesIO(render_mask_png(path, 'axial', 1))))
    assert rgba.shape == (4, 3, 4)
    assert rgba[1, 1, 3] > 0


def test_hd95_uses_full_affine_physical_distance(tmp_path):
    affine = np.eye(4)
    affine[:3, :3] = [[0, -2, 0], [3, 0, 0], [0, 0, 4]]
    predicted = np.zeros((5, 5, 5), np.uint8)
    reference = np.zeros_like(predicted)
    predicted[1, 1, 1] = reference[1, 1, 1] = 3
    reference[2, 1, 1] = 3
    first, second = tmp_path / 'pred.nii.gz', tmp_path / 'ref.nii.gz'
    nib.save(nib.Nifti1Image(predicted, affine), first)
    nib.save(nib.Nifti1Image(reference, affine), second)
    metrics = evaluate(first, second)['regions']['ET']
    assert metrics['hd95_mm'] == pytest.approx(2.7)
def test_study_geometry_is_rejected_before_activation(tmp_path):
    good = tmp_path / 'good.nii.gz'
    bad = tmp_path / 'bad.nii.gz'
    nib.save(nib.Nifti1Image(np.zeros((3, 4, 5), np.uint8), np.eye(4)), good)
    paths = {seq: good for seq in ('t1c', 't1n', 't2w', 't2f')}
    assert validate_sequences(paths).shape == (3, 4, 5)
    nib.save(nib.Nifti1Image(np.zeros((3, 4, 5), np.uint8), np.diag([2, 1, 1, 1])), bad)
    with pytest.raises(ValueError, match='affine'):
        validate_sequences({**paths, 't2w': bad})
    with pytest.raises(ValueError, match='1 mm'):
        validate_sequences({key: bad for key in paths})
    oblique = np.eye(4)
    angle = .3
    oblique[:2, :2] = [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]]
    nib.save(nib.Nifti1Image(np.zeros((3, 4, 5), np.uint8), oblique), bad)
    with pytest.raises(ValueError, match='Oblique'):
        validate_sequences({key: bad for key in paths})


def test_file_change_invalidates_mask_and_metadata_caches(tmp_path):
    import os
    source, mask = tmp_path / 'source.nii.gz', tmp_path / 'mask.nii.gz'
    nib.save(nib.Nifti1Image(np.zeros((3, 4, 5), np.uint8), np.eye(4)), source)
    nib.save(nib.Nifti1Image(np.zeros((3, 4, 5), np.uint8), np.eye(4)), mask)
    mri = SimpleNamespace(segmentation_path=str(mask))
    assert ensure_segmentation_mask(mri, source) == mask
    assert get_volume_metadata(source)['max'] == 0
    first_source_time, first_mask_time = source.stat().st_mtime_ns, mask.stat().st_mtime_ns
    nib.save(nib.Nifti1Image(np.full((3, 4, 5), 9, np.uint8), np.eye(4)), mask)
    os.utime(mask, ns=(first_mask_time + 1_000_000_000,) * 2)
    with pytest.raises(ValueError, match='labels'):
        ensure_segmentation_mask(mri, source)
    nib.save(nib.Nifti1Image(np.full((3, 4, 5), 7, np.uint8), np.eye(4)), source)
    os.utime(source, ns=(first_source_time + 1_000_000_000,) * 2)
    assert get_volume_metadata(source)['max'] == 7
