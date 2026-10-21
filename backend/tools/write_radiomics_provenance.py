"""Write a deterministic provenance manifest for the isolated Linux worker."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys

import radiomics
import SimpleITK
import numpy


ROOT = Path(__file__).resolve().parent


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


packages = sorted(
    ({"name": item.metadata["Name"], "version": item.version} for item in importlib.metadata.distributions()),
    key=lambda item: item["name"].lower(),
)
manifest = {
    "status": "build_verified",
    "role": "isolated Linux CPU radiomics worker; not a network service",
    "platform": f"{sys.platform}/{platform.machine()}",
    "base_image": "python:3.9-slim-bookworm@sha256:a02e9c5406c416c504d6c9a1a306ff4080c3173f1008d192f953bd20382a2d5c",
    "versions": {
        "python": platform.python_version(),
        "pyradiomics": radiomics.__version__,
        "numpy": numpy.__version__,
        "simpleitk": SimpleITK.Version_VersionString(),
    },
    "packages": packages,
    "inputs_sha256": {
        "source_Dockerfile": sha256(ROOT / "source-Dockerfile"),
        "requirements-radiomics-linux-amd64.txt": sha256(ROOT / "requirements-radiomics-linux-amd64.txt"),
        "requirements-radiomics-docopt.txt": sha256(ROOT / "requirements-radiomics-docopt.txt"),
        "extract_selected_radiomics.py": sha256(ROOT / "extract_selected_radiomics.py"),
        "write_radiomics_provenance.py": sha256(Path(__file__)),
    },
    "main_environment_changed": False,
}
(ROOT / "source.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
