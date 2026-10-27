"""Download/resume the pinned UCSF v5 eligible GBM cohort with LFS verification."""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import json
import os
import random
import shutil
import time
from pathlib import Path
from urllib.parse import quote
import requests

try:
    from .inventory_ucsf_fusion_cohort_v2 import REVISION, REPO, get, sha256
except ImportError:  # Executed as a script from this directory.
    from inventory_ucsf_fusion_cohort_v2 import REVISION, REPO, get, sha256

UA = "BrainFusion-UCSF-Fusion-Study-V2/1.0"
PILOT_ROOT = Path("E:/BrainFusion-Data/UCSF-PDGM/research-v2/MedOtter-UCSF-PDGM-e9372219")
PILOT_RUN = "ucsf-pdgm-fusion-pilot-20261027-v1"


def atomic_json(path: Path, value) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2), encoding="utf-8")
    os.replace(temp, path)


def safe_error(exc: Exception) -> str:
    """Persist only a safe failure category, never arbitrary URLs or headers."""
    name = type(exc).__name__
    if exc.__cause__ is not None:
        return f"{name} after bounded retries; underlying {safe_error(exc.__cause__)}"
    lowered = name.lower()
    if "ssl" in lowered or "tls" in lowered or "eof" in lowered:
        category = "TLS transfer interrupted"
    elif "timeout" in lowered:
        category = "bounded network request timed out"
    elif "http" in lowered:
        category = "remote HTTP request failed"
    elif "connection" in lowered:
        category = "network connection failed"
    else:
        category = "download failed; inspect local traceback without sharing signed URLs"
    return f"{name}: {category}; URL and signing parameters redacted"


def download_one(entry: dict, target: Path) -> dict:
    expected_size, expected_sha = int(entry["size"]), entry["sha256"]
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.stat().st_size == expected_size and sha256(target) == expected_sha:
            return {"status": "reused_verified", "path": str(target), "size": expected_size, "sha256": expected_sha}
        raise RuntimeError(f"Existing file differs from pinned content; refusing overwrite: {target}")
    part = target.with_name(target.name + ".part")
    url = f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/{quote(entry['path'], safe='/')}?download=true"
    last = None
    for attempt in range(3):
        offset = part.stat().st_size if part.exists() else 0
        if offset > expected_size:
            raise RuntimeError(f"Partial file exceeds pinned size: {part}")
        if offset == expected_size:
            if sha256(part) == expected_sha:
                os.replace(part, target)
                return {"status": "resumed_verified", "path": str(target), "size": expected_size, "sha256": expected_sha}
            raise RuntimeError(f"Full-size partial file has the wrong pinned hash; preserved for review: {part}")
        try:
            headers = {"User-Agent": UA}
            if offset:
                headers["Range"] = f"bytes={offset}-"
            with requests.get(url, headers=headers, stream=True, timeout=(20, 120)) as response:
                response.raise_for_status()
                if offset and response.status_code == 206:
                    mode = "ab"
                else:
                    offset, mode = 0, "wb"
                with part.open(mode) as stream:
                    for block in response.iter_content(chunk_size=1024 * 1024):
                        if not block:
                            continue
                        stream.write(block)
                        if stream.tell() > expected_size:
                            raise RuntimeError(f"Transfer exceeded pinned size for {entry['path']}")
            if not part.exists():
                raise RuntimeError("HTTP transfer completed without a partial output file")
            if part.stat().st_size > expected_size:
                raise RuntimeError(f"Transfer exceeded pinned size for {entry['path']}")
            if part.stat().st_size != expected_size or sha256(part) != expected_sha:
                raise RuntimeError(f"Size/hash mismatch after transfer: {entry['path']}")
            os.replace(part, target)
            return {"status": "downloaded_verified", "path": str(target), "size": expected_size, "sha256": expected_sha}
        except (TimeoutError, OSError, RuntimeError, requests.RequestException) as exc:
            last = exc
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError("Transfer failed after 3 bounded attempts; partial retained if present") from last


def load_pilot_reuse(inventory: dict) -> dict[str, dict]:
    old_manifest_path = PILOT_ROOT / "subset-manifest.json"
    if not old_manifest_path.is_file():
        return {}
    manifest = json.loads(old_manifest_path.read_text(encoding="utf-8"))
    if manifest.get("revision") != REVISION:
        raise ValueError("Existing ten-case pilot is not on the required immutable revision")
    reused = {}
    for case in manifest.get("selected_cases", []):
        patient = case["patient_id"]
        expected = inventory["case_files"].get(patient)
        if not expected:
            continue
        case_dir = PILOT_ROOT / "cases" / patient
        for entry in expected["files"]:
            name = Path(entry["path"]).name
            previous = next((x for x in case["files"] if Path(x["path"]).name == name), None)
            target = case_dir / name
            if (previous is None or not target.is_file() or target.stat().st_size != int(entry["size"])
                    or sha256(target) != entry["sha256"] or previous["sha256"] != entry["sha256"]
                    or int(previous["size"]) != int(entry["size"])):
                raise ValueError(f"Prior pilot file failed reuse validation: {target}")
        reused[patient] = {"kind": "reused_verified_prior_pilot", "directory": str(case_dir),
                           "files": expected["files"]}
    return reused


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4 or not 1 <= args.batch_size <= 50:
        raise ValueError("Workers must be 1-4 and batch size 1-50")
    root = args.output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    inventory = json.loads(args.inventory.resolve(strict=True).read_text(encoding="utf-8"))
    if inventory.get("revision") != REVISION or inventory.get("dataset") != REPO:
        raise ValueError("File inventory is not pinned to the required dataset revision")
    source_root = root / "sources"
    source_root.mkdir(exist_ok=True)
    official_dir = Path("E:/BrainFusion-Data/UCSF-PDGM/clinical").resolve(strict=True)
    for name, expected in (("UCSF-PDGM-metadata_v5.csv", inventory["clinical_csv_sha256"]),
                           ("UCSF-PDGM-metadata_glossary.csv", "f1404bcd730572d05bdf7ead2e62e32843944d0e27a05cd0ef2dcca8ce69378d")):
        source = official_dir / name
        if not source.is_file() or sha256(source) != expected:
            raise ValueError(f"Source metadata hash mismatch: {source}")
        target = source_root / name
        if target.exists():
            if sha256(target) != expected:
                raise ValueError(f"Existing copied metadata differs; refusing overwrite: {target}")
        else:
            shutil.copy2(source, target)
    readme = PILOT_ROOT / "HF-README-pinned.md"
    if readme.is_file():
        target = source_root / "HF-README-pinned.md"
        if target.exists() and sha256(target) != sha256(readme):
            raise ValueError(f"Existing pinned README differs; refusing overwrite: {target}")
        if not target.exists():
            shutil.copy2(readme, target)
    cases = inventory["case_files"]
    candidate_csv = root / "eligible-cohort-private.csv"
    if not candidate_csv.exists():
        raise FileNotFoundError("Run the inventory step first; private cohort CSV is missing")
    with candidate_csv.open("r", encoding="utf-8-sig", newline="") as f:
        cohort_rows = list(csv.DictReader(f))
    eligible = [r for r in cohort_rows if r["mirror_file_listing_verified"].lower() == "true"]
    eligible_ids = [r["patient_id"] for r in eligible]
    if len(eligible_ids) != len(set(eligible_ids)):
        raise ValueError("Duplicate eligible patient ID in private crosswalk")
    missing_inventory = set(eligible_ids) - set(cases)
    if missing_inventory:
        raise ValueError(f"Eligible rows lack complete pinned files: {len(missing_inventory)}")

    reuse = load_pilot_reuse(inventory)
    # The previous pilot was a convenience subset, so reuse only its intersection with the audited cohort.
    reuse = {k: v for k, v in reuse.items() if k in set(eligible_ids)}
    previous_progress_path = root / "download-progress.json"
    progress = json.loads(previous_progress_path.read_text(encoding="utf-8")) if previous_progress_path.exists() else {}
    completed = []
    failed = []

    def fetch_case(patient: str) -> dict:
        if patient in reuse:
            return {"patient_id": patient, **reuse[patient], "verified_files": len(reuse[patient]["files"])}
        files = []
        case_dir = root / "cases" / patient
        for entry in cases[patient]["files"]:
            target = case_dir / Path(entry["path"]).name
            result = download_one(entry, target)
            files.append({**entry, "local_path": str(target), "status": result["status"]})
        return {"patient_id": patient, "kind": "downloaded_in_v2_root", "directory": str(case_dir),
                "files": files, "verified_files": len(files)}

    # A fixed order makes resumable partial cohorts less dependent on the numeric
    # patient-ID prefix while preserving identical eventual coverage.
    download_order = eligible_ids.copy()
    random.Random(20261027).shuffle(download_order)
    todo = [p for p in download_order if p not in progress.get("completed_patient_ids", [])]
    for start in range(0, len(todo), args.batch_size):
        batch = todo[start:start + args.batch_size]
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(fetch_case, patient): patient for patient in batch}
            for future in concurrent.futures.as_completed(futures):
                patient = futures[future]
                try:
                    record = future.result()
                    completed.append(record)
                    progress.setdefault("case_records", {})[patient] = record
                    progress.setdefault("completed_patient_ids", [])
                    if patient not in progress["completed_patient_ids"]:
                        progress["completed_patient_ids"].append(patient)
                    progress.update({"revision": REVISION, "verified_case_count": len(progress["completed_patient_ids"]),
                                     "eligible_case_count": len(eligible_ids), "last_completed_patient": patient})
                    atomic_json(previous_progress_path, progress)
                except Exception as exc:
                    failed.append({"patient_id": patient, "error": safe_error(exc)})
        print(json.dumps({"batch_end": min(start + len(batch), len(todo)), "todo": len(todo),
                          "total_verified": progress.get("verified_case_count", 0), "failures_this_run": len(failed)}))
        if failed:
            break

    if failed:
        atomic_json(root / "download-failures.json", {"revision": REVISION, "failures": failed})
        raise RuntimeError(f"Stopped after bounded batch failure; verified files/cases were preserved: {failed[0]['error']}")

    all_records = progress.get("case_records", {})
    if set(all_records) != set(eligible_ids):
        print(json.dumps({"status": "PARTIAL_RESUMABLE", "verified_cases": len(all_records), "eligible": len(eligible_ids)}))
        return
    manifest = {"dataset": REPO, "revision": REVISION, "license": "CC-BY-4.0",
                "inventory_sha256": sha256(args.inventory.resolve(strict=True)),
                "clinical_csv_sha256": inventory["clinical_csv_sha256"],
                "eligible_cohort": inventory["cohort"], "file_count": sum(len(r["files"]) for r in all_records.values()),
                "total_file_bytes": sum(int(x["size"]) for r in all_records.values() for x in r["files"]),
                "prior_pilot_cases_reused_without_redownload": sum(r["kind"] == "reused_verified_prior_pilot" for r in all_records.values()),
                "cases": all_records}
    atomic_json(root / "expanded-cohort-manifest.json", manifest)
    print(json.dumps({"status": "ALL_ELIGIBLE_FILES_VERIFIED", "cases": len(all_records),
                      "files": manifest["file_count"], "bytes": manifest["total_file_bytes"],
                      "reused_prior_pilot_cases": manifest["prior_pilot_cases_reused_without_redownload"]}, indent=2))


if __name__ == "__main__":
    main()
