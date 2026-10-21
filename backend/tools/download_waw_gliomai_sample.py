"""Download a reproducible engineering subset of the open WAW-GliomAI v3 record.

Uses HTTP ranges to avoid downloading the 3.2 GB image archive for a few cases.
Source archive members are checked against ZIP CRC32; complete auxiliary files
are checked against the publisher's MD5. No authentication is required.
"""
import argparse
import hashlib
import io
import json
import re
import shutil
import time
import urllib.request
import zipfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


RECORD = "https://zenodo.org/api/records/22205631"


def request(url, headers=None):
    for attempt in range(3):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(url, headers=headers or {}), timeout=60
            )
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


class RangeFile(io.RawIOBase):
    def __init__(self, url, size):
        self.url, self.size, self.pos = url, size, 0
        self.cache_start, self.cache = 0, b""
        self.transferred = 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        position = offset if whence == 0 else (self.pos if whence == 1 else self.size) + offset
        if position < 0:
            raise ValueError("negative seek")
        self.pos = position
        return position

    def read(self, n=-1):
        n = min(self.size - self.pos, n if n >= 0 else self.size - self.pos)
        if n <= 0:
            return b""
        if not (self.cache_start <= self.pos and self.pos + n <= self.cache_start + len(self.cache)):
            end = min(self.size - 1, self.pos + max(n, 65536) - 1)
            blocks = []
            # Small requests limit recovery cost on unstable TLS connections.
            for start in range(self.pos, end + 1, 1048576):
                stop = min(end, start + 1048575)
                for attempt in range(3):
                    try:
                        with request(self.url, {"Range": f"bytes={start}-{stop}"}) as response:
                            expected = f"bytes {start}-{stop}/{self.size}"
                            if response.status != 206 or response.headers.get("Content-Range") != expected:
                                raise RuntimeError("Server did not honor the exact byte range")
                            block = response.read()
                            if len(block) != stop - start + 1:
                                raise RuntimeError("Truncated range response")
                        blocks.append(block)
                        self.transferred += len(block)
                        break
                    except Exception:
                        if attempt == 2:
                            raise
                        time.sleep(2 * (attempt + 1))
            self.cache = b"".join(blocks)
            self.cache_start = self.pos
        start = self.pos - self.cache_start
        self.pos += n
        return self.cache[start:start + n]


def patient_id(name):
    match = re.match(r"(\d+)_\d+_", PurePosixPath(name).name)
    return match.group(1) if match else None


def safe_target(root, member):
    target = (root / member).resolve()
    target.relative_to(root.resolve())
    return target


def write_member(archive, member, root):
    target = safe_target(root, member.filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = target.read_bytes() if target.exists() else None
    if data is None or len(data) != member.file_size or zlib.crc32(data) != member.CRC:
        # Reading to EOF makes zipfile verify the published member's CRC32.
        with archive.open(member) as source:
            data = source.read()
    if target.exists() and hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(data).digest():
        raise RuntimeError(f"Existing file differs: {target}")
    temporary = target.with_name(target.name + ".part")
    temporary.write_bytes(data)
    temporary.replace(target)
    print(f"Extracted {member.filename} ({len(data)} bytes)", flush=True)
    return {"member": member.filename, "path": str(target), "bytes": len(data),
            "zip_crc32": f"{member.CRC:08x}", "sha256": hashlib.sha256(data).hexdigest()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", type=int, default=5)
    args = parser.parse_args()
    if args.cases < 1:
        parser.error("--cases must be positive")
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    with request(RECORD) as response:
        record = json.load(response)
    if record["metadata"].get("access_right") != "open":
        raise RuntimeError("Record is not publicly open")
    (root / "zenodo_record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    files = {item["key"]: item for item in record["files"]}
    auxiliary = ["1_0_clinical_molecular_data.csv", "1_1_clinical_molecular_metadata_dictionary.csv",
                 "2_1_preop_scans_coreg_meta.csv", "4_radiomics_preop.csv", "3_1_preop_masks.zip"]
    completed = []
    for name in auxiliary:
        item = files[name]
        destination = root / "downloads" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        expected = item["checksum"].split(":", 1)[1]
        if not destination.exists() or hashlib.md5(destination.read_bytes()).hexdigest() != expected:
            part = destination.with_name(name + ".part")
            with request(item["links"]["self"]) as response, part.open("wb") as output:
                shutil.copyfileobj(response, output)
            if part.stat().st_size != item["size"] or hashlib.md5(part.read_bytes()).hexdigest() != expected:
                raise RuntimeError(f"Publisher checksum mismatch: {name}")
            part.replace(destination)
        completed.append({"file": name, "path": str(destination), "bytes": item["size"],
                          "checksum": item["checksum"], "verified": True})
        print(f"Verified {name}", flush=True)
    image_item = files["2_1_preop_scans_coreg.zip"]
    remote = RangeFile(image_item["links"]["self"], image_item["size"])
    extracted = []
    with zipfile.ZipFile(root / "downloads/3_1_preop_masks.zip") as masks, zipfile.ZipFile(remote) as images:
        image_members = [m for m in images.infolist() if m.filename.lower().endswith((".nii", ".nii.gz"))]
        mask_members = [m for m in masks.infolist() if m.filename.lower().endswith((".nii", ".nii.gz"))]
        groups = {}
        for member in image_members:
            identifier = patient_id(member.filename)
            if identifier:
                groups.setdefault(identifier, []).append(member)
        mask_ids = {patient_id(m.filename) for m in mask_members}
        eligible = []
        for identifier, members in groups.items():
            sequence_set = {re.search(r"_(t1n|t1c|t2f|t2w)\.nii(?:\.gz)?$", m.filename, re.I).group(1).lower()
                            for m in members if re.search(r"_(t1n|t1c|t2f|t2w)\.nii(?:\.gz)?$", m.filename, re.I)}
            if identifier in mask_ids and sequence_set == {"t1n", "t1c", "t2f", "t2w"}:
                eligible.append(identifier)
        selected = sorted(eligible, key=int)[:args.cases]
        if len(selected) < args.cases:
            raise RuntimeError(f"Only {len(selected)} complete image/mask patients found")
        # The archive inventory preserves the full-data route for later download.
        (root / "image_archive_inventory.json").write_text(json.dumps(
            [{"member": m.filename, "bytes": m.file_size, "compressed_bytes": m.compress_size,
              "patient_id": patient_id(m.filename)} for m in image_members], indent=2), encoding="utf-8")
        print(f"Selected engineering-only patients: {selected}", flush=True)
        def download_case(identifier):
            # Each worker owns its seek position and ZipFile. Never share a ranged
            # file object across concurrent ZIP readers.
            ranged = RangeFile(image_item["links"]["self"], image_item["size"])
            with zipfile.ZipFile(ranged) as archive:
                entries = [write_member(archive, member, root / "sample/images")
                           for member in groups[identifier]]
            return entries, ranged.transferred

        with ThreadPoolExecutor(max_workers=4) as pool:
            for entries, transferred in pool.map(download_case, selected):
                extracted.extend(entries)
                remote.transferred += transferred
        for member in mask_members:
            if patient_id(member.filename) in selected:
                extracted.append(write_member(masks, member, root / "sample/reference_masks"))
    manifest = {"dataset": "WAW-GliomAI", "record_id": record["id"],
                "source": "https://zenodo.org/records/22205631", "publication_date": record["metadata"]["publication_date"],
                "license": record["metadata"].get("license"), "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                "purpose": "engineering smoke tests; excluded from independent performance claims",
                "selected_patient_ids": selected, "complete_auxiliary_files": completed,
                "image_archive": {"file": image_item["key"], "published_bytes": image_item["size"],
                                  "published_checksum": image_item["checksum"],
                                  "range_bytes_transferred": remote.transferred,
                                  "full_archive_downloaded": False,
                                  "verification": "selected ZIP members CRC32, local SHA256; full archive MD5 not verified"},
                "extracted_members": extracted}
    (root / "sample_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Complete: {len(selected)} patients, {len(extracted)} files; manifest: {root / 'sample_manifest.json'}", flush=True)


if __name__ == "__main__":
    main()
