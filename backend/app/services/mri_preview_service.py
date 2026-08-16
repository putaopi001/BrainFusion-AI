from pathlib import Path

import numpy as np
import nibabel as nib
import SimpleITK as sitk
from PIL import Image


def generate_mri_previews(mri_path: Path, preview_dir: Path, mri_id: int) -> list[Path]:
    """Create normalized axial, coronal, and sagittal PNG previews."""
    if mri_path.name.lower().endswith((".nii", ".nii.gz")):
        volume = np.squeeze(nib.load(str(mri_path)).get_fdata(dtype=np.float32))
    else:
        image = sitk.ReadImage(str(mri_path))
        volume = np.squeeze(sitk.GetArrayFromImage(image)).astype(np.float32)
    if volume.ndim != 3:
        raise ValueError("MRI preview generation requires a 3D image volume")

    lower, upper = np.percentile(volume, (1, 99))
    if upper <= lower:
        upper = lower + 1
    normalized = np.clip((volume - lower) / (upper - lower), 0, 1)

    preview_dir.mkdir(parents=True, exist_ok=True)
    views = {
        "axial": (volume.shape[0], lambda index: volume[index, :, :]),
        "coronal": (volume.shape[1], lambda index: volume[:, index, :]),
        "sagittal": (volume.shape[2], lambda index: volume[:, :, index]),
    }
    preview_paths = []
    for view_name, (view_size, get_slice) in views.items():
        indices = np.linspace(view_size * 0.25, view_size * 0.75, 7, dtype=int)
        for position, index in enumerate(indices, start=1):
            output_path = preview_dir / f"mri_{mri_id}_{view_name}_{position:02d}.png"
            Image.fromarray((get_slice(index) * 255).astype(np.uint8)).save(output_path)
            preview_paths.append(output_path)

    return preview_paths
