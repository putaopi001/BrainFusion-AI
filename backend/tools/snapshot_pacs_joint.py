"""Offline joint backup/restore of the local SQLite archive and application.

Run with the development mutex held and services stopped by their identity-aware
scripts. Backups include service credentials: keep them in the private Runtime
backups tree, never in source delivery or public evidence. No services are killed.
Python environments, application code and Orthanc binaries remain prerequisites.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from tools.snapshot_database import sha256

PRIVATE_ROOT = Path('E:/BrainFusion-Runtime/backups').resolve()


def private_target(path):
    path = Path(path).resolve()
    if not path.is_relative_to(PRIVATE_ROOT) or path == PRIVATE_ROOT:
        raise ValueError('Joint bundles must be inside the private Runtime backups tree')
    if path.exists():
        raise FileExistsError('Existing bundle is never overwritten')
    return path


def offline():
    # Check the whole machine, not only stale registry PIDs or a single port.
    command = "$ErrorActionPreference='Stop'; @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object { $_.Name -eq 'Orthanc.exe' -or ($_.Name -match '^python' -and $_.CommandLine -match 'uvicorn app.main:app') }).Count"
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                            check=True, capture_output=True, text=True)
    if result.stdout.strip() != '0':
        raise ValueError('Stop Orthanc and application backends before joint backup/restore')
    for port in (8042, 8012):
        for host in ('127.0.0.1', '::1'):
            try:
                connection = socket.create_connection((host, port), timeout=0.3)
            except OSError:
                continue
            connection.close()
            raise ValueError('Service port is still occupied; offline operation refused')


def entries(root, prefix, *, exclude=()):
    if root.lstat().st_file_attributes & 0x400:
        raise ValueError('Reparse archive root is not supported')
    root = root.resolve(strict=True)
    found = []
    for file in sorted(root.rglob('*')):
        if file.relative_to(root).as_posix() in exclude:
            continue
        # Reject Windows junctions/reparse points as well as ordinary symlinks.
        if file.lstat().st_file_attributes & 0x400:
            raise ValueError('Reparse points are not supported in archive storage')
        if file.is_file():
            found.append({'source': str(file), 'relative': prefix + '/' + file.relative_to(root).as_posix(),
                          'bytes': file.stat().st_size, 'sha256': sha256(file)})
    return found


def inside(root, relative):
    path = (root / relative).resolve()
    if path == root or not path.is_relative_to(root):
        raise ValueError('Bundle path escapes its root')
    return path


def copy_verified(records, output, snapshot=None):
    # Validate the complete inventory before copying anything or issuing success.
    destinations = [inside(output, record['relative']) for record in records]
    if len(set(destinations)) != len(destinations) or any(path.exists() for path in destinations):
        raise ValueError('Duplicate or existing bundle files are never overwritten')
    for record in records:
        source = inside(snapshot, record['relative']) if snapshot else Path(record['source'])
        inside(output, record['relative'])
        if source.is_symlink() or source.stat().st_size != record['bytes'] or sha256(source) != record['sha256']:
            raise ValueError('Archive/configuration checksum mismatch')
    for record in records:
        source = inside(snapshot, record['relative']) if snapshot else Path(record['source'])
        target = inside(output, record['relative'])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if sha256(target) != record['sha256'] or sha256(source) != record['sha256']:
            raise ValueError('Archive/configuration changed during copy')


def conversion_material_records(index_path):
    """Inventory the conversion index and its sibling artifact trees without following links."""
    index_path = Path(index_path).absolute()
    root = index_path.parent.resolve(strict=True)
    if root.drive.upper() != 'E:' or index_path.parent != root:
        raise ValueError('Conversion materials must be anchored in the E: Runtime directory')
    records = []
    if index_path.exists():
        if index_path.is_symlink() or index_path.resolve(strict=True) != index_path:
            raise ValueError('Conversion index must be a regular E: file')
        records.append({'source': str(index_path), 'relative': index_path.name,
                        'bytes': index_path.stat().st_size, 'sha256': sha256(index_path)})
    for name in ('dicom-conversion-plans', 'dicom-conversion-jobs', 'dicom-conversion-outputs'):
        folder = root / name
        if not folder.exists():
            continue
        if folder.is_symlink() or not folder.is_dir() or folder.resolve(strict=True) != folder:
            raise ValueError('Conversion artifact roots must be ordinary directories')
        for record in entries(folder, name):
            source = Path(record['source'])
            relative_inside = source.relative_to(folder).as_posix()
            if any((part.startswith('.') and 'prepare' in part.lower()) or part.endswith('.tmp') for part in Path(relative_inside).parts):
                raise ValueError('Incomplete conversion staging material prevents a consistent backup')
            if source.name.endswith('.lock'):
                continue
            records.append(record)
    included_files = {Path(record['source']).resolve() for record in records}
    for record in records:
        manifest_path = Path(record['source'])
        if manifest_path.name not in {'source-files.json', 'source_files.json'}:
            continue
        try:
            if manifest_path.stat().st_size > 1024 * 1024:
                raise ValueError()
            manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
            if not isinstance(manifest, dict):
                raise ValueError()
            for item in manifest.values():
                source = Path(item['path'])
                expected = item['sha256']
                if (not source.is_absolute() or source.resolve(strict=True) not in included_files
                        or not source.resolve(strict=True).is_relative_to(root)
                        or not isinstance(expected, str) or sha256(source) != expected):
                    raise ValueError()
        except Exception:
            raise ValueError('Conversion source manifest points outside the recoverable, verified materials') from None
    return records


def _rebase_value(value, old_root, new_root):
    if isinstance(value, dict):
        return {key: _rebase_value(item, old_root, new_root) for key, item in value.items()}
    if isinstance(value, list):
        return [_rebase_value(item, old_root, new_root) for item in value]
    if isinstance(value, str):
        candidate = Path(value)
        if candidate.is_absolute():
            try:
                resolved = candidate.resolve()
                relative = resolved.relative_to(old_root)
                return str(new_root / relative)
            except (OSError, ValueError):
                return value
    return value


def rebase_conversion_materials(index_file, old_root, new_root):
    """Relink restored JSON references before a restored runtime can consume them."""
    old_root, new_root = Path(old_root).resolve(), Path(new_root).resolve()
    index_file = Path(index_file)
    candidates = [index_file]
    for name in ('dicom-conversion-plans', 'dicom-conversion-jobs'):
        folder = new_root / name
        if folder.exists():
            candidates.extend(path for path in folder.rglob('*.json')
                              if path.name == 'job.json' or path.name in {'source-files.json', 'source_files.json'})
    rewritten_jobs = []
    for path in candidates:
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding='utf-8-sig'))
        except (UnicodeError, json.JSONDecodeError):
            continue
        value = _rebase_value(value, old_root, new_root)
        if path.name == 'job.json':
            inputs = value.get('inputs', {})
            source_record = inputs.get('source_files', {})
            source_path = Path(source_record.get('path', ''))
            if source_path.is_file():
                source_record['sha256'] = sha256(source_path)
            rewritten_jobs.append(path)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    # A job manifest may have been rewritten after its owning job.json was visited.
    for path in rewritten_jobs:
        value = json.loads(path.read_text(encoding='utf-8'))
        source_path = Path(value.get('inputs', {}).get('source_files', {}).get('path', ''))
        if source_path.is_file():
            value['inputs']['source_files']['sha256'] = sha256(source_path)
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def write_new(path, value):
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)


def write_unified_runtime_config(output, *, local_auth_included, import_state_included,
                                 conversion_index_included):
    from app.core.runtime_config import load_runtime_config, PATH_KEYS

    output = Path(output).resolve(strict=True)
    application_paths = load_runtime_config(output / 'application/runtime.json')
    paths = {}
    for key, raw in application_paths.items():
        resolved = Path(raw).resolve()
        try:
            paths[key] = resolved.relative_to(output).as_posix()
        except ValueError:
            paths[key] = str(resolved)
    paths.update({
        'PACS_CONFIG_FILE': 'pacs-config.json',
        'PACS_IMPORT_REGISTRY_FILE': 'import-state/registry.json',
        'PACS_IMPORT_JOBS_DIR': 'import-state/jobs',
        'LOCAL_AUTH_FILE': 'local-auth/local-users.json',
        'DICOM_CONVERSION_INDEX_FILE': 'dicom-conversions.json',
    })
    if set(paths) != PATH_KEYS:
        raise ValueError('Restored application runtime does not satisfy the supported v2 path contract')
    config = {'format_version': 2, 'paths': paths,
              'scope': 'Unified paths for restored application, local PACS, import receipts, review accounts and conversion index.'}
    runtime_path = output / 'runtime.json'
    write_new(runtime_path, config)
    resolved = load_runtime_config(runtime_path)
    if set(resolved) != PATH_KEYS:
        raise ValueError('Generated unified runtime config failed its own reader')
    pacs_file = output / 'pacs-config.json'
    account_file = output / 'local-auth/local-users.json'
    try:
        from app.services.pacs_client import PacsConfig
        PacsConfig.model_validate_json(pacs_file.read_text(encoding='utf-8-sig'))
        pacs_config_valid = True
    except Exception:
        pacs_config_valid = False
    try:
        from app.services.local_auth import accounts
        users, _ = accounts(account_file) if local_auth_included else ([], None)
        usable_account = any(not user['disabled'] for user in users)
    except Exception:
        usable_account = False
    components = {'pacs_config': pacs_config_valid, 'local_auth': usable_account,
                  'import_history': import_state_included,
                  'conversion_index': conversion_index_included and (output / 'dicom-conversions.json').is_file()}
    return {'runtime_config': 'runtime.json', 'format_version': 2, 'path_count': len(resolved),
            'runtime_config_readable': True,
            'runtime_config_ready_for_local_start': bool(pacs_config_valid and usable_account),
            'restored_components': components, 'live_restoration_verified': False}


def app_tool(arguments, runtime=None):
    env = os.environ.copy()
    if runtime:
        for key, value in runtime.items():
            env['DATABASE_URL' if key == 'DATABASE_PATH' else key] = (
                'sqlite:///' + value.replace('\\', '/') if key == 'DATABASE_PATH' else value)
    result = subprocess.run([sys.executable, '-B', str(BACKEND / 'tools/snapshot_system.py'), *arguments],
                            env=env, check=True, capture_output=True, text=True, encoding='utf-8')
    return json.loads(result.stdout)


def backup(args):
    from app.core.runtime_config import load_runtime_config
    from app.services.pacs_client import PacsConfig
    output = private_target(args.output)
    runtime = load_runtime_config(args.runtime_config)
    config = json.loads(args.orthanc_config.read_text(encoding='utf-8-sig'))
    try:
        pacs = PacsConfig.model_validate_json(args.pacs_config.read_text(encoding='utf-8-sig'))
    except Exception:
        raise ValueError('Invalid private PACS configuration; credential values omitted') from None
    if (config.get('HttpPort') != 8042 or config.get('RemoteAccessAllowed') is not False
            or config.get('AuthenticationEnabled') is not True or config.get('DicomServerEnabled') is not False
            or pacs.base_url != 'http://127.0.0.1:8042'
            or set(config) - {'Name', 'StorageDirectory', 'IndexDirectory', 'HttpServerEnabled', 'HttpPort',
                             'RemoteAccessAllowed', 'AuthenticationEnabled', 'RegisteredUsers', 'DicomServerEnabled',
                             'Plugins', 'DicomWeb'}):
        raise ValueError('Only the current local SQLite/DICOMweb profile is supported')
    if config.get('RegisteredUsers', {}).get(pacs.username) != pacs.password.get_secret_value():
        raise ValueError('Archive and backend service accounts differ; values omitted')
    if any(output.is_relative_to(Path(path).resolve()) for key, path in runtime.items()
           if key.endswith('_DIR')):
        raise ValueError('Backup cannot be nested in source application directories')
    expected_plugin = Path('E:/BrainFusion-Runtime/toolchains/orthanc-1.13.0-dicomweb-1.24/OrthancDicomWeb-1.24.dll').resolve()
    if [Path(p).resolve() for p in config.get('Plugins', [])] != [expected_plugin]:
        raise ValueError('Database/storage plugins are outside the supported backup profile')
    roots = [Path(config[key]).resolve(strict=True) for key in ('StorageDirectory', 'IndexDirectory')]
    for root in roots:
        if not root.is_relative_to(Path('E:/BrainFusion-Runtime').resolve()) or output.is_relative_to(root):
            raise ValueError('Archive roots must stay in Runtime and outside the output')
    if roots[0].is_relative_to(roots[1]) or roots[1].is_relative_to(roots[0]):
        raise ValueError('This profile requires separate archive index and storage roots')
    if not (roots[1] / 'index').is_file():
        raise ValueError('SQLite archive index is missing')
    offline()
    archive_records = entries(roots[0], 'orthanc/storage') + entries(roots[1], 'orthanc/index')
    records = list(archive_records)
    for source, relative in [(args.orthanc_config, 'orthanc/orthanc.json'), (args.pacs_config, 'pacs-config.json')]:
        records.append({'source': str(source.resolve(strict=True)), 'relative': relative,
                        'bytes': source.stat().st_size, 'sha256': sha256(source)})
    from app.core.config import settings
    conversion_index = Path(settings.DICOM_CONVERSION_INDEX_FILE).absolute()
    conversion_material_records_before = conversion_material_records(conversion_index)
    conversion_index_included = conversion_index.exists()
    conversion_materials_included = bool(conversion_material_records_before)
    for record in conversion_material_records_before:
        if Path(record['source']).name == conversion_index.name:
            record['relative'] = 'dicom-conversions.json'
        records.append(record)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    copy_verified(records, output)
    app = app_tool(['--action', 'backup', '--source-db', runtime['DATABASE_PATH'], '--output', str(output / 'application')], runtime)
    from app.core.config import settings
    import_state_included = Path(settings.PACS_IMPORT_REGISTRY_FILE).exists()
    if import_state_included:
        from tools.snapshot_pacs_import_state import backup as backup_import_state
        backup_import_state(output / 'import-state')
    auth_file = Path(getattr(args, 'local_auth_file', None) or settings.LOCAL_AUTH_FILE)
    local_auth_included = auth_file.exists()
    if local_auth_included:
        from tools.snapshot_local_auth import backup as backup_local_auth
        backup_local_auth(auth_file, output / 'local-auth')
    offline()
    # Exact original archive inventories and configuration bytes must still match.
    if archive_records != entries(roots[0], 'orthanc/storage') + entries(roots[1], 'orthanc/index'):
        raise ValueError('Archive inventory changed during joint backup')
    for record in records:
        if sha256(Path(record['source'])) != record['sha256']:
            raise ValueError('Original archive/configuration changed')
    conversion_material_records_after = conversion_material_records(conversion_index)
    normalized_before = sorted((Path(item['source']).name if item['relative'] == 'dicom-conversions.json' else item['relative'], item['bytes'], item['sha256']) for item in conversion_material_records_before)
    normalized_after = sorted((Path(item['source']).name if item['source'] == str(conversion_index) else item['relative'], item['bytes'], item['sha256']) for item in conversion_material_records_after)
    if normalized_before != normalized_after:
        raise ValueError('Conversion materials changed during joint backup')
    manifest = {'format_version': 1, 'status': 'passed', 'created_utc': datetime.now(timezone.utc).isoformat(),
                'archive_files': records, 'application_manifest_sha256': sha256(output / 'application/manifest.json'),
                'archive_id': pacs.archive_id, 'endpoint_fingerprint': pacs.endpoint_fingerprint,
                'contains_private_service_credentials': True, 'application_files': app['files'],
                'local_auth_included': local_auth_included,
                'local_auth_manifest_sha256': sha256(output / 'local-auth/manifest.json') if local_auth_included else None,
                'import_state_included': import_state_included,
                'import_state_manifest_sha256': sha256(output / 'import-state/manifest.json') if import_state_included else None,
                'conversion_index_included': conversion_index_included,
                'conversion_index_sha256': sha256(output / 'dicom-conversions.json') if conversion_index_included else None,
                'conversion_materials_included': conversion_materials_included,
                'conversion_materials_root': str(conversion_index.parent.resolve()),
                'conversion_materials_files': sum(1 for record in conversion_material_records_before if record['relative'] != conversion_index.name),
                'scope': 'Offline SQLite archive, application, PACS and conversion plans/source captures/jobs/outputs with checksums; binaries/environments external'}
    write_new(output / 'joint-manifest.json', manifest)
    return {'status': 'passed', 'archive_and_config_files': len(records), 'application_files': app['files']}


def restore(args):
    output = private_target(args.output)
    snapshot = args.snapshot.resolve(strict=True)
    if not snapshot.is_relative_to(PRIVATE_ROOT):
        raise ValueError('Snapshot must be in the private Runtime backups tree')
    if output.is_relative_to(snapshot) or snapshot.is_relative_to(output):
        raise ValueError('Snapshot and restore directories must be separate')
    manifest = json.loads((snapshot / 'joint-manifest.json').read_text(encoding='utf-8'))
    if manifest.get('status') != 'passed' or manifest.get('format_version') != 1:
        raise ValueError('Incomplete joint snapshot')
    if sha256(snapshot / 'application/manifest.json') != manifest['application_manifest_sha256']:
        raise ValueError('Application manifest checksum mismatch')
    if manifest.get('import_state_included') and sha256(snapshot / 'import-state/manifest.json') != manifest['import_state_manifest_sha256']:
        raise ValueError('Import state manifest checksum mismatch')
    from tools.snapshot_local_auth import check_joint_snapshot, restore as restore_local_auth
    local_auth_included = check_joint_snapshot(snapshot, manifest)
    offline()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()
    copy_verified(manifest['archive_files'], output, snapshot)
    if manifest.get('conversion_materials_included'):
        old_root = Path(manifest.get('conversion_materials_root', ''))
        if not old_root.is_absolute() or old_root.drive.upper() != 'E:':
            raise ValueError('Conversion materials source root is invalid')
        rebase_conversion_materials(output / 'dicom-conversions.json', old_root, output)
    app_tool(['--action', 'restore', '--snapshot', str(snapshot / 'application'), '--output', str(output / 'application')])
    if manifest.get('import_state_included'):
        from tools.snapshot_pacs_import_state import restore as restore_import_state
        restore_import_state(snapshot / 'import-state', output / 'import-state')
    if local_auth_included:
        restore_local_auth(snapshot / 'local-auth', output / 'local-auth')
    config_path = output / 'orthanc/orthanc.json'
    config = json.loads(config_path.read_text(encoding='utf-8-sig'))
    for key, relative in [('StorageDirectory', 'storage'), ('IndexDirectory', 'index')]:
        config[key] = (output / 'orthanc' / relative).as_posix()
    pacs_config = json.loads((output / 'pacs-config.json').read_text(encoding='utf-8-sig'))
    saved_identity = pacs_config.get('expected_database_server_identifier')
    identity_pin_applied = isinstance(saved_identity, str) and bool(saved_identity.strip())
    if identity_pin_applied:
        # A restored copy can run on a different host/port; preserve the pinned service identity.
        config['DatabaseServerIdentifier'] = saved_identity
    config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
    runtime_result = write_unified_runtime_config(output, local_auth_included=local_auth_included,
        import_state_included=bool(manifest.get('import_state_included')),
        conversion_index_included=bool(manifest.get('conversion_index_included')))
    runtime_result['restored_components']['conversion_materials'] = bool(manifest.get('conversion_materials_included'))
    runtime_result['conversion_material_files_verified'] = manifest.get('conversion_materials_files', 0)
    write_new(output / 'joint-restore.json', {'status': 'passed', 'snapshot': str(snapshot),
              'endpoint_fingerprint': manifest['endpoint_fingerprint'], 'archive_files_verified': len(manifest['archive_files']),
              'local_auth_included': local_auth_included, **runtime_result,
              'database_server_identity_pin_applied': identity_pin_applied,
              'scope': 'Offline file restoration verified; runtime paths are unified but services and actual DICOM/UID/case links remain unverified'})
    return {'status': 'passed', 'archive_files_verified': len(manifest['archive_files']),
            'runtime_config': runtime_result['runtime_config'],
            'runtime_config_ready_for_local_start': runtime_result['runtime_config_ready_for_local_start'],
            'live_restoration_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--action', choices=['backup', 'restore'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--runtime-config', type=Path)
    parser.add_argument('--orthanc-config', type=Path, default=Path('E:/BrainFusion-Runtime/orthanc-local/orthanc.json'))
    parser.add_argument('--local-auth-file', type=Path, help='Optional private account configuration; default LOCAL_AUTH_FILE')
    parser.add_argument('--pacs-config', type=Path, default=Path('E:/BrainFusion-Runtime/local/pacs-config.json'))
    args = parser.parse_args()
    if args.action == 'backup' and not args.runtime_config: parser.error('--runtime-config required')
    if args.action == 'restore' and not args.snapshot: parser.error('--snapshot required')
    print(json.dumps(backup(args) if args.action == 'backup' else restore(args)))


if __name__ == '__main__':
    main()
