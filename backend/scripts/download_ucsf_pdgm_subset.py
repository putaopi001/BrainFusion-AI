"""Fetch a bounded, provenance-pinned UCSF-PDGM BraTS-format pilot subset.

This deliberately downloads at most ten patients and only four structural MRI
volumes plus the expert-corrected tumor mask. It never calls snapshot_download
or enumerates/downloads the full repository payload.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import shutil
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


REPO = "MedOtter/UCSF-PDGM"
REVISION = "e9372219cf1cd2fdd52260cd45f7514b4aa7638e"
METADATA_SHA256 = "afc1c23a0eb0597b56e603741e72f2308b4860281187cd3808e05b7a0116fd78"
FILES = (
    "T1.nii.gz", "T1c.nii.gz", "T2.nii.gz", "FLAIR.nii.gz",
    "tumor_segmentation.nii.gz",
)
CLINICAL_NAME = "UCSF-PDGM-metadata_v5.csv"
GLOSSARY_NAME = "UCSF-PDGM-metadata_glossary.csv"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def get_bytes(url: str, timeout: int = 60, retries: int = 3) -> bytes:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={"User-Agent": "BrainFusion-UCSF-PDGM-research-pilot/1.0"})
            with urlopen(req, timeout=timeout) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status} for {url}")
                return response.read()
        except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
            last = exc
            if attempt + 1 < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Request failed after {retries} attempts: {url}: {last}")


def pinned_url(path: str) -> str:
    return f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/{quote(path, safe='/')}?download=true"


def normalized_id(value: str) -> int:
    import re
    match = re.fullmatch(r"UCSF-PDGM-(\d+)(?:_FU\d+d)?", value.strip())
    if not match:
        raise ValueError(f"Unsupported patient ID syntax in source metadata: {value!r}")
    return int(match.group(1))


def choose_cases(clinical_csv: Path, count: int) -> list[dict[str, str]]:
    if not 5 <= count <= 10:
        raise ValueError("Pilot case count must be between 5 and 10")
    if sha256(clinical_csv) != METADATA_SHA256:
        raise ValueError("Local official v5 clinical CSV does not match the pinned source hash")
    by_id: dict[int, dict[str, str]] = {}
    with clinical_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"ID", "Final pathologic diagnosis (WHO 2021)", "IDH", "OS", "1-dead 0-alive", "BraTS21 ID"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Official metadata lacks required selection/provenance fields")
        for row in reader:
            # Imaging folders represent the baseline/preoperative acquisition;
            # follow-up rows are not separate images or independent patients.
            if "_FU" in row["ID"]:
                continue
            if row["Final pathologic diagnosis (WHO 2021)"].strip() != "Glioblastoma, IDH-wildtype":
                continue
            if row["IDH"].strip().lower() != "wildtype" or row["BraTS21 ID"].strip():
                continue
            try:
                os_days = float(row["OS"])
            except (TypeError, ValueError):
                continue
            status = row["1-dead 0-alive"].strip()
            if os_days <= 0 or status not in {"0", "1"}:
                continue
            number = normalized_id(row["ID"])
            normalized = {**row, "_numeric_id": str(number), "_event": status, "_os_days": str(int(os_days))}
            previous = by_id.get(number)
            if previous is not None and any(previous[k] != normalized[k] for k in ("OS", "1-dead 0-alive", "IDH", "Final pathologic diagnosis (WHO 2021)")):
                raise ValueError(f"Conflicting clinical rows for normalized patient {number}; refusing selection")
            by_id.setdefault(number, normalized)
    candidates = list(by_id.values())
    selected: list[dict[str, str]] = []
    for event in ("1", "0"):
        group = [r for r in candidates if r["_event"] == event]
        group.sort(key=lambda r: hashlib.sha256(("ucsf-pdgm-v5-seg-pilot-20261027:" + r["_numeric_id"]).encode()).hexdigest())
        selected.extend(group[: count // 2 if event == "1" else count - count // 2])
    selected.sort(key=lambda r: int(r["_numeric_id"]))
    if len(selected) != count or len({r["_numeric_id"] for r in selected}) != count:
        raise ValueError(f"Only {len(selected)} unique eligible non-BraTS-mapped GBM cases found")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-clinical-dir", type=Path, default=Path("E:/BrainFusion-Data/UCSF-PDGM/clinical"))
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--case-count", type=int, default=10)
    parser.add_argument("--resume-existing", action="store_true",
                        help="Resume only missing files in a partial download; existing content must match pinned hashes and is never overwritten")
    args = parser.parse_args()
    official = args.official_clinical_dir.resolve(strict=True)
    out = args.output_root.resolve()
    if out.exists() and not args.resume_existing:
        raise FileExistsError(f"Refusing to overwrite existing data directory: {out}")
    if out.exists() and (out / "subset-manifest.json").exists():
        raise FileExistsError("A completed subset manifest already exists; refusing to rewrite this data version")
    source_csv = official / CLINICAL_NAME
    source_glossary = official / GLOSSARY_NAME
    if not source_csv.is_file() or not source_glossary.is_file():
        raise FileNotFoundError("The locally verified TCIA v5 metadata and glossary are required")
    rows = choose_cases(source_csv, args.case_count)
    out.mkdir(parents=True, exist_ok=True)
    try:
        official_copy = out / "sources" / "TCIA-v5-local-official"
        mirror_copy = out / "sources" / "HF-pinned-mirror"
        official_copy.mkdir(parents=True, exist_ok=True)
        mirror_copy.mkdir(parents=True, exist_ok=True)
        for source in (source_csv, source_glossary):
            target = official_copy / source.name
            if target.exists():
                if sha256(target) != sha256(source):
                    raise RuntimeError(f"Existing official source copy differs; refusing overwrite: {target}")
            else:
                shutil.copy2(source, target)
        mirror_csv = get_bytes(pinned_url(CLINICAL_NAME))
        mirror_glossary = get_bytes(pinned_url(GLOSSARY_NAME))
        for name, payload in ((CLINICAL_NAME, mirror_csv), (GLOSSARY_NAME, mirror_glossary)):
            target = mirror_copy / name
            if target.exists():
                if sha256(target) != hashlib.sha256(payload).hexdigest():
                    raise RuntimeError(f"Existing pinned mirror source differs; refusing overwrite: {target}")
            else:
                target.write_bytes(payload)
        comparisons = {}
        for name in (CLINICAL_NAME, GLOSSARY_NAME):
            official_hash = sha256(official_copy / name)
            mirror_hash = sha256(mirror_copy / name)
            comparisons[name] = {"official_local_sha256": official_hash, "hf_mirror_sha256": mirror_hash,
                                 "byte_identical": official_hash == mirror_hash}
        if not comparisons[CLINICAL_NAME]["byte_identical"]:
            raise RuntimeError("Pinned HF v5 metadata differs bytewise from the local TCIA-designated copy")
        readme = get_bytes(pinned_url("README.md"))
        readme_path = out / "HF-README-pinned.md"
        if readme_path.exists():
            if sha256(readme_path) != hashlib.sha256(readme).hexdigest():
                raise RuntimeError("Existing pinned README differs; refusing overwrite")
        else:
            readme_path.write_bytes(readme)
        selected_records = []
        all_files = []
        for row in rows:
            number = int(row["_numeric_id"])
            folder_id = f"{number:04d}"
            patient_id = f"UCSF-PDGM-{folder_id}"
            listing_url = f"https://huggingface.co/api/datasets/{REPO}/tree/{REVISION}/{patient_id}"
            listing = json.loads(get_bytes(listing_url).decode("utf-8"))
            by_name = {item["path"].rsplit("/", 1)[-1]: item for item in listing if item.get("type") == "file"}
            expected_names = {f"{patient_id}_{suffix}" for suffix in FILES}
            if set(by_name) != expected_names:
                raise RuntimeError(f"Pinned repository file list differs for {patient_id}: {sorted(by_name)}")
            case_dir = out / "cases" / patient_id
            case_dir.mkdir(parents=True, exist_ok=True)
            case_files = []
            for filename in sorted(expected_names):
                item = by_name[filename]
                rel = item["path"]
                expected_size = int(item["size"])
                expected_lfs = str(item.get("lfs", {}).get("oid", "")).removeprefix("sha256:")
                if len(expected_lfs) != 64:
                    raise RuntimeError(f"Pinned LFS SHA-256 missing for {rel}")
                target = case_dir / filename
                if target.exists():
                    if target.stat().st_size != expected_size or sha256(target) != expected_lfs:
                        raise RuntimeError(f"Existing file does not match pinned hash; refusing overwrite: {rel}")
                else:
                    content = get_bytes(pinned_url(rel), timeout=120)
                    target.write_bytes(content)
                actual = sha256(target)
                record = {"path": rel, "size": target.stat().st_size, "sha256": actual,
                          "lfs_sha256": expected_lfs, "matches_pinned_lfs": actual == expected_lfs,
                          "expected_size": expected_size}
                if actual != expected_lfs or target.stat().st_size != expected_size:
                    raise RuntimeError(f"Downloaded file integrity check failed: {rel}")
                case_files.append(record)
                all_files.append(record)
            selected_records.append({"patient_id": patient_id, "clinical_id": row["ID"],
                                     "normalized_numeric_id": number, "event_code": int(row["_event"]),
                                     "os_days": int(row["_os_days"]), "known_brats21_id": None,
                                     "files": case_files})
        manifest = {
            "dataset": REPO, "revision": REVISION, "license": "CC-BY-4.0",
            "selection": {"n": len(selected_records), "seed": 20261027,
                          "rule": "IDH-wildtype GBM; positive OS; status in {0,1}; no BraTS21 ID; deterministic SHA-256 within event strata; normalized clinical numeric ID -> four-digit image directory"},
            "clinical_comparison": comparisons, "selected_cases": selected_records,
            "downloaded_files": len(all_files), "total_bytes": sum(x["size"] for x in all_files),
        }
        (out / "subset-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (out / "SOURCE.txt").write_text(
            f"TCIA UCSF-PDGM v5 collection: https://www.cancerimagingarchive.net/collection/ucsf-pdgm/\n"
            f"Hugging Face derived subset at immutable revision {REVISION}: https://huggingface.co/datasets/{REPO}/tree/{REVISION}\n"
            "HF README records the files as a v5-derived BraTS-format subset under CC BY 4.0. Image bytes are verified against that revision's LFS SHA-256; file-level byte identity against TCIA's full collection package was not independently verified.\n",
            encoding="utf-8")
    except Exception:
        # Keep any partial download for forensic recovery; never silently erase it.
        raise
    print(json.dumps({"output_root": str(out), "cases": len(rows), "files": len(all_files),
                      "bytes": sum(x["size"] for x in all_files),
                      "metadata_byte_identical": comparisons[CLINICAL_NAME]["byte_identical"],
                      "glossary_byte_identical": comparisons[GLOSSARY_NAME]["byte_identical"]}, indent=2))


if __name__ == "__main__":
    main()
