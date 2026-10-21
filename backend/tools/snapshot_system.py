"""Plan, checksum-backup and relocate local SQLite plus application artifacts.

No deletion, no execution of dataset content, no original database migration.
Use a stopped/idle application for a coherent file snapshot. Python environments
and application code are recorded external prerequisites, not portable binaries.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.core.config import settings
from tools.snapshot_database import sha256, counts

PATH_COLUMNS = {'filepath', 'mri_path', 'slice_path', 'processed_path', 'segmentation_path'}
JSON_COLUMNS = {'sequences_json', 'request_json', 'result_json'}


def normalized(value):
    path = Path(value)
    return path.resolve()


def json_paths(value):
    if isinstance(value, dict):
        for child in value.values(): yield from json_paths(child)
    elif isinstance(value, list):
        for child in value: yield from json_paths(child)
    elif isinstance(value, str) and Path(value).is_absolute():
        yield value


def safe_target(root, relative):
    target = (root / relative).resolve()
    target.relative_to(root)
    if target == root: raise ValueError('Artifact must be inside, not equal to target root')
    return target


def read_database(path):
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        active = db.execute("SELECT id FROM analysis_runs WHERE state IN ('queued','running')").fetchall()
        if active: raise ValueError('Active analysis exists; wait before backup')
        tables = {row[0]: list(db.execute('SELECT * FROM "' + row[0].replace('"','""') + '"'))
                  for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return tables, counts(db)


def inventory(args):
    source_db = args.source_db.resolve(strict=True)
    tables, row_counts = read_database(source_db)
    uploads = args.uploads.resolve(strict=True)
    roots = [(uploads, 'uploads'), (args.features.resolve(strict=True), 'feature_jobs'),
             (Path(settings.MODEL_DIR).resolve(strict=True), 'model'),
             (Path(settings.RESEARCH_DIR).resolve(strict=True), 'research'),
             (Path(settings.DATASET_DIR).resolve(strict=True), 'dataset')]
    files, missing = {}, []
    allowed = [BACKEND.resolve(), Path('E:/BrainFusion-Runtime').resolve(), Path('E:/BrainFusion-Data').resolve()]
    def add(path, relative):
        if path.is_symlink(): raise ValueError('Symlink artifacts are not copied: ' + str(path))
        path = path.resolve(strict=True)
        if path.is_symlink() or not any(path.is_relative_to(p) for p in allowed):
            raise ValueError('Artifact outside approved project/runtime/data scope: ' + str(path))
        files[str(path)] = relative.replace('\\', '/')
    for path, relative in roots:
        directory = path / 'downloads' if relative == 'dataset' else path
        for file in directory.rglob('*'):
            if file.is_file(): add(file, relative + '/' + file.relative_to(path).as_posix())
        if relative == 'dataset':
            for file in path.iterdir():
                if file.is_file() and file.suffix.lower() in {'.json', '.md', '.txt'}:
                    add(file, relative + '/' + file.name)
    for state in args.features.rglob('state.json'):
        if json.loads(state.read_text(encoding='utf-8'))['state'] in {'queued', 'running'}:
            raise ValueError('Active feature extraction exists; wait before backup')
    references = set()
    for rows in tables.values():
        for row in rows:
            for key in PATH_COLUMNS & set(row.keys()):
                if row[key]: references.add(row[key])
            for key in JSON_COLUMNS & set(row.keys()):
                if row[key]:
                    try: references.update(json_paths(json.loads(row[key])))
                    except ValueError: missing.append({'kind': 'invalid historical JSON', 'column': key, 'id': str(row['id'])})
    for value in sorted(references):
        path = Path(value)
        if not path.is_absolute():
            path = uploads / Path(*path.parts[1:]) if path.parts and path.parts[0] == 'uploads' else BACKEND / path
        path = path.resolve()
        if not path.exists():
            missing.append({'kind': 'pre-existing unavailable historical reference', 'source': str(path)})
            continue
        if any(path.is_relative_to(base) for base, _ in roots): continue
        tag = hashlib.sha256(str(path).encode()).hexdigest()[:16]
        base = 'uploads/imported/' + tag
        if path.is_dir():
            roots.append((path, base))
            for file in path.rglob('*'):
                if file.is_file(): add(file, base + '/' + file.relative_to(path).as_posix())
        else:
            add(path, base + '/' + path.name)
            # A referenced preview is one frame; include its sibling preview PNGs.
            if path.suffix.lower() == '.png':
                for sibling in path.parent.glob('*.png'): add(sibling, base + '/' + sibling.name)
    gate = Path(settings.RADIOMICS_COMPATIBILITY).resolve(strict=True)
    add(gate, 'contracts/compatibility.json')
    provenance = Path(settings.RADIOMICS_PYTHON).parent / 'source.json'
    add(provenance, 'environment/radiomics-source.json')
    return {'format_version': 1, 'source_database': str(source_db), 'row_counts': row_counts,
            'files': [{'source': path, 'relative': relative, 'bytes': Path(path).stat().st_size}
                      for path, relative in sorted(files.items())],
            'root_mapping': [{'source': str(path), 'relative': relative} for path, relative in roots],
            'preexisting_unavailable': missing, 'external_radiomics_python': settings.RADIOMICS_PYTHON,
            'scope': 'All local uploads/history plus referenced external assets, feature jobs, model provenance/weights, research artifacts, downloaded tables/metadata and reproduction gate. No raw cohort expansion or Python environment copy.'}


def backup(args):
    plan = inventory(args)
    output = args.output.resolve()
    if output.drive.upper() != 'E:': raise ValueError('Output must remain on E:')
    size = sum(item['bytes'] for item in plan['files'])
    if shutil.disk_usage(output.parent).free < size * 2 + 100 * 1024**2:
        raise ValueError('Insufficient free space for backup and restore')
    output.mkdir(exist_ok=False)
    db_target = output / 'database.db'
    with sqlite3.connect(Path(plan['source_database']).as_uri() + '?mode=ro', uri=True) as original:
        with sqlite3.connect(db_target) as saved:
            original.backup(saved)
            assert counts(saved) == plan['row_counts']
            assert saved.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    for item in plan['files']:
        source = Path(item['source']); target = safe_target(output, item['relative'])
        target.parent.mkdir(parents=True, exist_ok=True)
        before = sha256(source)
        shutil.copy2(source, target)
        if before != sha256(target) or before != sha256(source): raise ValueError('File changed during snapshot: ' + str(source))
        item['sha256'] = before
    assert read_database(args.source_db.resolve())[1] == plan['row_counts'], 'Database changed during backup'
    plan.update(status='passed', created_utc=datetime.now(timezone.utc).isoformat(), total_bytes=size,
                snapshot_database_sha256=sha256(db_target))
    (output / 'manifest.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': 'passed', 'files': len(plan['files']), 'bytes': size,
                      'preexisting_unavailable': plan['preexisting_unavailable'], 'manifest': str(output / 'manifest.json')}))


def restore(args):
    snapshot, output = args.snapshot.resolve(strict=True), args.output.resolve()
    if output.drive.upper() != 'E:': raise ValueError('Restore output must remain on E:')
    manifest = json.loads((snapshot / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['status'] == 'passed' and manifest['format_version'] == 1
    if shutil.disk_usage(output.parent).free < manifest['total_bytes'] + 100 * 1024**2: raise ValueError('Insufficient restore space')
    output.mkdir(exist_ok=False)
    assert sha256(snapshot / 'database.db') == manifest['snapshot_database_sha256']
    shutil.copy2(snapshot / 'database.db', output / 'database.db')
    exact = {}
    for item in manifest['files']:
        source, target = safe_target(snapshot, item['relative']), safe_target(output, item['relative'])
        if sha256(source) != item['sha256']: raise ValueError('Backup checksum mismatch: ' + item['relative'])
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, target)
        assert sha256(target) == item['sha256']
        exact[str(normalized(item['source'])).casefold()] = str(target)
    root_mapping = sorted(manifest['root_mapping'], key=lambda item: len(item['source']), reverse=True)
    # Declared empty roots are part of the runtime contract, not file inventory.
    for mapping in root_mapping:
        safe_target(output, mapping['relative']).mkdir(parents=True, exist_ok=True)
    old_uploads = Path(next(item['source'] for item in root_mapping if item['relative'] == 'uploads'))
    def relocate(value):
        if isinstance(value, dict): return {key: relocate(child) for key, child in value.items()}
        if isinstance(value, list): return [relocate(child) for child in value]
        if not isinstance(value, str): return value
        path = Path(value)
        if not path.is_absolute():
            if not path.parts or path.parts[0] != 'uploads': return value
            path = old_uploads / Path(*path.parts[1:])
        path = path.resolve()
        if str(path).casefold() in exact: return exact[str(path).casefold()]
        for mapping in root_mapping:
            try: relative = path.relative_to(Path(mapping['source']))
            except ValueError: continue
            return str(safe_target(output, mapping['relative'] + '/' + relative.as_posix()))
        return value  # Preserve already-unavailable historical provenance, explicitly in manifest.
    changes = 0
    with sqlite3.connect(output / 'database.db') as db:
        db.row_factory = sqlite3.Row
        tables = [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for table in tables:
            quoted = '"' + table.replace('"','""') + '"'
            for row in list(db.execute('SELECT * FROM ' + quoted)):
                updates = {}
                for key in PATH_COLUMNS & set(row.keys()):
                    if row[key]: updates[key] = relocate(row[key])
                for key in JSON_COLUMNS & set(row.keys()):
                    if row[key]:
                        try: updates[key] = json.dumps(relocate(json.loads(row[key])), ensure_ascii=False)
                        except ValueError: pass
                if table == 'mris' and row['filepath']:
                    new_path = Path(updates['filepath'])
                    if new_path.is_relative_to(output / 'uploads'):
                        updates['web_path'] = '/uploads/' + new_path.relative_to(output / 'uploads').as_posix()
                if updates:
                    fields = ','.join('"' + key + '"=?' for key in updates)
                    db.execute('UPDATE ' + quoted + ' SET ' + fields + ' WHERE id=?', [*updates.values(), row['id']]); changes += 1
        assert counts(db) == manifest['row_counts']
        db.commit(); assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    for state_file in (output / 'feature_jobs').rglob('state.json'):
        request_file = state_file.parent / 'request.json'
        request = relocate(json.loads(request_file.read_text(encoding='utf-8')))
        state = relocate(json.loads(state_file.read_text(encoding='utf-8')))
        state['cache_key'] = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        request_file.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding='utf-8')
        state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    config = {'format_version': 1, 'paths': {'DATABASE_PATH': 'database.db', 'UPLOAD_DIR': 'uploads', 'FEATURE_JOBS_DIR': 'feature_jobs',
              'MODEL_DIR': 'model', 'RESEARCH_DIR': 'research', 'DATASET_DIR': 'dataset',
              'RADIOMICS_COMPATIBILITY': 'contracts/compatibility.json', 'RADIOMICS_PYTHON': manifest['external_radiomics_python']},
              'scope': 'Restored application data/model/results; code and two installed Python environments remain external prerequisites.'}
    (output / 'runtime.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
    evidence = {'status': 'passed', 'snapshot': str(snapshot), 'restored': str(output),
                'files_verified_before_path_remap': len(manifest['files']), 'database_counts_equal': True,
                'row_paths_remapped': changes, 'preexisting_unavailable': manifest['preexisting_unavailable'],
                'feature_cache_keys_rebound_to_restored_paths': True, 'scope': config['scope']}
    (output / 'restore-validation.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(evidence, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--action', choices=['plan', 'backup', 'restore'], required=True)
    parser.add_argument('--source-db', type=Path)
    parser.add_argument('--uploads', type=Path, default=Path(settings.UPLOAD_DIR))
    parser.add_argument('--features', type=Path, default=Path(settings.FEATURE_JOBS_DIR))
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.action in {'plan','backup'} and not args.source_db: parser.error('--source-db is required')
    if args.action in {'backup','restore'} and not args.output: parser.error('--output is required')
    if args.action == 'restore' and not args.snapshot: parser.error('--snapshot is required')
    if args.action == 'plan':
        plan = inventory(args)
        print(json.dumps({'files': len(plan['files']), 'bytes': sum(item['bytes'] for item in plan['files']),
                          'preexisting_unavailable': plan['preexisting_unavailable'], 'row_counts': plan['row_counts'],
                          'scope': plan['scope']}, ensure_ascii=False, indent=2))
    elif args.action == 'backup': backup(args)
    else: restore(args)


if __name__ == '__main__': main()
