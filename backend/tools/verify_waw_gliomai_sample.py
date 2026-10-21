"""Verify downloaded sample hashes, MRI/mask geometry, labels and linkage."""
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import nibabel as nib
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = json.loads((root / "sample_manifest.json").read_text(encoding="utf-8"))
    for item in manifest["extracted_members"]:
        actual = hashlib.sha256(Path(item["path"]).read_bytes()).hexdigest()
        if actual != item["sha256"]:
            raise ValueError(f"SHA256 mismatch: {item['path']}")
    for item in manifest["complete_auxiliary_files"]:
        algorithm, expected = item["checksum"].split(":", 1)
        if hashlib.new(algorithm, Path(item["path"]).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Auxiliary checksum mismatch: {item['file']}")
    with (root / "downloads/1_0_clinical_molecular_data.csv").open(encoding="utf-8-sig") as handle:
        clinical = list(csv.DictReader(handle, delimiter=";"))
    clinical_ids = {row["id"] for row in clinical}
    report = {"dataset": manifest["dataset"], "record_id": manifest["record_id"],
              "scope": "engineering sample only, not model-performance evaluation", "cases": [],
              "clinical_rows": len(clinical), "clinical_label_counts": {
                  name: dict(Counter(row[name] for row in clinical)) for name in ["idh1/2", "mgmt_met"]}}
    for identifier in manifest["selected_patient_ids"]:
        files = sorted((root / "sample/images").rglob(f"{identifier}_0_brain_*.nii.gz"))
        mask_files = sorted((root / "sample/reference_masks").rglob(f"{identifier}_0_tumor_mask_pre.nii.gz"))
        if len(files) != 4 or len(mask_files) != 1 or identifier not in clinical_ids:
            raise ValueError(f"Incomplete image/mask/clinical linkage: {identifier}")
        mask_image = nib.load(str(mask_files[0]))
        mask = np.asanyarray(mask_image.dataobj)
        labels = np.unique(mask)
        if not np.isfinite(mask).all() or not np.isin(labels, [0, 1, 2, 3, 4]).all():
            raise ValueError(f"Invalid mask labels: {identifier}")
        entries = []
        for path in files:
            image = nib.load(str(path))
            data = np.asanyarray(image.dataobj)
            if image.shape != mask_image.shape or not np.allclose(image.affine, mask_image.affine, atol=1e-4, rtol=0):
                raise ValueError(f"Image/mask geometry mismatch: {path}")
            if data.ndim != 3 or not np.isfinite(data).all():
                raise ValueError(f"Invalid image volume: {path}")
            entries.append({"sequence": path.name.split("_brain_")[1].split(".")[0], "path": str(path),
                            "shape": list(image.shape), "spacing_mm": list(map(float, image.header.get_zooms()[:3])),
                            "axis_codes": list(nib.aff2axcodes(image.affine)), "finite": True})
        voxel_ml = abs(float(np.linalg.det(mask_image.affine[:3, :3]))) / 1000
        report["cases"].append({"patient_id": identifier, "images": entries, "mask": str(mask_files[0]),
                                "mask_labels": labels.tolist(), "mask_matches_all_images": True,
                                "reference_label_volumes_ml": {str(int(label)): round(float(np.sum(mask == label)) * voxel_ml, 4)
                                                               for label in labels if label != 0}})
    report["passed"] = True
    output = root / "sample_validation.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": True, "case_count": len(report["cases"]), "report": str(output),
                      "clinical_rows": report["clinical_rows"], "label_counts": report["clinical_label_counts"]}))


if __name__ == "__main__":
    main()
