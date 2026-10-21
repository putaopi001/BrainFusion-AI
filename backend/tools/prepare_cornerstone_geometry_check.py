"""Nibabel reference for JS/Cornerstone geometry; no inference or source writes."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

import nibabel as nib
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', required=True)
    parser.add_argument('--case-id', type=int, required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(exist_ok=False)
    with sqlite3.connect(Path(args.database).as_uri() + '?mode=ro', uri=True) as db:
        row = db.execute('SELECT sequences_json,segmentation_path FROM mris WHERE case_id=? ORDER BY id DESC LIMIT 1', (args.case_id,)).fetchone()
    files = [(key, Path(value), False) for key, value in json.loads(row[0]).items()]
    files.append(('mask', Path(row[1]), True))
    # Explicitly synthetic spatial fixtures, not DICOM or a patient cohort.
    a = np.array([[0, -2, 0, 12], [1.5, 0, 0, -8], [0, 0, -3, 21], [0, 0, 0, 1.]])
    for name, cls, dtype in [('synthetic-sform', nib.Nifti1Image, np.dtype('>i2')), ('synthetic-nifti2', nib.Nifti2Image, np.float32)]:
        img = cls(np.arange(60, dtype=np.int16).reshape(3, 4, 5), a)
        img.header.set_data_dtype(dtype)
        img.header.set_xyzt_units('mm')
        img.set_sform(a, code=1)
        q = a.copy(); q[0, 3] += 15
        img.set_qform(q, code=4)  # nibabel still chooses valid sform.
        img.header.set_slope_inter(2, -5)
        path = output / (name + '.nii.gz')
        nib.save(img, path)
        files.append((name, path, False))
    records = []
    for name, path, mask in files:
        img = nib.load(path)
        data = img.get_fdata(dtype=np.float32)
        coords = [(0, 0, 0), tuple(n - 1 for n in img.shape), tuple(n // 2 for n in img.shape)]
        positive = np.argwhere(data > 0)
        if mask:
            # A real nonempty model voxel selected deterministically, not accuracy evidence.
            coords.append(tuple(int(v) for v in positive[len(positive) // 2]))
        points = []
        for voxel in coords:
            ras = nib.affines.apply_affine(img.affine, voxel)
            points.append({'ijk': list(voxel), 'lps': (ras * [-1, -1, 1]).tolist(), 'value': float(data[voxel])})
        raw = data.astype('u1' if mask else '<f4').ravel(order='F').tobytes()
        records.append({'name': name, 'path': str(path), 'labelmap': mask, 'shape': list(img.shape),
                        'raw_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'voxel_sha256': hashlib.sha256(raw).hexdigest(), 'points': points})
    (output / 'reference.json').write_text(json.dumps({'reference': 'nibabel', 'records': records}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
