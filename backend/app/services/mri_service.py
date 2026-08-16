import io
from pathlib import Path

import nibabel as nib
import numpy as np
import SimpleITK as sitk
from PIL import Image

from app.models.mri import MRI


# 视图 -> 体数据轴向。与 mri_preview_service.generate_mri_previews 保持完全一致：
#   axial   = axis 0
#   coronal = axis 1
#   sagittal= axis 2
VIEW_AXIS = {"axial": 0, "coronal": 1, "sagittal": 2}


def resolve_filepath(mri: MRI) -> Path | None:
    """Resolve an MRI record's filepath to an absolute path on disk."""
    if not mri or not mri.filepath:
        return None
    path = Path(mri.filepath)
    if not path.is_absolute():
        backend_dir = Path(__file__).resolve().parents[2]
        path = backend_dir / path
    return path if path.is_file() else None


def load_volume(filepath: Path) -> tuple[np.ndarray, list[float], str]:
    """Load a 3D MRI volume to a float32 numpy array (nii/nii.gz via nibabel, dcm via SimpleITK)."""
    name = filepath.name.lower()
    if name.endswith((".nii", ".nii.gz")):
        image = nib.load(str(filepath))
        data = np.squeeze(np.asanyarray(image.dataobj)).astype(np.float32)
        spacing = [float(value) for value in image.header.get_zooms()[:3]]
    else:
        sitk_image = sitk.ReadImage(str(filepath))
        data = np.squeeze(sitk.GetArrayFromImage(sitk_image)).astype(np.float32)
        spacing = [float(value) for value in sitk_image.GetSpacing()]
    if data.ndim != 3:
        raise ValueError("MRI volume must be 3-dimensional")
    return data, spacing, str(data.dtype)


def get_volume_metadata(filepath: Path) -> dict:
    """Return {shape, spacing, min, max, mean, std, dtype, display_min, display_max}."""
    data, spacing, dtype = load_volume(filepath)
    flat = data.ravel()
    return {
        "shape": list(data.shape),
        "spacing": spacing,
        "dtype": dtype,
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
        return data[:, index, :]
    return data[:, :, index]


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


def _mock_tumor_mask(data: np.ndarray) -> np.ndarray:
    """Deterministic mock tumor mask (ellipsoid around the brightest region).

    This is a teaching/demo placeholder only — no real segmentation model is run.
    """
    shape = np.array(data.shape, dtype=np.float32)
    mean = float(data.mean())
    std = float(data.std()) + 1e-6
    bright = data > (mean + 1.4 * std)
    if bright.any():
        center = np.argwhere(bright).mean(axis=0)
    else:
        center = shape / 2.0

    radii = np.maximum(shape * 0.14, 2.0)
    grid = np.indices(data.shape).astype(np.float32)
    normalized = sum(((grid[axis] - center[axis]) / radii[axis]) ** 2 for axis in range(3))
    return (normalized <= 1.0).astype(np.uint8)


def ensure_segmentation_mask(mri: MRI, source: Path) -> Path:
    """Return the path to the cached mock segmentation mask, generating it once if needed."""
    mask_path = source.parent / "seg_mask.nii.gz"
    if mask_path.is_file():
        return mask_path

    data, _, _ = load_volume(source)
    mask = _mock_tumor_mask(data)

    # Reuse the original NIfTI affine so the mask aligns voxel-for-voxel with the MRI.
    reference = nib.load(str(source))
    mask_image = nib.Nifti1Image(mask, affine=reference.affine, header=reference.header)
    mask_image.set_data_dtype(np.uint8)
    nib.save(mask_image, str(mask_path))
    return mask_path


def render_mask_png(mask_path: Path, view: str, index: int) -> bytes:
    """Render a semi-transparent red overlay PNG for the segmentation mask slice."""
    mask = np.squeeze(np.asanyarray(nib.load(str(mask_path)).dataobj))
    axis = VIEW_AXIS[view]
    size = mask.shape[axis]
    index = max(0, min(int(index), size - 1))
    slice_mask = extract_slice(mask.astype(np.float32), view, index) > 0

    height, width = slice_mask.shape
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[..., 0] = 255          # red
    rgba[..., 1] = 20
    rgba[..., 2] = 20
    rgba[..., 3] = np.where(slice_mask, 160, 0).astype(np.uint8)

    buffer = io.BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(buffer, format="PNG")
    return buffer.getvalue()


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
