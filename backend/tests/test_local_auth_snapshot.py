"""Actual private account copy/login, tamper-before-write and maintenance exclusion."""
import json
import msvcrt
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.services import local_auth
from tools import snapshot_local_auth as snapshot
from tools import snapshot_pacs_joint as joint
from test_local_auth import account_config, PASSWORD

@pytest.fixture
def private_root(tmp_path,monkeypatch):
    root=tmp_path.parent/(tmp_path.name+'-private');root.mkdir()
    monkeypatch.setattr(joint,'PRIVATE_ROOT',root.resolve())
    return root

def test_account_roundtrip_login_without_restoring_session(account_config,private_root,monkeypatch):
    c=TestClient(app)
    assert c.post('/local-auth/login',json=dict(username='doctor-test',password=PASSWORD)).status_code==200
    token=c.cookies.get(local_auth.COOKIE)
    original=account_config.read_bytes()
    result=snapshot.backup(account_config,private_root/'snapshot')
    assert result['users']==2 and (private_root/'snapshot/local-users.json').read_bytes()==original
    manifest=json.loads((private_root/'snapshot/manifest.json').read_text(encoding='utf-8'))
    assert manifest['contains_plain_passwords'] is manifest['contains_active_sessions'] is False
    assert PASSWORD not in json.dumps(manifest)
    snapshot.restore(private_root/'snapshot',private_root/'restored')
    assert (private_root/'restored/local-users.json').read_bytes()==original
    paths=json.loads((private_root/'restored/runtime.json').read_text(encoding='utf-8'))['paths']
    monkeypatch.setattr(settings,'LOCAL_AUTH_FILE',paths['LOCAL_AUTH_FILE'])
    # Simulate a fresh single-process server: backups contain no live session.
    with local_auth._lock:local_auth._sessions.clear()
    # The browser already retains the scoped old cookie across a server restart.
    # Adding an unscoped duplicate is not a browser restart and can shadow login.
    assert c.cookies.get(local_auth.COOKIE)==token
    assert c.get('/local-auth/session').json()['data']['user'] is None
    assert c.post('/local-auth/login',json=dict(username='doctor-test',password=PASSWORD)).status_code==200
    assert c.get('/local-auth/session').json()['data']['user']['id']=='a'*32
    assert account_config.read_bytes()==original

def test_tampered_snapshot_refused_before_output_and_never_overwrites(account_config,private_root):
    snapshot.backup(account_config,private_root/'snapshot')
    with pytest.raises(FileExistsError):snapshot.backup(account_config,private_root/'snapshot')
    saved=private_root/'snapshot/local-users.json';saved.write_bytes(saved.read_bytes()+b' ')
    with pytest.raises(ValueError,match='checksum mismatch'):snapshot.restore(private_root/'snapshot',private_root/'restored')
    assert not (private_root/'restored').exists()

def test_operator_lock_excludes_backup(account_config,private_root):
    with account_config.with_suffix('.lock').open('a+b') as handle:
        handle.write(b'0');handle.flush();handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        try:
            with pytest.raises(ValueError,match='maintenance'):snapshot.backup(account_config,private_root/'snapshot')
            assert not (private_root/'snapshot').exists()
        finally:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)

def test_joint_legacy_compatibility_and_account_manifest_tampering(account_config,private_root):
    bundle=private_root/'bundle';bundle.mkdir()
    assert snapshot.check_joint_snapshot(bundle,dict(format_version=1)) is False
    snapshot.backup(account_config,bundle/'local-auth')
    value=dict(local_auth_included=True,local_auth_manifest_sha256=snapshot.sha256(bundle/'local-auth/manifest.json'))
    assert snapshot.check_joint_snapshot(bundle,value) is True
    (bundle/'local-auth/manifest.json').write_text('{}',encoding='utf-8')
    with pytest.raises(ValueError,match='manifest checksum'):snapshot.check_joint_snapshot(bundle,value)
