"""Capture recorded and locally verifiable Conda/Python provenance read-only.

Conda URLs and expected hashes come from conda-meta; cached archives are
re-hashed when present. Python wheel origins are reported only when
direct_url.json recorded them, and local archives are re-hashed when present.
Missing origins remain explicitly unknown. This is inventory, not an install lock.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import sys
from urllib.parse import unquote, urlparse


def capture(prefix: Path) -> dict:
    prefix = prefix.resolve(strict=True)
    if Path(sys.prefix).resolve() != prefix:
        raise ValueError("Run this tool with the interpreter inside --prefix")
    metadata_dir = prefix / "conda-meta"
    if not metadata_dir.is_dir():
        raise ValueError("--prefix has no conda-meta directory")

    conda_packages = []
    for record_path in sorted(metadata_dir.glob("*.json")):
        record = json.loads(record_path.read_text(encoding="utf-8"))
        archive_name = record.get("fn") or (record_path.stem + ".conda")
        extracted = Path(record.get("extracted_package_dir", ""))
        archive_path = extracted.parent / archive_name if str(extracted) else None
        cached_sha256 = None
        if archive_path and archive_path.is_file():
            digest = hashlib.sha256()
            with archive_path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            cached_sha256 = digest.hexdigest()
        conda_packages.append(
            {
                "name": record.get("name"),
                "version": record.get("version"),
                "build": record.get("build"),
                "url": record.get("url"),
                "sha256": record.get("sha256"),
                "md5": record.get("md5"),
                "cached_archive": archive_name if cached_sha256 else None,
                "cached_archive_sha256": cached_sha256,
                "cached_archive_matches_record": (
                    cached_sha256 == record.get("sha256") if cached_sha256 else None
                ),
            }
        )
    if not conda_packages:
        raise ValueError("No Conda package records found")
    conda_names = {item["name"].lower() for item in conda_packages if item["name"]}

    python_distributions = []
    for distribution in metadata.distributions():
        name = distribution.metadata.get("Name")
        if not name:
            continue
        direct_url_raw = distribution.read_text("direct_url.json")
        direct_url = None
        if direct_url_raw:
            recorded = json.loads(direct_url_raw)
            url = recorded.get("url", "")
            parsed_url = urlparse(url)
            local_path = None
            if parsed_url.scheme == "file":
                decoded_path = unquote(parsed_url.path)
                if len(decoded_path) >= 3 and decoded_path[0] == "/" and decoded_path[2] == ":":
                    decoded_path = decoded_path[1:]
                local_path = Path(decoded_path)
            wheel_sha256 = None
            if local_path and local_path.is_file():
                digest = hashlib.sha256()
                with local_path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                wheel_sha256 = digest.hexdigest()
            expected_hash = recorded.get("archive_info", {}).get("hashes", {}).get("sha256")
            direct_url = {
                "kind": "local_wheel" if url.lower().endswith(".whl") else "direct_url",
                "filename": Path(url.replace("\\", "/")).name if url else None,
                "archive_hashes": recorded.get("archive_info", {}).get("hashes", {}),
                "local_archive_sha256": wheel_sha256,
                "local_archive_matches_recorded": (
                    wheel_sha256 == expected_hash if wheel_sha256 and expected_hash else None
                ),
            }
        if name.lower() in conda_names:
            source_evidence = "conda_meta"
        elif direct_url and direct_url["kind"] == "local_wheel":
            source_evidence = "direct_wheel_metadata"
        else:
            source_evidence = "original_source_not_recorded"
        python_distributions.append(
            {
                "name": name,
                "version": distribution.version,
                "installer": (distribution.read_text("INSTALLER") or "").strip() or None,
                "source_evidence": source_evidence,
                "direct_url": direct_url,
            }
        )
    python_distributions.sort(key=lambda item: item["name"].lower())
    return {
        "status": "captured",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "interpreter": str(Path(sys.executable).resolve()),
        "python": sys.version,
        "environment_prefix": str(prefix),
        "conda_packages": conda_packages,
        "python_distributions": python_distributions,
        "summary": {
            "conda_packages": len(conda_packages),
            "conda_packages_with_url_and_sha256": sum(
                bool(item["url"] and item["sha256"]) for item in conda_packages
            ),
            "conda_archives_locally_rehashed": sum(
                item["cached_archive_sha256"] is not None for item in conda_packages
            ),
            "conda_archives_matching_recorded_sha256": sum(
                item["cached_archive_matches_record"] is True for item in conda_packages
            ),
            "python_distributions": len(python_distributions),
            "python_distributions_with_original_source_not_recorded": sum(
                item["source_evidence"] == "original_source_not_recorded"
                for item in python_distributions
            ),
            "direct_archives_locally_rehashed": sum(
                bool(item["direct_url"] and item["direct_url"]["local_archive_sha256"])
                for item in python_distributions
            ),
            "direct_archives_matching_recorded_sha256": sum(
                bool(item["direct_url"] and item["direct_url"]["local_archive_matches_recorded"] is True)
                for item in python_distributions
            ),
            "limitations": (
                "Cached Conda archives are re-hashed when present; archives absent "
                "from local caches are represented only by installed conda-meta. "
                "No archives were downloaded. Most Python wheel origins were not "
                "retained. This is not a complete install lock and does not prove "
                "all installed files match their original archives."
            ),
        },
        "environment_changed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to(Path("E:/BrainFusion-Runtime/results/nightly").resolve())
    output.mkdir(exist_ok=False)
    result = capture(args.prefix)
    (output / "main-environment-provenance.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    conda_lines = [
        "# Observed from installed conda-meta; installer has not been tested",
        *(
            f"{item['name']}=={item['version']}={item['build']} {item['url']} sha256={item['sha256']}"
            for item in result["conda_packages"]
        ),
    ]
    (output / "conda-explicit-observed-sha256.txt").write_text(
        "\n".join(conda_lines) + "\n", encoding="utf-8"
    )
    distribution_lines = [
        "# Installed versions; unknown wheel sources remain explicitly unverified",
        *(
            f"{item['name']}=={item['version']} [{item['source_evidence']}]"
            for item in result["python_distributions"]
        ),
    ]
    (output / "python-distributions-observed.txt").write_text(
        "\n".join(distribution_lines) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": result["status"], **result["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
