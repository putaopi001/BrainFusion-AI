import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.snapshot_pacs_joint import copy_verified, inside, private_target


def test_tampered_archive_refuses_entire_copy_before_any_file(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'one').write_bytes(b'original')
    (source / 'two').write_bytes(b'corrupt')
    records = [dict(relative=name, bytes=8, sha256=hashlib.sha256(b'original').hexdigest())
               for name in ('one', 'two')]
    output = tmp_path / 'copy'
    output.mkdir()
    with pytest.raises(ValueError, match='checksum mismatch'):
        copy_verified(records, output, source)
    assert list(output.iterdir()) == []
    assert (source / 'two').read_bytes() == b'corrupt'


def test_verified_copy_preserves_archive_bytes(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    raw = bytes(range(256)) * 3
    (source / 'instance').write_bytes(raw)
    output = tmp_path / 'copy'
    output.mkdir()
    copy_verified([dict(relative='instance', bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())], output, source)
    assert (source / 'instance').read_bytes() == (output / 'instance').read_bytes() == raw


@pytest.mark.parametrize('relative', ['../escape', '.', 'E:/outside-bundle'])
def test_restore_record_cannot_escape_bundle(tmp_path, relative):
    with pytest.raises(ValueError, match='escapes'):
        inside(tmp_path.resolve(), relative)


def test_existing_private_target_is_never_overwritten(tmp_path, monkeypatch):
    monkeypatch.setattr('tools.snapshot_pacs_joint.PRIVATE_ROOT', tmp_path.resolve())
    bundle = tmp_path / 'existing'
    bundle.mkdir()
    (bundle / 'keep').write_bytes(b'user-owned')
    with pytest.raises(FileExistsError):
        private_target(bundle)
    assert (bundle / 'keep').read_bytes() == b'user-owned'


def test_private_credentials_bundle_cannot_target_source_or_evidence(tmp_path):
    with pytest.raises(ValueError, match='private Runtime'):
        private_target(tmp_path / 'public-evidence')


def test_duplicate_archive_paths_and_existing_files_are_never_overwritten(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'index').write_bytes(b'new')
    output = tmp_path / 'copy'
    output.mkdir()
    record = dict(relative='index', bytes=3, sha256=hashlib.sha256(b'new').hexdigest())
    with pytest.raises(ValueError, match='never overwritten'):
        copy_verified([record, record], output, source)
    (output / 'index').write_bytes(b'keep')
    with pytest.raises(ValueError, match='never overwritten'):
        copy_verified([record], output, source)
    assert (output / 'index').read_bytes() == b'keep'


def test_joint_restore_refuses_tampered_import_manifest_before_creating_target(tmp_path,monkeypatch):
    from tools import snapshot_pacs_joint as joint
    monkeypatch.setattr(joint,'PRIVATE_ROOT',tmp_path.resolve())
    snapshot=tmp_path/'snapshot'
    (snapshot/'application').mkdir(parents=True)
    (snapshot/'application/manifest.json').write_bytes(b'{}')
    (snapshot/'import-state').mkdir()
    (snapshot/'import-state/manifest.json').write_bytes(b'{"changed":true}')
    (snapshot/'joint-manifest.json').write_text(json.dumps(dict(format_version=1,status='passed',
        application_manifest_sha256=hashlib.sha256(b'{}').hexdigest(),import_state_included=True,
        import_state_manifest_sha256='0'*64)),encoding='utf-8')
    output=tmp_path/'restored'
    with pytest.raises(ValueError,match='Import state manifest checksum mismatch'):
        joint.restore(SimpleNamespace(snapshot=snapshot,output=output))
    assert not output.exists()

def test_joint_restore_emits_unified_v2_runtime_for_all_thirteen_paths(tmp_path):
    from tools.snapshot_pacs_joint import write_unified_runtime_config
    from app.core.runtime_config import load_runtime_config, PATH_KEYS

    output = tmp_path / 'restored'
    application = output / 'application'
    application.mkdir(parents=True)
    (application / 'runtime.json').write_text(json.dumps({'format_version': 1, 'paths': {
        'DATABASE_PATH': 'database.db', 'UPLOAD_DIR': 'uploads', 'FEATURE_JOBS_DIR': 'feature_jobs',
        'MODEL_DIR': 'model', 'RESEARCH_DIR': 'research', 'DATASET_DIR': 'dataset',
        'RADIOMICS_COMPATIBILITY': 'contracts/compatibility.json',
        'RADIOMICS_PYTHON': 'E:/BrainFusion-Runtime/envs/radiomics39/python.exe'}}), encoding='utf-8')
    (output / 'pacs-config.json').write_text(json.dumps({'format_version':1,'archive_id':'synthetic',
        'base_url':'http://127.0.0.1:8042','username':'test-user','password':'synthetic-test-only'}),encoding='utf-8')
    (output / 'local-auth').mkdir()
    (output / 'local-auth/local-users.json').write_text(json.dumps({'format_version':1,'users':[{
        'id':'a'*32,'username':'test-user','role':'researcher','display_name':'Synthetic User','disabled':False,
        'password_hash':'pbkdf2_sha256$600000$'+'0'*32+'$'+'0'*64}]}),encoding='utf-8')
    (output / 'import-state/jobs').mkdir(parents=True)
    (output / 'dicom-conversions.json').write_text('{"format":"dicom-conversion-index-v1","entries":[]}', encoding='utf-8')

    result = write_unified_runtime_config(output, local_auth_included=True,
        import_state_included=True, conversion_index_included=True)
    config_path = output / 'runtime.json'
    value = json.loads(config_path.read_text(encoding='utf-8'))
    resolved = load_runtime_config(config_path)
    assert value['format_version'] == 2 and set(value['paths']) == PATH_KEYS
    assert len(resolved) == 13 and all(Path(item).drive.upper() == 'E:' for item in resolved.values())
    assert resolved['DATABASE_PATH'] == str((application / 'database.db').resolve())
    assert resolved['PACS_CONFIG_FILE'] == str((output / 'pacs-config.json').resolve())
    assert resolved['LOCAL_AUTH_FILE'] == str((output / 'local-auth/local-users.json').resolve())
    assert result['runtime_config_ready_for_local_start'] is True
    assert result['live_restoration_verified'] is False


def test_joint_restore_config_reports_missing_private_account_without_claiming_ready(tmp_path):
    from tools.snapshot_pacs_joint import write_unified_runtime_config
    output = tmp_path / 'restored'
    application = output / 'application'
    application.mkdir(parents=True)
    (application / 'runtime.json').write_text(json.dumps({'format_version': 1, 'paths': {
        'DATABASE_PATH': 'database.db', 'UPLOAD_DIR': 'uploads', 'FEATURE_JOBS_DIR': 'feature_jobs',
        'MODEL_DIR': 'model', 'RESEARCH_DIR': 'research', 'DATASET_DIR': 'dataset',
        'RADIOMICS_COMPATIBILITY': 'contracts/compatibility.json',
        'RADIOMICS_PYTHON': 'E:/BrainFusion-Runtime/envs/radiomics39/python.exe'}}), encoding='utf-8')
    (output / 'pacs-config.json').write_text('{}', encoding='utf-8')

    result = write_unified_runtime_config(output, local_auth_included=False,
        import_state_included=False, conversion_index_included=False)
    assert result['runtime_config_readable'] is True
    assert result['runtime_config_ready_for_local_start'] is False
    assert result['restored_components']['local_auth'] is False
    assert result['live_restoration_verified'] is False



def test_joint_restore_function_writes_unified_config_for_legacy_bundle(tmp_path, monkeypatch):
    from tools import snapshot_pacs_joint as joint
    from app.core.runtime_config import load_runtime_config, PATH_KEYS

    private = tmp_path.resolve()
    monkeypatch.setattr(joint, 'PRIVATE_ROOT', private)
    monkeypatch.setattr(joint, 'offline', lambda: None)
    snapshot = private / 'legacy-snapshot'
    (snapshot / 'application').mkdir(parents=True)
    app_manifest = b'{"format_version":1,"status":"passed"}'
    (snapshot / 'application/manifest.json').write_bytes(app_manifest)
    archive = snapshot / 'orthanc'
    archive.mkdir()
    pacs_config = snapshot / 'pacs-config.json'
    config_path = archive / 'orthanc.json'
    config_path.write_text(json.dumps({'StorageDirectory':'old-storage','IndexDirectory':'old-index'}), encoding='utf-8')
    pacs_config.write_text(json.dumps({'expected_database_server_identifier':'SYNTHETIC-SAVED-PIN'}), encoding='utf-8')
    records=[]
    for source, relative in ((config_path,'orthanc/orthanc.json'),(pacs_config,'pacs-config.json')):
        raw=source.read_bytes()
        records.append({'relative':relative,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    (snapshot / 'joint-manifest.json').write_text(json.dumps({
        'format_version':1,'status':'passed','application_manifest_sha256':hashlib.sha256(app_manifest).hexdigest(),
        'archive_files':records,'endpoint_fingerprint':'synthetic-fingerprint','local_auth_included':False,
        'import_state_included':False}), encoding='utf-8')

    def restore_application(arguments, runtime=None):
        restored=Path(arguments[arguments.index('--output')+1])
        restored.mkdir(parents=True)
        (restored / 'runtime.json').write_text(json.dumps({'format_version':1,'paths':{
            'DATABASE_PATH':'database.db','UPLOAD_DIR':'uploads','FEATURE_JOBS_DIR':'feature_jobs',
            'MODEL_DIR':'model','RESEARCH_DIR':'research','DATASET_DIR':'dataset',
            'RADIOMICS_COMPATIBILITY':'contracts/compatibility.json',
            'RADIOMICS_PYTHON':'E:/BrainFusion-Runtime/envs/radiomics39/python.exe'}}),encoding='utf-8')
        return {'status':'passed'}
    monkeypatch.setattr(joint, 'app_tool', restore_application)
    output=private/'restored'
    result=joint.restore(SimpleNamespace(snapshot=snapshot,output=output))
    resolved=load_runtime_config(output/'runtime.json')
    restore_report=json.loads((output/'joint-restore.json').read_text(encoding='utf-8'))
    restored_orthanc=json.loads((output/'orthanc/orthanc.json').read_text(encoding='utf-8'))
    assert result['runtime_config']=='runtime.json' and result['runtime_config_ready_for_local_start'] is False
    assert set(resolved)==PATH_KEYS and len(resolved)==13
    assert resolved['DATABASE_PATH']==str((output/'application/database.db').resolve())
    assert resolved['PACS_CONFIG_FILE']==str((output/'pacs-config.json').resolve())
    assert restore_report['restored_components']['local_auth'] is False
    assert restore_report['live_restoration_verified'] is False
    assert restore_report['database_server_identity_pin_applied'] is True
    assert restored_orthanc['DatabaseServerIdentifier']=='SYNTHETIC-SAVED-PIN'


def test_conversion_material_inventory_covers_plan_capture_job_and_output(tmp_path):
    from tools.snapshot_pacs_joint import conversion_material_records
    local = tmp_path / 'local'
    local.mkdir()
    index = local / 'dicom-conversions.json'
    index.write_text('{"format":"dicom-conversion-index-v1","entries":[]}', encoding='utf-8')
    plan = local / 'dicom-conversion-plans' / 'draft-a'
    capture = plan / 'capture-a'
    capture.mkdir(parents=True)
    (plan / 'proposal.json').write_text('{}', encoding='utf-8')
    (capture / 'p00001.dcm').write_bytes(b'synthetic-dicom-bytes')
    (capture / 'source-files.json').write_text('{}', encoding='utf-8')
    job = local / 'dicom-conversion-jobs' / ('a' * 32)
    (job / 'inputs').mkdir(parents=True)
    (job / 'job.json').write_text('{}', encoding='utf-8')
    output = local / 'dicom-conversion-outputs' / 'web-a'
    output.mkdir(parents=True)
    (output / 'conversion-report.json').write_text('{}', encoding='utf-8')

    records = conversion_material_records(index)
    relatives = {record['relative'] for record in records}
    assert 'dicom-conversions.json' in relatives
    assert 'dicom-conversion-plans/draft-a/capture-a/p00001.dcm' in relatives
    assert 'dicom-conversion-jobs/' + 'a' * 32 + '/job.json' in relatives
    assert 'dicom-conversion-outputs/web-a/conversion-report.json' in relatives


def test_conversion_recovery_rebases_paths_and_refreshes_source_manifest_hash(tmp_path):
    from tools.snapshot_pacs_joint import rebase_conversion_materials, sha256
    old_root = tmp_path / 'old' / 'local'
    new_root = tmp_path / 'restored'
    jobs = old_root / 'dicom-conversion-jobs' / ('b' * 32)
    inputs = jobs / 'inputs'
    capture = old_root / 'dicom-conversion-plans' / 'draft-b' / 'capture-b'
    output = old_root / 'dicom-conversion-outputs' / 'web-b'
    inputs.mkdir(parents=True)
    capture.mkdir(parents=True)
    output.mkdir(parents=True)
    (capture / 'p00001.dcm').write_bytes(b'synthetic-original')
    capture_manifest = capture / 'source-files.json'
    capture_manifest.write_text(json.dumps({'synthetic-instance': {
        'path': str(capture / 'p00001.dcm'), 'sha256': sha256(capture / 'p00001.dcm')}}), encoding='utf-8')
    job_source_manifest = inputs / 'source_files.json'
    job_source_manifest.write_text(json.dumps({'synthetic-instance': {
        'path': str(capture / 'p00001.dcm'), 'sha256': sha256(capture / 'p00001.dcm')}}), encoding='utf-8')
    for name in ('proposal', 'snapshots'):
        (inputs / (name + '.json')).write_text('{}', encoding='utf-8')
    row = {'format': 'dicom-conversion-job-v1', 'inputs': {
        'proposal': {'path': str(inputs / 'proposal.json'), 'sha256': sha256(inputs / 'proposal.json')},
        'snapshots': {'path': str(inputs / 'snapshots.json'), 'sha256': sha256(inputs / 'snapshots.json')},
        'source_files': {'path': str(job_source_manifest), 'sha256': sha256(job_source_manifest)}},
        'output_base': str(output), 'output_dir': None}
    (jobs / 'job.json').write_text(json.dumps(row), encoding='utf-8')
    index = old_root / 'dicom-conversions.json'
    index.write_text(json.dumps({'format':'dicom-conversion-index-v1','entries':[{
        'version_dir':str(output), 'proposal_path':str(inputs / 'proposal.json'),
        'snapshots_path':str(inputs / 'snapshots.json')}]}), encoding='utf-8')

    import shutil
    shutil.copytree(old_root, new_root)
    restored_capture_manifest = new_root / 'dicom-conversion-plans' / 'draft-b' / 'capture-b' / 'source-files.json'
    restored_job_manifest = new_root / 'dicom-conversion-jobs' / ('b' * 32) / 'inputs' / 'source_files.json'
    restored_job_file = new_root / 'dicom-conversion-jobs' / ('b' * 32) / 'job.json'
    rebase_conversion_materials(new_root / 'dicom-conversions.json', old_root, new_root)

    expected_dicom = str(new_root / 'dicom-conversion-plans' / 'draft-b' / 'capture-b' / 'p00001.dcm')
    assert json.loads(restored_capture_manifest.read_text())['synthetic-instance']['path'] == expected_dicom
    assert json.loads(restored_job_manifest.read_text())['synthetic-instance']['path'] == expected_dicom
    restored_job = json.loads(restored_job_file.read_text())
    assert restored_job['inputs']['source_files']['sha256'] == sha256(restored_job_manifest)
    restored_index = json.loads((new_root / 'dicom-conversions.json').read_text())['entries'][0]
    assert restored_index['version_dir'] == str(new_root / 'dicom-conversion-outputs' / 'web-b')
    assert str(old_root) not in restored_job_file.read_text()


def test_conversion_inventory_refuses_incomplete_staging_directory(tmp_path):
    from tools.snapshot_pacs_joint import conversion_material_records
    local = tmp_path / 'local'
    (local / 'dicom-conversion-plans' / '.prepare-partial').mkdir(parents=True)
    (local / 'dicom-conversion-plans' / '.prepare-partial' / 'draft.json').write_text('{}')
    with pytest.raises(ValueError, match='Incomplete conversion staging'):
        conversion_material_records(local / 'dicom-conversions.json')


def test_conversion_inventory_refuses_source_manifest_outside_recovery_roots(tmp_path):
    from tools.snapshot_pacs_joint import conversion_material_records
    local = tmp_path / 'local'
    capture = local / 'dicom-conversion-plans' / 'draft-x' / 'capture-x'
    capture.mkdir(parents=True)
    external = tmp_path / 'external-original.dcm'
    external.write_bytes(b'not-in-conversion-root')
    (capture / 'source-files.json').write_text(json.dumps({'synthetic-instance': {
        'path': str(external), 'sha256': hashlib.sha256(external.read_bytes()).hexdigest()}}), encoding='utf-8')
    with pytest.raises(ValueError, match='outside the recoverable'):
        conversion_material_records(local / 'dicom-conversions.json')
