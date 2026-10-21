import json
from pathlib import Path
from types import SimpleNamespace
import sqlite3
import pytest
from tools.snapshot_system import safe_target, restore
from tools.snapshot_database import sha256


def test_restore_rejects_path_escape(tmp_path):
    with pytest.raises(ValueError): safe_target(tmp_path, '../outside')
    with pytest.raises(ValueError): safe_target(tmp_path, '.')


def test_corrupt_snapshot_never_reports_restore_success(tmp_path):
    snapshot=tmp_path/'snapshot'; snapshot.mkdir()
    with sqlite3.connect(snapshot/'database.db') as db: db.execute('CREATE TABLE items (id integer)')
    (snapshot/'image.nii').write_bytes(b'owned invalid integrity fixture')
    manifest={'status':'passed','format_version':1,'total_bytes':64,
              'snapshot_database_sha256':sha256(snapshot/'database.db'),
              'files':[{'source':str(snapshot/'image.nii'),'relative':'image.nii','sha256':'0'*64}]}
    (snapshot/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    output=tmp_path/'restore'
    with pytest.raises(ValueError,match='checksum mismatch'):
        restore(SimpleNamespace(snapshot=snapshot,output=output))
    assert not (output/'runtime.json').exists()
    assert (snapshot/'image.nii').read_bytes()==b'owned invalid integrity fixture'


def test_existing_restore_target_is_not_overwritten(tmp_path):
    snapshot=tmp_path/'snapshot';snapshot.mkdir()
    (snapshot/'manifest.json').write_text(json.dumps({'status':'passed','format_version':1,'total_bytes':0}),encoding='utf-8')
    output=tmp_path/'restore';output.mkdir(); (output/'original.txt').write_text('keep',encoding='utf-8')
    with pytest.raises(FileExistsError): restore(SimpleNamespace(snapshot=snapshot,output=output))
    assert (output/'original.txt').read_text(encoding='utf-8')=='keep'


def test_restore_keeps_declared_empty_runtime_directories(tmp_path):
    snapshot=tmp_path/'snapshot';snapshot.mkdir()
    with sqlite3.connect(snapshot/'database.db') as db:db.execute('CREATE TABLE items (id integer)')
    roots=['uploads','feature_jobs','model','research','dataset']
    manifest=dict(status='passed',format_version=1,total_bytes=0,files=[],row_counts={'items':0},
        snapshot_database_sha256=sha256(snapshot/'database.db'),
        root_mapping=[dict(source=str(tmp_path/'original'/name),relative=name) for name in roots],
        external_radiomics_python='E:/external/python.exe',preexisting_unavailable=[])
    (snapshot/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
    before=(snapshot/'database.db').read_bytes();output=tmp_path/'restored'
    restore(SimpleNamespace(snapshot=snapshot,output=output))
    runtime=json.loads((output/'runtime.json').read_text(encoding='utf-8'))
    assert all((output/name).is_dir() and list((output/name).iterdir())==[] for name in roots)
    assert runtime['paths']['UPLOAD_DIR']=='uploads'
    assert (snapshot/'database.db').read_bytes()==before
