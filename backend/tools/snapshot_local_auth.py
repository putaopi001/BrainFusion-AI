"""Private local-account snapshot, supplementary to archive/application backup.

Only configuration and salted password hashes are copied. Active sessions and
initial plaintext password files are never backed up by this tool.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime,timezone
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools import snapshot_pacs_joint as joint
from tools.snapshot_database import sha256
from app.services.local_auth import accounts

@contextmanager
def configuration_lock(source):
    import msvcrt
    with source.with_suffix('.lock').open('a+b') as handle:
        if handle.tell()==0:handle.write(b'0');handle.flush()
        handle.seek(0)
        try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:raise ValueError('Local account maintenance is already active') from None
        try:yield
        finally:handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)

def backup(source,output):
    raw=Path(source)
    if raw.is_symlink():raise ValueError('Account configuration cannot be a symlink')
    source=raw.resolve(strict=True);output=joint.private_target(output)
    if source.drive.upper()!='E:' or output.is_relative_to(source.parent):
        raise ValueError('Use a separate E: private account backup directory')
    with configuration_lock(source):
        users,_=accounts(source)
        record=dict(source=str(source),relative='local-users.json',bytes=source.stat().st_size,sha256=sha256(source))
        output.parent.mkdir(parents=True,exist_ok=True);output.mkdir()
        joint.copy_verified([record],output)
        joint.write_new(output/'manifest.json',dict(format_version=1,status='passed',files=[record],users=len(users),
            created_utc=datetime.now(timezone.utc).isoformat(),contains_private_password_hashes=True,
            contains_plain_passwords=False,contains_active_sessions=False))
    return dict(status='passed',users=len(users),active_sessions_restored=False)

def validate_snapshot(snapshot):
    snapshot=Path(snapshot).resolve(strict=True)
    if not snapshot.is_relative_to(joint.PRIVATE_ROOT):raise ValueError('Account snapshot must stay in private backups')
    value=json.loads((snapshot/'manifest.json').read_text(encoding='utf-8'))
    if value.get('format_version')!=1 or value.get('status')!='passed' or len(value.get('files',[]))!=1:
        raise ValueError('Incomplete local account snapshot')
    record=value['files'][0];source=snapshot/'local-users.json'
    if record.get('relative')!='local-users.json' or source.is_symlink() or source.stat().st_size!=record['bytes'] or sha256(source)!=record['sha256']:
        raise ValueError('Local account snapshot checksum mismatch')
    users,_=accounts(source)
    if len(users)!=value['users']:raise ValueError('Local account count mismatch')
    return value

def check_joint_snapshot(snapshot,manifest):
    # Old joint bundles stay readable and do not invent missing accounts.
    if not manifest.get('local_auth_included',False):return False
    path=Path(snapshot)/'local-auth/manifest.json'
    if sha256(path)!=manifest.get('local_auth_manifest_sha256'):
        raise ValueError('Local account manifest checksum mismatch')
    validate_snapshot(Path(snapshot)/'local-auth')
    return True

def restore(snapshot,output):
    snapshot=Path(snapshot).resolve(strict=True);output=joint.private_target(output)
    if snapshot.is_relative_to(output) or output.is_relative_to(snapshot):raise ValueError('Use separate account snapshot and restore paths')
    value=validate_snapshot(snapshot)  # Fail before creating the output.
    output.parent.mkdir(parents=True,exist_ok=True);output.mkdir()
    joint.copy_verified(value['files'],output,snapshot)
    joint.write_new(output/'runtime.json',dict(format_version=1,paths=dict(LOCAL_AUTH_FILE=str(output/'local-users.json')),
        scope='Extra private process configuration; restart requires fresh login, never restored sessions'))
    return dict(status='passed',users=value['users'],active_sessions_restored=False)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--action',choices=['backup','restore'],required=True)
    parser.add_argument('--source',type=Path)
    parser.add_argument('--snapshot',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args()
    if a.action=='backup' and not a.source:parser.error('--source required')
    if a.action=='restore' and not a.snapshot:parser.error('--snapshot required')
    print(json.dumps(backup(a.source,a.output) if a.action=='backup' else restore(a.snapshot,a.output)))
if __name__=='__main__':main()
