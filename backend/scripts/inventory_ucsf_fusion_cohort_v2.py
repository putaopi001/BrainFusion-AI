"""Inventory the pinned UCSF v5 GBM survival cohort against the HF image subset.

Patient-level inventory and download manifests are written only under the protected
data directory. No clinical CSV or patient list belongs in Git.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO = "MedOtter/UCSF-PDGM"
REVISION = "e9372219cf1cd2fdd52260cd45f7514b4aa7638e"
CSV_SHA256 = "afc1c23a0eb0597b56e603741e72f2308b4860281187cd3808e05b7a0116fd78"
GLOSSARY_SHA256 = "f1404bcd730572d05bdf7ead2e62e32843944d0e27a05cd0ef2dcca8ce69378d"
SUFFIXES = ("T1.nii.gz", "T1c.nii.gz", "T2.nii.gz", "FLAIR.nii.gz", "tumor_segmentation.nii.gz")
USER_AGENT = "BrainFusion-UCSF-Fusion-Study-V2/1.0"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def get(url: str, timeout: int = 45, retries: int = 3) -> bytes:
    last = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=timeout) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}: {url}")
                return response.read()
        except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
            last = exc
            if attempt + 1 < retries:
                retry_after = 0
                if isinstance(exc, HTTPError):
                    try:
                        retry_after = min(15, int(exc.headers.get("Retry-After", "0")))
                    except ValueError:
                        retry_after = 0
                time.sleep(max(retry_after, 1.5 * (attempt + 1)))
    raise RuntimeError(f"request failed after {retries} bounded attempts: {url}: {last}")


def normalized_id(raw: str) -> int:
    match = re.fullmatch(r"UCSF-PDGM-(\d+)", raw.strip())
    if not match:
        raise ValueError(f"not a baseline UCSF patient ID: {raw!r}")
    return int(match.group(1))


def eligible_cohort(clinical_csv: Path) -> tuple[list[dict], dict]:
    if sha256(clinical_csv) != CSV_SHA256:
        raise ValueError("Local clinical CSV does not match the pinned TCIA v5 hash")
    required = {"ID", "Sex", "Age at MRI", "Final pathologic diagnosis (WHO 2021)",
                "1-dead 0-alive", "OS", "Biopsy prior to imaging", "BraTS21 ID"}
    rows = list(csv.DictReader(clinical_csv.open("r", encoding="utf-8-sig", newline="")))
    if not required.issubset(rows[0] if rows else {}):
        raise ValueError("v5 clinical CSV is missing the reviewed cohort contract")
    baseline = [r for r in rows if not re.search(r"_FU(?:\d|$)", r["ID"].strip())]
    gbm = [r for r in baseline if r["Final pathologic diagnosis (WHO 2021)"].strip() == "Glioblastoma, IDH-wildtype"]
    eligible, reasons = [], {"invalid_age": 0, "unsupported_sex": 0, "invalid_os": 0,
                            "invalid_status": 0, "unsupported_biopsy": 0}
    seen = set()
    for row in gbm:
        raw_id = row["ID"].strip()
        key = normalized_id(raw_id)
        if key in seen:
            raise ValueError(f"duplicate baseline patient ID: {raw_id}")
        seen.add(key)
        try:
            age, os_days = float(row["Age at MRI"]), float(row["OS"])
        except (TypeError, ValueError):
            reasons["invalid_os"] += 1
            continue
        if not (math.isfinite(age) and 18 <= age <= 120):
            reasons["invalid_age"] += 1
            continue
        if row["Sex"].strip() not in {"F", "M"}:
            reasons["unsupported_sex"] += 1
            continue
        if not (math.isfinite(os_days) and os_days > 0):
            reasons["invalid_os"] += 1
            continue
        try:
            event = int(row["1-dead 0-alive"].strip())
        except (TypeError, ValueError):
            reasons["invalid_status"] += 1
            continue
        if event not in {0, 1}:
            reasons["invalid_status"] += 1
            continue
        biopsy = row["Biopsy prior to imaging"].strip()
        if biopsy not in {"Yes", "No"}:
            reasons["unsupported_biopsy"] += 1
            continue
        eligible.append({"clinical_id": raw_id, "numeric_id": key, "patient_id": f"UCSF-PDGM-{key:04d}",
                         "event": event, "os_days": int(os_days), "age_at_mri": age,
                         "sex": row["Sex"].strip(), "biopsy_prior_to_imaging": biopsy,
                         "brats21_id": row["BraTS21 ID"].strip()})
    if len(eligible) != 367 or sum(r["event"] for r in eligible) != 223:
        raise ValueError(f"Pinned V2 cohort contract changed: n={len(eligible)}, events={sum(r['event'] for r in eligible)}")
    return eligible, {"source_rows": len(rows), "baseline_rows": len(baseline), "baseline_gbm_rows": len(gbm),
                      "eligible_n": len(eligible), "events": sum(r["event"] for r in eligible),
                      "censored": len(eligible) - sum(r["event"] for r in eligible), "exclusions": reasons,
                      "braTS21_mapped": sum(bool(r["brats21_id"]) for r in eligible),
                      "endpoint": "TCIA v5 glossary: OS in days from initial diagnosis to last clinical follow-up; status 1=dead, 0=alive.",
                      "prediction_landmark": "Preoperative diagnostic MRI; diagnosis-to-MRI interval is not encoded in the reviewed cohort contract."}


def api_siblings() -> dict[str, dict]:
    url = f"https://huggingface.co/api/datasets/{REPO}/revision/{REVISION}?blobs=true"
    payload = json.loads(get(url))
    if payload.get("sha") != REVISION:
        raise ValueError("Hugging Face repository response does not match the pinned revision")
    siblings = payload.get("siblings", [])
    return {str(x["rfilename"]): x for x in siblings if x.get("rfilename")}


def inventory(args) -> dict:
    clinical_csv = args.clinical_csv.resolve(strict=True)
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    candidates, cohort_summary = eligible_cohort(clinical_csv)
    siblings = api_siblings()
    sibling_sha = hashlib.sha256(json.dumps(siblings, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    available_by_name = {}
    for case in candidates:
        names = {f"{case['patient_id']}/{case['patient_id']}_{suffix}" for suffix in SUFFIXES}
        available_by_name[case["patient_id"]] = names.issubset(siblings)
    listings = {}
    for row in candidates:
        patient = row["patient_id"]
        paths = [f"{patient}/{patient}_{suffix}" for suffix in SUFFIXES]
        entries = []
        for path in paths:
            item = siblings.get(path, {})
            digest = str(item.get("lfs", {}).get("sha256", ""))
            size = int(item.get("size", -1))
            if len(digest) != 64 or size <= 0:
                entries = []
                break
            entries.append({"path": path, "size": size, "sha256": digest})
        if len(entries) == len(SUFFIXES):
            listings[patient] = {"complete": True, "files": entries, "bytes": sum(x["size"] for x in entries)}
    complete = [r for r in candidates if r["patient_id"] in listings]
    total_bytes = sum(listings[r["patient_id"]]["bytes"] for r in complete)
    inventory_path = output / "cohort-file-inventory.json"
    private_path = output / "eligible-cohort-private.csv"
    payload = {"dataset": REPO, "revision": REVISION, "license": "CC-BY-4.0",
               "clinical_csv_sha256": sha256(clinical_csv), "mirror_siblings_listing_sha256": sibling_sha,
               "cohort": cohort_summary,
               "mirror_availability": {"eligible_cohort_n": len(candidates),
                                        "five_required_paths_present": sum(available_by_name.values()),
                                        "all_files_metadata_and_lfs_sha_verified": len(complete),
                                        "unavailable_or_incomplete": len(candidates) - len(complete),
                                        "expected_transfer_bytes": total_bytes,
                                        "case_listing_errors": []},
               "case_files": {k: v for k, v in sorted(listings.items()) if v.get("complete")}}
    inventory_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    with private_path.open("w", newline="", encoding="utf-8") as f:
        fields = list(candidates[0]) + ["mirror_five_file_set_present", "mirror_file_listing_verified"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in candidates:
            patient = row["patient_id"]
            w.writerow({**row, "mirror_five_file_set_present": available_by_name[patient],
                        "mirror_file_listing_verified": bool(listings.get(patient, {}).get("complete"))})
    return payload


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--clinical-csv", type=Path, default=Path("E:/BrainFusion-Data/UCSF-PDGM/clinical/UCSF-PDGM-metadata_v5.csv"))
    p.add_argument("--output-root", type=Path, required=True)
    a = p.parse_args()
    data = inventory(a)
    inventory_sha = sha256(a.output_root.resolve(strict=True) / "cohort-file-inventory.json")
    print(json.dumps({"revision": data["revision"], "eligible": data["cohort"]["eligible_n"],
                      "events": data["cohort"]["events"], "censored": data["cohort"]["censored"],
                      "mapped_to_brats21": data["cohort"]["braTS21_mapped"],
                      "five_path_available": data["mirror_availability"]["five_required_paths_present"],
                      "all_hash_metadata_verified": data["mirror_availability"]["all_files_metadata_and_lfs_sha_verified"],
                      "expected_bytes": data["mirror_availability"]["expected_transfer_bytes"],
                      "listing_errors": len(data["mirror_availability"]["case_listing_errors"]),
                      "inventory_sha256": inventory_sha}, indent=2))


if __name__ == "__main__":
    main()
