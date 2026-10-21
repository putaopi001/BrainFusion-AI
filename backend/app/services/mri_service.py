import io
import json
from functools import lru_cache
from pathlib import Path

import nibabel as nib
import numpy as np
import SimpleITK as sitk
from PIL import Image

from app.models.mri import MRI
from app.core.storage import resolve_stored_path


# Display volume axes: [S, P, L], normalized from the NIfTI affine.
# Axial rows increase P; coronal/sagittal rows are flipped to put S on top.
VIEW_AXIS = {"axial": 0, "coronal": 1, "sagittal": 2}


def resolve_filepath(mri: MRI) -> Path | None:
    """Resolve an MRI record's filepath to an absolute path on disk."""
    if not mri or not mri.filepath:
        return None
    path = resolve_stored_path(mri.filepath)
    return path if path.is_file() else None


def resolve_view_sequence(mri, sequence=None):
    """Use the uploaded common grid only. No registration/resampling is implicit."""
    if not mri.sequences_json:
        if sequence is not None:
            raise ValueError('This legacy MRI has no identified four-sequence study')
        return resolve_filepath(mri), None, []
    from app.services.study_validation import validate_sequences
    paths = json.loads(mri.sequences_json)
    if not isinstance(paths, dict) or set(paths) != {'t1c', 't1n', 't2w', 't2f'}:
        raise ValueError('Exactly four identified MRI sequences are required for switching')
    resolved = {}
    for key, value in paths.items():
        path = resolve_stored_path(value)
        resolved[key] = path
    # Header checks also reject externally changed geometry, rather than misalign masks/annotations.
    validate_sequences(resolved)
    selected = sequence or 't2f'
    if selected not in resolved:
        raise ValueError('Unknown MRI sequence')
    return resolved[selected], selected, ['t1c', 't1n', 't2w', 't2f']


def load_volume(filepath: Path) -> tuple[np.ndarray, list[float], str]:
    path = Path(filepath).resolve()
    return _load_display(str(path), path.stat().st_mtime_ns, path.stat().st_size)


@lru_cache(maxsize=2)
def _load_display(path, modified, size):
    if not path.lower().endswith((".nii", ".nii.gz")):
        raise ValueError("Only 3D NIfTI volumes are supported by this viewer")
    image = nib.load(path)
    if len(image.shape) != 3:
        raise ValueError("MRI volume must be 3-dimensional")
    target = nib.orientations.axcodes2ornt(("L", "P", "S"))
    transform = nib.orientations.ornt_transform(nib.orientations.io_orientation(image.affine), target)
    lps_image = image.as_reoriented(transform)
    matrix = lps_image.affine[:3, :3]
    directions = matrix / np.linalg.norm(matrix, axis=0)
    if not np.allclose(np.abs(directions), np.eye(3), atol=1e-3):
        raise ValueError("Oblique MRI requires resampling before orthogonal viewing")
    data = lps_image.get_fdata(dtype=np.float32).transpose(2, 1, 0).copy()
    if not np.isfinite(data).all():
        raise ValueError("MRI contains nonfinite values")
    data.setflags(write=False)
    spacing = list(map(float, lps_image.header.get_zooms()[:3][::-1]))
    return data, spacing, str(data.dtype)


def get_volume_metadata(filepath: Path) -> dict:
    path = Path(filepath).resolve()
    stat = path.stat()
    return _metadata_cached(str(path), stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=16)
def _metadata_cached(filepath, modified, size):
    """Return {shape, spacing, min, max, mean, std, dtype, display_min, display_max}."""
    data, spacing, dtype = load_volume(filepath)
    flat = data.ravel()
    return {
        "shape": list(data.shape),
        "spacing": spacing,
        "dtype": dtype,
        "coordinate_contract": "LPS_DISPLAY_V1",
        "display_axes": ["S", "P", "L"],
        "min": float(flat.min()),
        "max": float(flat.max()),
        "mean": float(flat.mean()),
        "std": float(flat.std()),
        "display_min": float(np.percentile(flat, 2)),
        "display_max": float(np.percentile(flat, 98)),
    }


def extract_slice(data: np.ndarray, view: str, index: int) -> np.ndarray:
    axis = VIEW_AXIS[view]
    if axis == 0:
        return data[index, :, :]
    if axis == 1:
        return data[::-1, index, :]
    return data[::-1, :, index]


def apply_window_level(slice_data: np.ndarray, ww: float, wl: float) -> np.ndarray:
    """Map raw voxel intensity to 0..255 grayscale via window width / window level."""
    low = wl - ww / 2.0
    high = wl + ww / 2.0
    if high <= low:
        high = low + 1.0
    mapped = np.clip((slice_data - low) / (high - low), 0.0, 1.0)
    return (mapped * 255.0).astype(np.uint8)


def render_slice_png(filepath: Path, view: str, index: int, ww: float, wl: float) -> bytes:
    """Render a single MRI slice to PNG bytes after applying a real window/level LUT."""
    data, _, _ = load_volume(filepath)
    axis = VIEW_AXIS[view]
    size = data.shape[axis]
    index = max(0, min(int(index), size - 1))
    gray = apply_window_level(extract_slice(data, view, index), ww, wl)
    buffer = io.BytesIO()
    Image.fromarray(gray).save(buffer, format="PNG")
    return buffer.getvalue()


def ensure_segmentation_mask(mri: MRI, source: Path) -> Path:
    """Only expose an explicit uploaded/reference/model mask, never fabricate one."""
    path = getattr(mri, "segmentation_path", None)
    if not path:
        raise FileNotFoundError("No segmentation available; run a real model or upload a mask")
    mask_path = Path(path)
    mask_stat, source_stat = mask_path.stat(), Path(source).stat()
    _validate_mask_cached(str(mask_path.resolve()), mask_stat.st_mtime_ns, mask_stat.st_size,
                          str(Path(source).resolve()), source_stat.st_mtime_ns, source_stat.st_size)
    return mask_path


@lru_cache(maxsize=8)
def _validate_mask_cached(mask, mask_modified, mask_size, source, source_modified, source_size):
    from app.services.segmentation_metrics import validate_mask
    validate_mask(nib.load(mask), nib.load(source))


def render_mask_png(mask_path: Path, view: str, index: int) -> bytes:
    """Render a semi-transparent red overlay PNG for the segmentation mask slice."""
    mask = load_volume(mask_path)[0]
    axis = VIEW_AXIS[view]
    size = mask.shape[axis]
    index = max(0, min(int(index), size - 1))
    slice_mask = extract_slice(mask, view, index)

    height, width = slice_mask.shape
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    for label, color in {1: (59, 130, 246, 160), 2: (245, 158, 11, 140),
                         3: (239, 68, 68, 180), 4: (168, 85, 247, 140)}.items():
        rgba[slice_mask == label] = color

    buffer = io.BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(buffer, format="PNG")
    return buffer.getvalue()


def voxel_coord_for_point(view: str, index: int, nx: float, ny: float, shape: tuple) -> dict:
    """由视图 + 切片索引 + 归一化坐标计算体素坐标 {x,y,z}。"""
    axis = VIEW_AXIS[view]
    row_axis = 1 if axis == 0 else 0
    col_axis = 2 if axis != 2 else 1
    coord = [0, 0, 0]
    coord[axis] = index
    coord[col_axis] = int(round(nx * (shape[col_axis] - 1)))
    coord[row_axis] = int(round(ny * (shape[row_axis] - 1)))
    if view != "axial":
        coord[row_axis] = shape[row_axis] - 1 - coord[row_axis]
    return {"x": coord[0], "y": coord[1], "z": coord[2]}


def get_voxel_value(filepath: Path, view: str, index: int, nx: float, ny: float) -> dict:
    """读取某视图某切片上归一化 (nx, ny) 处的体素强度值（探针工具）。"""
    data, _, _ = load_volume(filepath)
    axis = VIEW_AXIS[view]
    index = max(0, min(int(index), data.shape[axis] - 1))
    slice_2d = extract_slice(data, view, index)
    rows, cols = slice_2d.shape
    col = max(0, min(int(round(nx * (cols - 1))), cols - 1))
    row = max(0, min(int(round(ny * (rows - 1))), rows - 1))
    value = float(slice_2d[row, col])
    voxel = voxel_coord_for_point(view, index, nx, ny, data.shape)
    return {"value": value, "voxel": voxel, "coordinate_contract": "LPS_DISPLAY_V1", "unit": "MRI intensity"}


def compute_display_status(mri: MRI) -> str:
    """Derive a human-friendly reading status from stored fields (not the raw DB status)."""
    if mri.status == "analyzed":
        return "analyzed"
    if mri.status == "processing":
        return "processing"
    if mri.status == "failed" or (mri.preview_error and not mri.slice_path):
        return "failed"
    if mri.slice_path:
        return "preview_ready"
    return "uploaded"
