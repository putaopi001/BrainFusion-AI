"""Verify/unpack a trusted source-lock bundle and rebuild a CPU env from E caches.

Standard library only: does not need the project's historical Python or pip.
Does not download, start services, execute dataset scripts or change defaults.
External trusted bundle SHA is required; hashes are integrity, not signatures.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from urllib.parse import urlparse, unquote
import zipfile


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''): value.update(block)
    return value.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def safe_member(name):
    value = PurePosixPath(name)
    if not name or '\\' in name or ':' in name or '..' in value.parts or value.is_absolute() or value.as_posix() != name:
        raise ValueError('Unsafe archive member')
    return name


def members(archive, entries, extras=()):
    expected = {}
    for item in entries:
        name = safe_member(item['path'])
        if name in expected or not 0 <= item['bytes'] <= 2*1024**2 or not re.fullmatch('[0-9a-f]{64}', item['sha256']):
            raise ValueError('Invalid manifest entry')
        expected[name] = item
    names = archive.namelist()
    if len(names) != len(set(names)) or set(names) != set(expected) | set(extras):
        raise ValueError('Archive member set mismatch')
    if sum(i.file_size for i in archive.infolist()) > 20*1024**2:
        raise ValueError('Archive too large')
    payload = {}
    for info in archive.infolist():
        safe_member(info.filename)
        if info.is_dir() or info.file_size > 2*1024**2 or (info.external_attr >> 16) & 0o170000 == 0o120000:
            raise ValueError('Directory, symlink or oversized archive member')
        raw = archive.read(info)
        if info.filename in expected:
            item = expected[info.filename]
            if len(raw) != item['bytes'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
                raise ValueError('Archive content checksum mismatch: ' + info.filename)
        payload[info.filename] = raw
    return payload


def verify_bundle(path, expected_sha):
    if not re.fullmatch('[0-9a-f]{64}', expected_sha) or digest(path) != expected_sha:
        raise ValueError('Trusted external bundle SHA mismatch')
    with zipfile.ZipFile(path) as archive:
        if archive.namelist().count('manifest.json') != 1 or archive.getinfo('manifest.json').file_size > 2*1024**2:
            raise ValueError('Bounded bundle manifest required')
        manifest = json.loads(archive.read('manifest.json'))
        if manifest.get('format_version') != 1:
            raise ValueError('Unsupported bundle format')
        payload = members(archive, manifest['files'], ('manifest.json',))
    required = {'bootstrap_cpu_delivery.py', 'brainfusion-source-candidate.zip', 'source-audit.json', 'cpu-source-lock.json', 'main-conda-explicit.txt'}
    if not required.issubset(payload): raise ValueError('Incomplete CPU source bundle')
    with zipfile.ZipFile(__import__('io').BytesIO(payload['brainfusion-source-candidate.zip'])) as archive:
        source = members(archive, json.loads(payload['source-audit.json'])['files'])
    # The standalone entry must be the same code present in the frozen project.
    if payload['bootstrap_cpu_delivery.py'] != source.get('backend/tools/bootstrap_cpu_delivery.py'):
        raise ValueError('Bootstrap entry differs from frozen project')
    lock = json.loads(payload['cpu-source-lock.json'])
    validate_lock(lock)
    expected = '@EXPLICIT\n'+'\n'.join(p['url']+'#sha256:'+p['sha256'] for p in lock['conda_bootstrap'])+'\n'
    if payload['main-conda-explicit.txt'].decode('utf-8').replace('\r\n','\n') != expected:
        raise ValueError('Conda lock disagrees with frozen source')
    return manifest, payload, source, lock


def validate_lock(lock):
    if lock.get('python') != '3.11.17' or lock.get('platform') != 'win_amd64':
        raise ValueError('Only the accepted Windows CP311 profile is supported')
    names, filenames = set(), set()
    for group, allowed in (('packages', {'files.pythonhosted.org', 'download.pytorch.org'}), ('conda_bootstrap', {'conda.anaconda.org'})):
        for item in lock[group]:
            parsed = urlparse(item['url'])
            filename = item.get('filename') or unquote(parsed.path).rsplit('/',1)[-1]
            size = item.get('bytes', item.get('size'))
            if parsed.scheme != 'https' or parsed.hostname not in allowed or parsed.username or parsed.password or parsed.port not in (None,443) or parsed.query or parsed.fragment:
                raise ValueError('Unapproved distribution origin')
            if group == 'conda_bootstrap' and not parsed.path.startswith('/conda-forge/'):
                raise ValueError('Unapproved Conda channel')
            if safe_member(filename) != filename or '/' in filename or filename != unquote(parsed.path).rsplit('/',1)[-1] or not 0 < size < 1024**3 or not re.fullmatch('[0-9a-f]{64}', item['sha256']):
                raise ValueError('Invalid distribution record')
            if group == 'packages':
                if not filename.endswith('.whl') or item['name'] in names or filename in filenames:
                    raise ValueError('Duplicate or non-wheel distribution')
                names.add(item['name']); filenames.add(filename)
    if len(names) != 52 or len(lock['conda_bootstrap']) != 20:
        raise ValueError('Accepted profile requires exactly 52 wheels and 20 interpreter packages')


def verify_cache(lock, wheel_cache, conda_cache):
    result = []
    for group, directory in (('packages',wheel_cache), ('conda_bootstrap',conda_cache)):
        for item in lock[group]:
            filename = item.get('filename') or unquote(urlparse(item['url']).path).rsplit('/',1)[-1]
            path = (Path(directory)/filename).resolve(strict=True)
            path.relative_to(Path(directory).resolve())
            if path.drive.upper() != 'E:' or not path.is_file() or path.stat().st_size != item.get('bytes',item.get('size')) or digest(path) != item['sha256']:
                raise ValueError('Missing/changed approved cache file; no installation')
            result.append(dict(group=group,name=item['name'],path=str(path),sha256=item['sha256']))
    return result


def fresh(path, root):
    path = Path(path).resolve(); path.relative_to(Path(root).resolve())
    if path == Path(root).resolve() or path.exists(): raise ValueError('Fresh owned directory required')
    return path


def record(path, value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def run(command, output, label, env):
    started = datetime.now(timezone.utc).isoformat()
    with (output/(label+'.log')).open('x',encoding='utf-8') as log:
        process = subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT)
        identity=dict(pid=process.pid,started_utc=started,command=command,state='running')
        record(output/(label+'-process.json'),identity)
        code=process.wait(timeout=300)
        record(output/(label+'-process.json'),dict(identity,state='completed',returncode=code,finished_utc=datetime.now(timezone.utc).isoformat()))
    if code: raise ValueError(label+' failed; evidence retained, do not repeat into same prefix')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--expected-bundle-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--install-prefix',type=Path)
    parser.add_argument('--conda-python',type=Path,default=Path('E:/Anaconda3/python.exe'))
    parser.add_argument('--wheel-cache',type=Path,default=Path('E:/BrainFusion-Runtime/cache/runtime311-cpu/wheels'))
    parser.add_argument('--conda-cache',type=Path,default=Path('E:/BrainFusion-Runtime/cache/conda'))
    args=parser.parse_args()
    # Verify everything before extracting or creating an environment.
    manifest,payload,source,lock=verify_bundle(args.bundle,args.expected_bundle_sha256)
    cache=verify_cache(lock,args.wheel_cache,args.conda_cache) if args.install_prefix else []
    output=fresh(args.output,'E:/BrainFusion-Runtime/results/nightly')
    prefix=None
    if args.install_prefix:
        prefix=fresh(args.install_prefix,'E:/BrainFusion-Runtime/envs')
        if not prefix.name.startswith('runtime311-cpu-delivery-'):
            raise ValueError('Fresh runtime311-cpu-delivery-* prefix required')
        conda=args.conda_python.resolve(strict=True)
        if conda.drive.upper()!='E:' or conda.name.lower()!='python.exe':raise ValueError('Existing trusted E-drive Conda interpreter required')
    output.mkdir(parents=True,exist_ok=False)
    record(output/'process.json',dict(pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),prefix=str(prefix) if prefix else None,command=sys.argv))
    for name,raw in payload.items():
        target=output/'bundle'/safe_member(name)
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    for name,raw in source.items():
        target=output/'project'/safe_member(name)
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    status='verified_and_unpacked_no_install'
    if prefix:
        temporary=Path('E:/BrainFusion-Runtime/tmp/cpu-delivery');temporary.mkdir(parents=True,exist_ok=True)
        env=dict(os.environ,TEMP=str(temporary),TMP=str(temporary),PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',CONDA_PKGS_DIRS=str(args.conda_cache.resolve()),CONDA_ENVS_PATH='E:/BrainFusion-Runtime/envs',CONDA_REGISTER_ENVS='false',CONDA_NUMBER_CHANNEL_NOTICES='0',PIP_CACHE_DIR='E:/BrainFusion-Runtime/cache/pip')
        local_conda=output/'local-conda-explicit.txt'
        local_conda.write_text('@EXPLICIT\n'+'\n'.join(Path(p['path']).as_uri()+'#sha256:'+p['sha256'] for p in cache if p['group']=='conda_bootstrap')+'\n',encoding='utf-8')
        run([str(conda),'-B','-m','conda','create','--offline','--no-default-packages','--no-shortcuts','-y','-p',str(prefix),'--file',str(local_conda)],output,'conda-create',env)
        wheel_lock=output/'local-wheel-hash-lock.txt'
        wheel_lock.write_text('\n'.join(p['name']+' @ '+Path(p['path']).as_uri()+' --hash=sha256:'+p['sha256'] for p in cache if p['group']=='packages')+'\n',encoding='utf-8')
        python=prefix/'python.exe'
        run([str(python),'-B','-m','pip','install','--force-reinstall','--no-index','--no-deps','--no-compile','--require-hashes','--report',str(output/'pip-install-report.json'),'-r',str(wheel_lock)],output,'pip-install',env)
        run([str(python),'-B','-m','pip','check'],output,'pip-check',env)
        inspected=subprocess.run([str(python),'-B','-c',"import sys,json,importlib.metadata as m;print(json.dumps(dict(python=sys.version.split()[0],packages={d.metadata['Name'].lower().replace('_','-'):d.version for d in m.distributions() if d.metadata.get('Name')})))"],env=env,capture_output=True,text=True,check=True,timeout=30)
        installed=json.loads(inspected.stdout)
        if installed['python']!=lock['python'] or installed['packages']!={p['name']:p['version'] for p in lock['packages']}:
            raise ValueError('Actual installed metadata differs from source lock')
        reports={p['metadata']['name'].lower().replace('_','-'):p for p in read(output/'pip-install-report.json')['install']}
        if set(reports)!=set(installed['packages']):raise ValueError('Pip source report incomplete')
        for item in lock['packages']:
            if reports[item['name']]['download_info']['archive_info']['hashes']['sha256']!=item['sha256']:
                raise ValueError('Installed wheel source mismatch')
        record(output/'installed-metadata.json',installed)
        record(prefix/'delivery-source.json',dict(bundle_sha256=args.expected_bundle_sha256,source_lock_sha256=digest(output/'bundle/cpu-source-lock.json'),bootstrap=lock['conda_bootstrap'],packages=lock['packages'],local_install_sources=cache,conda_executable=str(conda),no_service_or_default_switch=True))
        status='rebuilt_from_verified_local_caches_not_model_or_deployment_accepted'
    record(output/'validation.json',dict(status=status,bundle_sha256=args.expected_bundle_sha256,source_files=len(source),bundle_payload_files=len(manifest['files']),prefix=str(prefix) if prefix else None,verified_cache_files=len(cache),no_network_download=True,no_service_switch=True,scope='Source integrity/unpack and optional same-workstation CPU rebuild. Separate model/runtime/browser gates required; not new-machine, Linux, feature-worker setup or clinical/scientific acceptance.'))
    print(json.dumps(dict(status=status,source_files=len(source),cache_files=len(cache),prefix=str(prefix) if prefix else None)))


if __name__=='__main__':main()
