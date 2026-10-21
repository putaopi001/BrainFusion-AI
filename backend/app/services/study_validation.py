import nibabel as nib
import numpy as np

MAX_VOXELS = 32_000_000
MODEL_INPUT_CONTRACT_ID = 'monai-brats-four-sequence-1mm-axis-aligned-v1'


def validate_model_geometry(shape, affine, spacing):
    """The existing model's header contract; never reads pixels or resamples."""
    if len(shape) != 3 or any(size < 2 for size in shape) or np.prod(shape, dtype=np.int64) > MAX_VOXELS:
        raise ValueError('MRI must be 3D with at most 32 million voxels per sequence')
    if not np.allclose(spacing[:3], 1, atol=1e-3):
        raise ValueError('This model requires 1 mm MRI spacing')
    orientation = nib.orientations.ornt_transform(nib.orientations.io_orientation(affine), nib.orientations.axcodes2ornt(('L', 'P', 'S')))
    # Same affine as image.as_reoriented(), without materializing its dataobj.
    matrix = (affine @ nib.orientations.inv_ornt_aff(orientation, shape))[:3, :3]
    lengths = np.linalg.norm(matrix, axis=0)
    if not np.isfinite(matrix).all() or (lengths <= 0).any() or not np.allclose(np.abs(matrix / lengths), np.eye(3), atol=1e-3):
        raise ValueError('Oblique MRI needs resampling before this model')


def validate_sequences(paths):
    if set(paths) != {'t1c', 't1n', 't2w', 't2f'}:
        raise ValueError('Four aligned MRI sequences are required')
    reference = nib.load(str(paths['t1c']))
    for key, path in paths.items():
        image = nib.load(str(path))
        if len(image.shape) != 3 or any(size < 2 for size in image.shape) or np.prod(image.shape, dtype=np.int64) > MAX_VOXELS:
            raise ValueError('MRI must be 3D with at most 32 million voxels per sequence')
        if image.shape != reference.shape or not np.allclose(image.affine, reference.affine, atol=1e-4, rtol=0):
            raise ValueError('Four sequences must share shape and affine')
        if not np.allclose(image.header.get_zooms()[:3], 1, atol=1e-3):
            raise ValueError('This model requires 1 mm MRI spacing')
        validate_model_geometry(image.shape, image.affine, image.header.get_zooms())
    return reference
