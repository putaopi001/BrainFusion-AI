"""Explicit same-FrameOfReference grid resampling for the existing 1 mm model input.

This performs interpolation only. It never estimates or applies registration.
The source DICOM bytes and source geometries remain separate, immutable evidence.
"""
import itertools

import numpy as np

from app.services.study_validation import MAX_VOXELS, validate_model_geometry


class ResamplingError(ValueError):
    pass


def _matrix(geometry):
    orientation = np.asarray(geometry['image_orientation_patient'], dtype=float)
    spacing = np.asarray(geometry['spacing_xyz_mm'], dtype=float)
    origin = np.asarray(geometry['origin_lps_mm'], dtype=float)
    direction = np.column_stack((orientation[:3], orientation[3:],
                                 np.asarray(geometry['unit_normal_for_sorting'], dtype=float)))
    if (orientation.shape != (6,) or spacing.shape != (3,) or origin.shape != (3,)
            or direction.shape != (3, 3) or not np.isfinite(direction).all()
            or not np.isfinite(spacing).all() or (spacing <= 0).any()
            or not np.isfinite(origin).all() or abs(float(np.linalg.det(direction))) < 0.999):
        raise ResamplingError('源序列空间矩阵无效，无法定义患者坐标插值。')
    return origin, direction, spacing


def build_target_grid(reference_geometry, spacing_xyz_mm=(1.0, 1.0, 1.0)):
    """Cover the reference voxel-center extent using the declared output spacing."""
    origin, direction, source_spacing = _matrix(reference_geometry)
    dimensions = np.asarray(reference_geometry['dimensions'], dtype=np.int64)
    target_spacing = np.asarray(spacing_xyz_mm, dtype=float)
    if (dimensions.shape != (3,) or (dimensions < 2).any()
            or target_spacing.shape != (3,) or not np.isfinite(target_spacing).all()
            or (target_spacing <= 0).any()):
        raise ResamplingError('参考序列或目标spacing无效。')
    extent = (dimensions - 1) * source_spacing
    target_dimensions = np.floor(extent / target_spacing + 1e-8).astype(np.int64) + 1
    if ((target_dimensions < 2).any()
            or int(np.prod(target_dimensions, dtype=np.int64)) > MAX_VOXELS):
        raise ResamplingError('重采样输出超出模型三维体素预算。')
    affine_lps = np.eye(4)
    affine_lps[:3, :3] = direction @ np.diag(target_spacing)
    affine_lps[:3, 3] = origin
    affine_ras = np.diag([-1.0, -1.0, 1.0, 1.0]) @ affine_lps
    try:
        validate_model_geometry(target_dimensions.tolist(), affine_ras, target_spacing)
    except ValueError as exc:
        raise ResamplingError('重采样参考方向不满足当前模型轴向空间契约。') from exc
    return {
        'format': 'dicom-model-resampling-grid-v1',
        'dimensions': target_dimensions.tolist(),
        'spacing_xyz_mm': target_spacing.tolist(),
        'origin_lps_mm': origin.tolist(),
        'direction_lps': direction.reshape(-1).tolist(),
        'affine_ras_mm': affine_ras.tolist(),
        'reference_source_dimensions': dimensions.tolist(),
        'reference_source_spacing_xyz_mm': source_spacing.tolist(),
        'coverage_policy': 'reference_voxel_centers_no_extrapolated_endpoint',
    }


def ensure_grid_covered(source_geometry, target_grid, tolerance_mm=1e-3):
    """Require every output corner center to lie inside the source volume.

    Same FrameOfReferenceUID is checked by the caller. This corner test uses the
    full 3-D direction matrices, so it does not assume axial orientation.
    """
    source_origin, source_direction, source_spacing = _matrix(source_geometry)
    target_origin = np.asarray(target_grid['origin_lps_mm'], dtype=float)
    target_direction = np.asarray(target_grid['direction_lps'], dtype=float).reshape(3, 3)
    target_spacing = np.asarray(target_grid['spacing_xyz_mm'], dtype=float)
    target_dimensions = np.asarray(target_grid['dimensions'], dtype=np.int64)
    source_dimensions = np.asarray(source_geometry['dimensions'], dtype=np.int64)
    source_step = source_direction @ np.diag(source_spacing)
    target_step = target_direction @ np.diag(target_spacing)
    try:
        inverse = np.linalg.inv(source_step)
    except np.linalg.LinAlgError as exc:
        raise ResamplingError('源序列空间矩阵不可逆。') from exc
    for corner in itertools.product(*[(0, int(n) - 1) for n in target_dimensions]):
        world = target_origin + target_step @ np.asarray(corner, dtype=float)
        source_index = inverse @ (world - source_origin)
        if np.any(source_index < -tolerance_mm / source_spacing) or np.any(
                source_index > source_dimensions - 1 + tolerance_mm / source_spacing):
            raise ResamplingError('目标重采样网格超出至少一个输入序列覆盖范围。')
    return True


def target_image(target_grid, sitk):
    image = sitk.Image(target_grid['dimensions'], sitk.sitkFloat32)
    image.SetOrigin(target_grid['origin_lps_mm'])
    image.SetSpacing(target_grid['spacing_xyz_mm'])
    image.SetDirection(target_grid['direction_lps'])
    return image


def resample_image(image, target_grid, sitk, outside_value=0.0):
    reference = target_image(target_grid, sitk)
    transform = sitk.Transform(3, sitk.sitkIdentity)
    return sitk.Resample(image, reference, transform, sitk.sitkLinear,
                         float(outside_value), sitk.sitkFloat32)


def resample_array(array_zyx, source_geometry, target_grid, outside_value=0.0):
    """Independent metadata-driven verifier path from source decoded pixels."""
    import SimpleITK as sitk

    source = sitk.GetImageFromArray(np.asarray(array_zyx, dtype=np.float32))
    origin, direction, spacing = _matrix(source_geometry)
    source.SetOrigin(origin.tolist())
    source.SetDirection(direction.reshape(-1).tolist())
    source.SetSpacing(spacing.tolist())
    output = resample_image(source, target_grid, sitk, outside_value)
    return sitk.GetArrayFromImage(output)
