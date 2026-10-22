from pathlib import Path

import nibabel as nib
import numpy as np
from scipy.ndimage import binary_erosion
from scipy.spatial import cKDTree

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
    p, r = nib.load(str(predicted), mmap=False), nib.load(str(reference), mmap=False)
    pd = validate_mask(p, r)
    rd = validate_mask(r, r)
    affine = np.asarray(p.affine, dtype=float)
    if not np.isfinite(affine).all() or abs(float(np.linalg.det(affine[:3, :3]))) < 1e-8:
        raise ValueError("Mask affine must be finite and invertible")
    result = {}
    for key, labels in REGIONS.items():
        a, b = np.isin(pd, labels), np.isin(rd, labels)
        na, nb = int(a.sum()), int(b.sum())
        true_positive = int(np.count_nonzero(a & b))
        false_positive = na - true_positive
        false_negative = nb - true_positive
        dice = float(2 * true_positive / (na + nb)) if na + nb else 1.0
        precision = float(true_positive / na) if na else None
        recall = float(true_positive / nb) if nb else None
        hd95, reason = None, None
        if na and nb:
            sa = a & ~binary_erosion(a)
            sb = b & ~binary_erosion(b)
            # Transform surface voxel centers into patient coordinates. This preserves
            # oblique and non-isotropic physical geometry instead of assuming axis-only spacing.
            a_world = nib.affines.apply_affine(affine, np.argwhere(sa))
            b_world = nib.affines.apply_affine(affine, np.argwhere(sb))
            distances = np.concatenate([
                cKDTree(b_world).query(a_world, k=1, workers=1)[0],
                cKDTree(a_world).query(b_world, k=1, workers=1)[0],
            ])
            hd95 = float(np.percentile(distances, 95))
        elif not na and not nb:
            reason = "Both regions are empty; HD95 is undefined. Dice follows the documented both-empty rule."
        else:
            reason = "One region is empty; HD95 is undefined."
        result[key] = {"dice": round(dice, 6),
                       "precision": round(precision, 6) if precision is not None else None,
                       "recall": round(recall, 6) if recall is not None else None,
                       "true_positive_voxels": true_positive,
                       "false_positive_voxels": false_positive,
                       "false_negative_voxels": false_negative,
                       "hd95_mm": hd95,
                       "hd95_status": "available" if hd95 is not None else "not_available",
                       "hd95_reason": reason,
                       "empty_rule": "both_empty" if not na and not nb else "single_empty" if not na or not nb else None}
    return {"regions": result, "volumes_ml": region_volumes(predicted),
            "reference_volumes_ml": region_volumes(reference), "scope": "engineering sample comparison"}
