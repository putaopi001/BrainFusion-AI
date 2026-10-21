"""Local operator only: add/replace a review account; never print a password/hash."""
import argparse
import getpass
import json
import os
from pathlib import Path
import secrets
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.local_auth import hash_password

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--username',required=True)
    parser.add_argument('--display-name',required=True)
    parser.add_argument('--role',choices=['doctor','researcher'],required=True)
    parser.add_argument('--password-file',type=Path)
    parser.add_argument('--replace',action='store_true')
    args=parser.parse_args()
    import re
    assert re.fullmatch(r'[A-Za-z0-9_.-]{3,64}',args.username),'Invalid username'
    assert 1<=len(args.display_name.strip())<=120,'Invalid display name'
    target=args.config.resolve()
    assert target.drive.upper()=='E:' and target.suffix=='.json','Use an E: JSON configuration'
    target.parent.mkdir(parents=True,exist_ok=True)
    if args.password_file:
        source=args.password_file.resolve(strict=True)
        assert source.drive.upper()=='E:' and source.stat().st_size<=1024,'Use a small E: private password file'
        password=source.read_text(encoding='utf-8-sig').rstrip('\r\n')
    else:
        password=getpass.getpass('New local password (12-128 chars): ')
        if password!=getpass.getpass('Repeat password: '):raise ValueError('Passwords differ')
    hashed=hash_password(password)
    # Atomic configuration replacement; the OS mutex serializes local operator updates.
    import msvcrt
    with target.with_suffix('.lock').open('a+b') as lock:
        if lock.tell()==0:lock.write(b'0');lock.flush()
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        try:
            data=json.loads(target.read_text(encoding='utf-8-sig')) if target.exists() else dict(format_version=1,users=[])
            assert data['format_version']==1
            old=next((u for u in data['users'] if u['username']==args.username),None)
            if old and not args.replace:raise ValueError('Existing account: use explicit --replace')
            user=dict(id=old['id'] if old else secrets.token_hex(16),username=args.username,
                display_name=args.display_name.strip(),role=args.role,disabled=False,password_hash=hashed)
            data['users']=[u for u in data['users'] if u['username']!=args.username]+[user]
            temp=target.with_name(target.name+'.'+secrets.token_hex(8)+'.tmp')
            try:
                with temp.open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
                os.replace(temp,target)
            finally:temp.unlink(missing_ok=True)
        finally:
            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
    print(json.dumps(dict(status='saved',username=args.username,role=args.role,scope='Local permission assignment, not medical credential verification')))

if __name__=='__main__':main()
