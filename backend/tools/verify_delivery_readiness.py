"""Read-only local handoff checks; never install, publish or certify new machines.

Verify historical source and engineering archives without extraction; compare
them to current source, check the existing runtime using the real preflight,
and preserve database content signatures. Only an owned fresh evidence
directory is written. Run under the unified development lock.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import subprocess
import sys
import zipfile

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.core.runtime_config import load_runtime_config
from tools.prepare_source_delivery import scan


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def safe_member(name):
    path = PurePosixPath(name)
    if not name or '\\' in name or ':' in name or path.is_absolute() or '..' in path.parts or path.as_posix() != name:
        raise ValueError('Unsafe archive/manifest member')
    return name


def verify_archive(archive_path, entries, expected_sha256, extra_entries=()):
    if sha256(archive_path) != expected_sha256:
        raise ValueError('Archive checksum mismatch')
    expected = {}
    for entry in entries:
        name = safe_member(entry['path'])
        if name in expected or not 0 <= entry['bytes'] <= 2 * 1024**2:
            raise ValueError('Duplicate or oversized manifest member')
        expected[name] = entry
    extras = {safe_member(name) for name in extra_entries}
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != set(expected) | extras:
            raise ValueError('Archive manifest member set mismatch')
        if sum(info.file_size for info in archive.infolist()) > 20 * 1024**2:
            raise ValueError('Archive exceeds bounded handoff size')
        for info in archive.infolist():
            safe_member(info.filename)
            if info.file_size > 2 * 1024**2 or info.is_dir():
                raise ValueError('Oversized or directory archive member')
            if info.filename in expected:
                item = expected[info.filename]
                raw = archive.read(info)
                if len(raw) != item['bytes'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
                    raise ValueError('Archive member checksum mismatch: ' + info.filename)
    return {'status': 'passed', 'payload_files': len(expected), 'archive_sha256': expected_sha256,
            'archive_bytes': Path(archive_path).stat().st_size, 'no_extraction': True}


def source_changes(previous, current):
    old = {entry['path']: entry['sha256'] for entry in previous}
    new = {entry['path']: entry['sha256'] for entry in current}
    return {'added': sorted(new.keys() - old.keys()), 'removed': sorted(old.keys() - new.keys()),
            'changed': sorted(name for name in old.keys() & new.keys() if old[name] != new[name]),
            'unchanged': sum(old[name] == new[name] for name in old.keys() & new.keys()),
            'is_current': old == new}



def delivery_gaps(source_is_current):
    gaps = ['Historical main environment original package download URLs/file hashes remain incomplete; installed versions are not a provenance lock']
    if not source_is_current:
        gaps.append('Source ZIP differs from current source; package a fresh accepted candidate before calling it current')
    gaps.extend([
        'New-machine installation has not been performed',
        'Real four-sequence DICOM acceptance requires licensed data and independent image-privacy review',
        'Independent user operation and mentor rehearsal have not been completed',
    ])
    return gaps


def verify_files(root, entries):
    root = Path(root).resolve(strict=True)
    for entry in entries:
        name = safe_member(entry['path'])
        path = (root / name).resolve(strict=True)
        path.relative_to(root)
        if not path.is_file() or sha256(path) != entry['sha256']:
            raise ValueError('Current evidence file changed: ' + name)


def database_signatures(path):
    path = Path(path).resolve(strict=True)  # Never create a database accidentally.
    result = {}
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Database integrity failure')
        for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            quoted = '"' + name.replace('"', '""') + '"'
            # Keep canonical row signatures, not raw patient values, in evidence.
            rows = sorted(json.dumps(list(row), ensure_ascii=False, separators=(',', ':'), default=str)
                          for row in db.execute('SELECT * FROM ' + quoted))
            result[name] = {'rows': len(rows), 'sha256': hashlib.sha256('\n'.join(rows).encode('utf-8')).hexdigest()}
        if db.execute("SELECT COUNT(*) FROM analysis_runs WHERE state IN ('queued','running')").fetchone()[0]:
            raise ValueError('Active analysis: defer handoff checks')
    return result


def verify_worker_locks(source_path, locks_root):
    source = read_json(source_path)
    locks_root = Path(locks_root)
    frozen = read_json(locks_root / 'validation.json')
    if frozen['status'] != 'passed' or frozen['source_sha256'] != sha256(source_path):
        raise ValueError('CPU dependency lock provenance mismatch')
    if frozen['conda_packages'] != source['conda_packages']:
        raise ValueError('CPU Conda lock differs from worker provenance')
    declared = {(p['metadata']['name'].lower(), p['metadata']['version'], p['download_info']['url'],
                 p['download_info']['archive_info']['hashes']['sha256'])
                for p in source['pypi_dependencies'] + source.get('supplemental_dependencies', [])}
    frozen_pip = {(p['name'].lower(), p['version'], p['url'], p['sha256']) for p in frozen['pip_packages']}
    if not declared or declared != frozen_pip or not frozen['conda_packages']:
        raise ValueError('CPU pip lock differs from worker provenance')
    wheel_path = Path(source['wheel']).resolve(strict=True)
    wheel = frozen['wheel']
    if wheel['sha256'] != source['wheel_sha256'] or sha256(wheel_path) != wheel['sha256'] or wheel_path.stat().st_size != wheel['bytes']:
        raise ValueError('CPU wheel differs from frozen dependency lock')
    expected = {
        'conda-explicit.txt': '@EXPLICIT\n' + '\n'.join(p['url'] + '#sha256:' + p['sha256'] for p in frozen['conda_packages']) + '\n',
        'pip-dependencies.txt': '\n'.join(p['name'] + ' @ ' + p['url'] + ' --hash=sha256:' + p['sha256'] for p in frozen['pip_packages']) + '\n',
        'pyradiomics-wheel.txt': 'pyradiomics @ ' + wheel_path.as_uri() + ' --hash=sha256:' + source['wheel_sha256'] + '\n',
    }
    files = []
    for name, text in expected.items():
        path = locks_root / name
        # Both LF/CRLF serialize the same frozen install statements. Preserve
        # actual original bytes and hash them; do not rewrite the user's lock.
        if path.read_text(encoding='utf-8') != text:
            raise ValueError('CPU lock text changed: ' + name)
        files.append({'path': str(path.resolve()), 'bytes': path.stat().st_size, 'sha256': sha256(path)})
    return {'status': 'passed', 'source_sha256': sha256(source_path), 'conda_packages': len(frozen['conda_packages']),
            'pip_dependencies': len(frozen['pip_packages']), 'files': files, 'no_install_or_network': True}


def check(args, output):
    project = args.project.resolve(strict=True)
    paths = load_runtime_config(args.runtime_config)
    before = database_signatures(paths['DATABASE_PATH'])
    for state in Path(paths['FEATURE_JOBS_DIR']).rglob('state.json'):
        if read_json(state).get('state') in {'queued', 'running'}:
            raise ValueError('Active feature task: defer handoff checks')
    current = scan(project)
    (output / 'current-source-audit.json').write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding='utf-8')
    if current['status'] != 'passed':
        raise ValueError('Current source audit rejected; inspect redacted findings')
    historical = read_json(args.source_candidate / 'audit.json')
    validation = read_json(args.source_candidate / 'validation.json')
    if historical['status'] != 'passed' or validation['status'] != 'passed':
        raise ValueError('Unaccepted historical source candidate')
    source_archive = verify_archive(args.source_candidate / 'brainfusion-source-candidate.zip',
                                    historical['files'], validation['archive_sha256'])
    changes = source_changes(historical['files'], current['files'])
    manifest = read_json(args.materials / 'engineering-materials-bundle/manifest.json')
    material_validation = read_json(args.materials / 'engineering-materials-validation.json')
    if manifest['status'] != 'passed' or material_validation['status'] != 'passed':
        raise ValueError('Unaccepted engineering materials')
    verify_files(args.materials / 'engineering-materials-bundle', manifest['files'])
    material_archive = verify_archive(args.materials / 'brainfusion-engineering-materials.zip', manifest['files'],
                                      material_validation['archive_sha256'], extra_entries=('manifest.json',))
    with zipfile.ZipFile(args.materials / 'brainfusion-engineering-materials.zip') as archive:
        if archive.read('manifest.json') != (args.materials / 'engineering-materials-bundle/manifest.json').read_bytes():
            raise ValueError('Archived material manifest changed')
    viewport = read_json(args.materials / 'engineering-materials-bundle/source-data/viewport-engineering-evidence.json')
    verify_files(project, viewport['implementation_sources'])
    tool_files = [dict(path='backend/tools/' + name, sha256=sha256(args.materials / 'engineering-materials-bundle/source' / name))
                  for name in ('capture_thesis_engineering_evidence.py', 'render_thesis_engineering_figures.py')]
    tool_files.append(dict(path='frontend/tools/capture_thesis_engineering_browser.mjs',
                          sha256=sha256(args.materials / 'engineering-materials-bundle/source/capture_thesis_engineering_browser.mjs')))
    verify_files(project, tool_files)
    source = read_json(Path(paths['RADIOMICS_PYTHON']).parent / 'source.json')
    worker_locks = verify_worker_locks(Path(paths['RADIOMICS_PYTHON']).parent / 'source.json', args.worker_locks)
    wheel_path = Path(source['wheel']).resolve(strict=True)
    wheel_path.relative_to(Path('E:/BrainFusion-Runtime').resolve())
    if sha256(wheel_path) != source['wheel_sha256']:
        raise ValueError('Preserved CPU worker wheel checksum mismatch')
    env = dict(os.environ, **{key: value for key, value in paths.items() if key != 'DATABASE_PATH'})
    env.update(DATABASE_URL='sqlite:///' + Path(paths['DATABASE_PATH']).as_posix(), PYTHONDONTWRITEBYTECODE='1')
    preflight = subprocess.run([sys.executable, '-B', str(project / 'backend/tools/preflight_runtime.py'), '--strict'],
                              cwd=project / 'backend', env=env, capture_output=True, text=True, encoding='utf-8', timeout=120)
    (output / 'preflight.stdout.json').write_text(preflight.stdout, encoding='utf-8')
    (output / 'preflight.stderr.log').write_text(preflight.stderr, encoding='utf-8')
    if preflight.returncode:
        raise ValueError('Existing-runtime preflight failed; inspect bounded logs')
    checked = json.loads(preflight.stdout)
    if checked['status'] != 'passed':
        raise ValueError('Runtime preflight did not pass')
    after = database_signatures(paths['DATABASE_PATH'])
    if before != after:
        raise ValueError('Database changed during handoff checks; no accepted snapshot')
    verify_files(project, current['files'])
    return {'status': 'passed_existing_workstation_only', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'scope': 'Read-only current source/archive/material compatibility, CPU wheel and existing runtime preflight. Not new-machine install, Docker, complete deployment or research acceptance.',
            'current_source': {'files': len(current['files']), 'bytes': current['total_bytes'], 'redacted_findings': current['findings']},
            'source_candidate': source_archive, 'source_candidate_vs_current': changes,
            'historical_candidate_is_not_current': not changes['is_current'],
            'engineering_materials': material_archive, 'material_implementation_matches': len(viewport['implementation_sources']),
            'material_reproduction_tools_match': len(tool_files), 'database_unchanged': True, 'database_table_signatures': before,
            'cpu_worker_wheel': {'path': str(wheel_path), 'bytes': wheel_path.stat().st_size, 'sha256': source['wheel_sha256'], 'provenance': 'Preserved locally built cp311 Windows wheel, not an upstream binary or Linux wheel'},
            'cpu_worker_dependency_locks': worker_locks,
            'runtime_config': {'path': str(args.runtime_config.resolve()), 'sha256': sha256(args.runtime_config), 'paths': paths},
            'preflight': checked, 'new_segmentation_extraction_or_app_migration': False,
            'delivery_gaps': delivery_gaps(changes['is_current']),
            'no_install_stop_restart_publish_or_data_copy': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=BACKEND.parent)
    parser.add_argument('--runtime-config', type=Path, required=True)
    parser.add_argument('--source-candidate', type=Path, required=True)
    parser.add_argument('--materials', type=Path, required=True)
    parser.add_argument('--worker-locks', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to(Path('E:/BrainFusion-Runtime/results/nightly').resolve())
    output.mkdir(exist_ok=False)
    try:
        result = check(args, output)
    except Exception as error:
        (output / 'failure.json').write_text(json.dumps({'status': 'failed', 'error': str(error)}, ensure_ascii=False, indent=2), encoding='utf-8')
        raise
    (output / 'validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('status', 'current_source', 'source_candidate_vs_current', 'database_unchanged', 'delivery_gaps')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
