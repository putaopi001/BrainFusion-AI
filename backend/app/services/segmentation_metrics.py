from pathlib import Path

import nibabel as nib
import numpy as np
from scipy.ndimage import binary_erosion, distance_transform_edt

REGIONS = {"WT": [1, 2, 3], "TC": [1, 3], "ET": [3]}


def validate_mask(image, reference):
    if image.shape != reference.shape or not np.allclose(image.affine, reference.affine, atol=1e-4, rtol=0):
        raise ValueError("Mask must match the MRI shape and affine")
    data = np.asanyarray(image.dataobj)
    if not np.isfinite(data).all() or not np.isin(np.unique(data), [0, 1, 2, 3, 4]).all():
        raise ValueError("Mask contains invalid labels")
    return data


def region_volumes(mask_path):
    image = nib.load(str(mask_path))
    data = validate_mask(image, image)
    ml = abs(float(np.linalg.det(image.affine[:3, :3]))) / 1000
    return {key: round(float(np.isin(data, labels).sum()) * ml, 4) for key, labels in REGIONS.items()}


def evaluate(predicted: Path, reference: Path):
    p, r = nib.load(str(predicted)), nib.load(str(reference))
    pd = validate_mask(p, r)
    rd = validate_mask(r, r)
    spacing = p.header.get_zooms()[:3]
    result = {}
    for key, labels in REGIONS.items():
        a, b = np.isin(pd, labels), np.isin(rd, labels)
        na, nb = int(a.sum()), int(b.sum())
        dice = float(2 * np.count_nonzero(a & b) / (na + nb)) if na + nb else 1.0
        hd95 = None
        if na and nb:
            sa = a & ~binary_erosion(a)
            sb = b & ~binary_erosion(b)
            distances = np.concatenate([distance_transform_edt(~sb, sampling=spacing)[sa],
                                         distance_transform_edt(~sa, sampling=spacing)[sb]])
            hd95 = float(np.percentile(distances, 95))
        result[key] = {"dice": round(dice, 6), "hd95_mm": hd95,
                       "empty_rule": "both_empty" if not na and not nb else "single_empty" if not na or not nb else None}
    return {"regions": result, "volumes_ml": region_volumes(predicted),
            "reference_volumes_ml": region_volumes(reference), "scope": "engineering sample comparison"}
