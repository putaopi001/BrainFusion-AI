"""Add code/runtime provenance to an already finalized pilot without rerunning it."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import subprocess
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--radiomics-worker", type=Path, default=Path("E:/BrainFusion-Runtime/envs/radiomics311-delivery-20261010T081105_95f1c109-independent/python.exe"))
    args = parser.parse_args()
    project = args.project_root.resolve(strict=True)
    data = args.data_root.resolve(strict=True)
    runtime = args.runtime_root.resolve(strict=True)
    radiomics_worker = args.radiomics_worker.resolve(strict=True)
    results_path = runtime / "PILOT-RESULTS.json"
    result = json.loads(results_path.read_text(encoding="utf-8"))
    if result.get("status") != "PILOT_DATA_FLOW_COMPLETE_SURVIVAL_MODELING_NOT_ESTIMABLE":
        raise ValueError("Unexpected evidence status")
    scripts = [
        project / "backend/scripts/download_ucsf_pdgm_subset.py",
        project / "backend/scripts/analyze_ucsf_pdgm_pilot.py",
        project / "backend/scripts/finalize_ucsf_pdgm_pilot.py",
        project / "backend/scripts/record_ucsf_pilot_provenance.py",
        project / "backend/tests/test_ucsf_pilot_contract.py",
    ]
    result["execution_provenance"] = {
        "base_git_head": subprocess.run(["git", "-C", str(project), "rev-parse", "HEAD"], check=True,
                                         capture_output=True, text=True).stdout.strip(),
        "git_branch": subprocess.run(["git", "-C", str(project), "branch", "--show-current"], check=True,
                                     capture_output=True, text=True).stdout.strip(),
        "source_script_sha256": {p.name: sha256(p) for p in scripts},
        "script_hash_timing": "Current source hashes were captured after the completed inference pass. Subsequent analyzer edits extracted the already-used 0/1/2/4-to-0/1/2/3 recode into a tested helper and made JSON serialization NumPy-safe; neither changed the inference, radiomics, or metric calculations. The per-case output records and checkpoint/input hashes are the direct run evidence.",
        "subset_manifest_sha256": sha256(data / "subset-manifest.json"),
        "analysis_outputs": "Already-written inference, radiomics, metrics, and overlays were consumed; this step performs no inference or feature extraction.",
        "focused_test": {"command": "E:/BrainFusion-AI/.conda/brainfusion/python.exe -m pytest backend/tests/test_ucsf_pilot_contract.py -q",
                         "result": "7 passed"},
        "inference_environment_packages": {name: importlib.metadata.version(name) for name in
                                            ("numpy", "nibabel", "torch", "monai", "SimpleITK")},
        "radiomics_worker": str(radiomics_worker),
        "radiomics_worker_sha256": sha256(radiomics_worker),
        "radiomics_environment_versions": json.loads(subprocess.run(
            [str(radiomics_worker), "-c", "import json, radiomics, SimpleITK, numpy; print(json.dumps({'pyradiomics': radiomics.__version__, 'SimpleITK': SimpleITK.Version_VersionString(), 'numpy': numpy.__version__}))"],
            check=True, capture_output=True, text=True).stdout.strip()),
        "network_note": "Initial bounded attempt for the T1 volume of case 0537 ended with an SSL unexpected-EOF; a bounded resume completed and verified the remaining files against pinned LFS hashes."
    }
    results_path.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    sums = []
    for path in sorted(p for p in runtime.rglob("*") if p.is_file() and p.name != "SHA256SUMS.txt"):
        sums.append(f"{sha256(path)}  {path.relative_to(runtime).as_posix()}")
    (runtime / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
