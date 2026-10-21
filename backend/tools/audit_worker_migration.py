"""Read-only preservation/CPU migration audit, fresh evidence directory only."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sqlite3


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-root', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--previous-runtime', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--gate-directory', default='candidate-reference-gate-complete')
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to(Path('E:/BrainFusion-Runtime/results/nightly').resolve())
    output.mkdir(exist_ok=False)
    manifest = json.loads((args.snapshot / 'manifest.json').read_text(encoding='utf-8'))
    for entry in manifest['files']:
        for path in (Path(entry['source']), args.snapshot / entry['relative']):
            assert path.stat().st_size == entry['bytes'] and digest(path) == entry['sha256'], str(path)
    legacy_jobs = []
    for path in (args.previous_runtime / 'feature_jobs').rglob('*'):
        if path.is_file():
            copy = args.run_root / 'feature_jobs' / path.relative_to(args.previous_runtime / 'feature_jobs')
            assert digest(path) == digest(copy), str(path)
            legacy_jobs.append(dict(relative=path.relative_to(args.previous_runtime / 'feature_jobs').as_posix(), sha256=digest(path)))
    gate = json.loads((args.run_root / args.gate_directory / 'compatibility.json').read_text(encoding='utf-8'))
    assert gate['worker_provenance_sha256'] == digest(Path('E:/BrainFusion-Runtime/envs/radiomics311-candidate/source.json'))
    old_gate = json.loads((args.snapshot / 'contracts/compatibility.json').read_text(encoding='utf-8'))
    probabilities = [abs(p['reextracted_probability'] - next(q['reextracted_probability'] for q in old_gate['patients'] if q['source_patient_id'] == p['source_patient_id'])) for p in gate['patients']]
    main_probe = json.loads(subprocess.run(['E:/BrainFusion-AI/.conda/brainfusion/python.exe', '-B', '-c',
        'import sys,torch,json;print(json.dumps(dict(python=sys.version.split()[0],torch=torch.__version__,cuda_available=torch.cuda.is_available(),cuda_build=torch.version.cuda)))'], capture_output=True, text=True, check=True).stdout)
    legacy_probe = json.loads(subprocess.run(['E:/BrainFusion-Runtime/envs/radiomics39/python.exe', '-B', '-c',
        'import sys,numpy,radiomics,SimpleITK,json;print(json.dumps(dict(python=sys.version.split()[0],numpy=numpy.__version__,pyradiomics=radiomics.__version__,simpleitk=SimpleITK.Version_VersionString())))'], capture_output=True, text=True, check=True).stdout)
    assert main_probe['cuda_available'] and main_probe['torch'] == '2.11.0+cu128'
    assert legacy_probe['python'] == '3.9.13' and legacy_probe['pyradiomics'] == 'v3.1.0'
    baseline = json.loads((args.run_root / 'valid-current-baseline/baseline.json').read_text(encoding='utf-8'))
    with sqlite3.connect((args.run_root / 'database-backup/restored-validation.db').as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = {name: [dict(row) for row in db.execute('SELECT * FROM "' + name.replace('"', '""') + '" ORDER BY 1')] for name in baseline['source_database_rows']}
        assert rows == baseline['source_database_rows']
        active_analysis = db.execute("SELECT count(*) FROM analysis_runs WHERE state IN ('queued','running')").fetchone()[0]
        assert active_analysis == 0
    states = [json.loads(p.read_text(encoding='utf-8'))['state'] for p in (args.run_root / 'feature_jobs').glob('*/*/*/state.json')]
    assert all(s not in ('queued', 'running') for s in states)
    pip_check = subprocess.run(['E:/BrainFusion-Runtime/envs/radiomics311-candidate/python.exe', '-B', '-m', 'pip', 'check'], capture_output=True, text=True, check=True).stdout.strip()
    record = dict(status='passed', created_utc=datetime.now(timezone.utc).isoformat(),
                  original_and_snapshot_files=len(manifest['files']), original_and_snapshot_bytes=manifest['total_bytes'],
                  preserved_legacy_job_files=legacy_jobs, provenance_gate_unchanged=True,
                  reference_finite_feature_comparisons=sum(len(p['features']) for p in gate['baseline_comparisons']),
                  maximum_old_new_reference_feature_difference=max(abs(f['old']-f['candidate']) for p in gate['baseline_comparisons'] for f in p['features']),
                  maximum_old_new_reference_probability_difference=max(probabilities), normalization_checks=gate['normalization_checks'],
                  main_environment=main_probe, legacy_worker=legacy_probe, new_gpu_inference_or_training=False,
                  database_rows_unchanged=True, active_analysis_tasks=active_analysis, active_feature_tasks=0,
                  feature_states=states, candidate_pip_check=pip_check)
    (output / 'validation.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in record.items() if k != 'preserved_legacy_job_files'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
