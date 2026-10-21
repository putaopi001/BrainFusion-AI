"""Build an isolated Windows frontend with a verified official Node/lock profile.

Does not rewrite original locks, follow existing node_modules junctions, change
global PATH, start services or run dependency install scripts. Caches stay on E.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.bootstrap_cpu_delivery import digest, fresh, read, safe_member
from tools.prepare_source_delivery import scan


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def origin(url, host):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != host or parsed.username or parsed.password or parsed.port not in (None,443) or parsed.query or parsed.fragment:
        raise ValueError('Unapproved official distribution URL')
    return url


def sri_path(cache, integrity):
    algorithm, encoded = integrity.split('-', 1)
    if algorithm != 'sha512': raise ValueError('Frozen SHA512 SRI required')
    value = base64.b64decode(encoded, validate=True)
    if len(value) != 64: raise ValueError('Invalid SHA512 integrity')
    key = value.hex()
    return Path(cache)/'_cacache/content-v2/sha512'/key[:2]/key[2:4]/key[4:]


def sri_matches(path, integrity):
    if not Path(path).is_file(): return False
    with Path(path).open('rb') as handle:
        hashed = hashlib.sha512()
        for block in iter(lambda: handle.read(1024**2), b''): hashed.update(block)
        actual = hashed.digest()
    return base64.b64encode(actual).decode() == integrity.split('-',1)[1]


def verify_lock(original, derived, probe):
    if probe['status'] != 'official_source_mapping_checked_not_installed' or probe['matched_entries'] != 422:
        raise ValueError('Accepted official metadata preflight required')
    clone = json.loads(json.dumps(derived))
    records = {item['path']:item for item in probe['packages']}
    entries = {key:value for key,value in original['packages'].items() if value.get('resolved')}
    if set(records) != set(entries) or len(entries) != 422: raise ValueError('Incomplete fixed lock')
    for key,item in entries.items():
        record = records[key]
        target = derived['packages'][key]
        if not record['matched'] or record['version'] != item['version'] or record['name'] != item.get('name',key.rsplit('node_modules/',1)[1]) or record['sri'] != item['integrity'] or target['resolved'] != record['official_tarball_url']:
            raise ValueError('Fixed package identity/version/SRI changed')
        origin(target['resolved'],'registry.npmjs.org')
        sri_path(Path('E:/BrainFusion-Runtime/cache/npm'), item['integrity'])
        clone['packages'][key]['resolved'] = item['resolved']
    if clone != original: raise ValueError('Only derived resolved URL changes are allowed')
    return records


def download_node(item, cache):
    url = origin(item['url'],'nodejs.org')
    target = cache/PurePosixPath(urlparse(url).path).name
    if target.exists():
        if target.stat().st_size != item['archive_bytes'] or digest(target) != item['archive_sha256']:
            raise ValueError('Existing Node cache differs; preserve and investigate')
        return target, 'verified_existing_cache'
    partial = cache/(target.name+'.'+item['archive_sha256'][:12]+'.part')
    offset = partial.stat().st_size if partial.exists() else 0
    headers = {'User-Agent':'BrainFusion-delivery/1.0'}
    if offset: headers['Range'] = 'bytes='+str(offset)+'-'
    with urlopen(Request(url,headers=headers),timeout=60) as response:
        origin(response.url,'nodejs.org')
        resumed = offset and response.status == 206
        if resumed and not response.headers.get('Content-Range','').startswith('bytes '+str(offset)+'-'):
            raise ValueError('Node resume response mismatch')
        with partial.open('ab' if resumed else 'wb') as handle:
            while block := response.read(1024**2):
                handle.write(block)
                if handle.tell() > item['archive_bytes']: raise ValueError('Node exceeds frozen file budget')
    if partial.stat().st_size != item['archive_bytes'] or digest(partial) != item['archive_sha256']:
        raise ValueError('Node checksum mismatch; partial retained, no execution')
    partial.rename(target)
    return target, 'downloaded_official_verified_sha256'


def unpack_node(archive, prefix):
    with zipfile.ZipFile(archive) as source:
        infos = source.infolist()
        if len(infos) > 10000 or len({i.filename for i in infos}) != len(infos) or sum(i.file_size for i in infos) > 1024**3:
            raise ValueError('Node archive exceeds bounded profile')
        for item in infos:
            name = item.filename.rstrip('/') if item.is_dir() else item.filename
            safe_member(name)
            valid_root = name == 'node-v24.21.0-win-x64' and item.is_dir()
            if not (valid_root or name.startswith('node-v24.21.0-win-x64/')) or (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Node archive path/link rejected')
        prefix.mkdir(exist_ok=False)
        for item in infos:
            parts = PurePosixPath(item.filename).parts[1:]
            if not parts: continue
            target = prefix.joinpath(*parts)
            if item.is_dir(): target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with source.open(item) as handle, target.open('xb') as output: shutil.copyfileobj(handle,output)


def child(command, cwd, output, label, env):
    with (output/(label+'.log')).open('x',encoding='utf-8') as log:
        process = subprocess.Popen(command,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT)
        # Record native process creation time, not a guessed stale PID identity.
        started = subprocess.check_output(['powershell.exe','-NoProfile','-Command',f"(Get-Process -Id {process.pid}).StartTime.ToUniversalTime().ToString('o')"],text=True).strip()
        identity = dict(pid=process.pid,started_utc=started,command=command,cwd=str(cwd),state='running')
        save(output/(label+'-process.json'),identity)
        code = process.wait(timeout=600)
        save(output/(label+'-process.json'),dict(identity,state='completed',returncode=code,finished_utc=datetime.now(timezone.utc).isoformat()))
    if code: raise ValueError(label+' failed; retain evidence, do not retry npm ci into the same directory')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',type=Path,default=Path('E:/BrainFusion-AI'))
    parser.add_argument('--source-probe',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--node-prefix',type=Path,required=True)
    parser.add_argument('--api-base',required=True,help='Actual deployment API origin, e.g. http://127.0.0.1:8012; no assumed old port')
    args = parser.parse_args()
    api = urlparse(args.api_base)
    if api.scheme not in ('http','https') or not api.hostname or api.username or api.password or api.query or api.fragment or api.path not in ('','/'):
        raise ValueError('Explicit credential-free API origin required')
    project = args.project.resolve(strict=True)
    project.relative_to(Path('E:/').resolve())
    original_path = project/'frontend/package-lock.json'
    probe = read(args.source_probe/'validation.json')
    derived_path = args.source_probe/'package-lock-official-candidate.json'
    if digest(original_path) != probe['original_lock_sha256'] or digest(derived_path) != probe['derived_lock_sha256']:
        raise ValueError('Frozen original/derived lock hash changed')
    original,derived = read(original_path),read(derived_path)
    records = verify_lock(original,derived,probe)
    node = probe['node']
    if node['status'] != 'official_manifest_and_head_checked_not_downloaded' or node['version'] != '24.21.0' or node['archive_bytes'] != 37618919:
        raise ValueError('Frozen official Node profile required')
    output = fresh(args.output,'E:/BrainFusion-Runtime/results/nightly')
    prefix = fresh(args.node_prefix,'E:/BrainFusion-Runtime/envs')
    if not prefix.name.startswith('node24-delivery-'): raise ValueError('Fresh owned Node prefix required')
    audit = scan(project)
    if audit['status'] != 'passed': raise ValueError('Source audit rejected')
    output.mkdir(parents=True,exist_ok=False)
    save(output/'process.json',dict(pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),command=sys.argv,state='running'))
    cache = Path('E:/BrainFusion-Runtime/cache/npm')
    node_cache = Path('E:/BrainFusion-Runtime/cache/node24'); node_cache.mkdir(parents=True,exist_ok=True)
    existing_cache = {key:sri_matches(sri_path(cache,item['sri']),item['sri']) for key,item in records.items()}
    # Conservative planning bound from published unpacked sizes, not measured traffic.
    reserve = 2*1024**3
    free = shutil.disk_usage('E:/').free
    if free < reserve: raise ValueError('Insufficient E-drive planning reserve')
    save(output/'budget.json',dict(node_archive_bytes=node['archive_bytes'],all_422_unpacked_bytes=probe['estimated_package_unpacked_bytes'],planning_reserve_bytes=reserve,disk_free_bytes=free,known_sri_cache_entries=sum(existing_cache.values()),scope='2GiB conservative disk reserve, not exact transfer estimate. npm installs platform-applicable entries; actual cached tarball bytes recorded after installation.'))
    archive,method = download_node(node,node_cache)
    unpack_node(archive,prefix)
    python_sources = {item['path']:item for item in audit['files'] if item['path'].startswith('frontend/')}
    frontend = output/'frontend';frontend.mkdir()
    for name,item in python_sources.items():
        source = project/name
        if digest(source) != item['sha256']: raise ValueError('Frontend source changed during copy')
        target = output/name; target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    shutil.copyfile(derived_path,frontend/'package-lock.json')
    # Never npm ci through an existing directory/junction; only this fresh owned tree.
    if (frontend/'node_modules').exists() or (frontend/'node_modules').is_symlink(): raise ValueError('Fresh node_modules required')
    (output/'empty-user.npmrc').write_text('',encoding='utf-8')
    (output/'empty-global.npmrc').write_text('',encoding='utf-8')
    temporary = Path('E:/BrainFusion-Runtime/tmp/frontend-delivery');temporary.mkdir(parents=True,exist_ok=True)
    env = {key:value for key,value in os.environ.items() if not key.lower().startswith(('npm_config_','npm_token'))}
    env.update(PATH=str(prefix)+os.pathsep+env.get('PATH',''),TEMP=str(temporary),TMP=str(temporary),npm_config_cache=str(cache),npm_config_userconfig=str(output/'empty-user.npmrc'),npm_config_globalconfig=str(output/'empty-global.npmrc'),npm_config_registry='https://registry.npmjs.org',PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD='1',PLAYWRIGHT_BROWSERS_PATH='E:/BrainFusion-Runtime/cache/playwright',PYTHONDONTWRITEBYTECODE='1',VITE_API_BASE=args.api_base.rstrip('/'))
    exe = str(prefix/'node.exe'); npm = str(prefix/'node_modules/npm/bin/npm-cli.js')
    version = subprocess.check_output([exe,'--version'],env=env,text=True).strip()
    npm_version = subprocess.check_output([exe,npm,'--version'],env=env,text=True).strip()
    if version != 'v24.21.0': raise ValueError('Actual Node version mismatch')
    save(prefix/'delivery-source.json',dict(url=node['url'],archive_bytes=archive.stat().st_size,archive_sha256=digest(archive),method=method,node_version=version,npm_version=npm_version,license_sha256=digest(prefix/'LICENSE'),signature_verified=False,no_global_path_or_service_change=True))
    save(output/'source-audit.json',dict(frontend_files=list(python_sources.values()),original_lock_sha256=probe['original_lock_sha256'],derived_lock_sha256=probe['derived_lock_sha256']))
    child([exe,npm,'ci','--ignore-scripts','--no-audit','--no-fund','--prefer-offline'],frontend,output,'npm-ci',env)
    if digest(frontend/'package-lock.json') != probe['derived_lock_sha256']: raise ValueError('npm changed frozen candidate lock')
    installed = read(frontend/'node_modules/.package-lock.json')['packages']
    actual = []
    for key,item in installed.items():
        expected = derived['packages'][key]
        package = read(frontend/key/'package.json')
        record = records[key]
        if item['version'] != expected['version'] or item.get('integrity') != expected['integrity'] or item.get('resolved') != expected['resolved'] or package['name'] != record['name'] or package['version'] != record['version']:
            raise ValueError('Installed package identity/version/source differs')
        cached = sri_path(cache,record['sri'])
        if not sri_matches(cached,record['sri']): raise ValueError('Actual cached tarball SRI mismatch')
        actual.append(dict(path=key,name=package['name'],version=package['version'],official_source_url=record['official_tarball_url'],integrity=record['sri'],tarball_cache=str(cached),tarball_bytes=cached.stat().st_size,tarball_sha256=digest(cached),cache_was_already_verified=existing_cache[key],actual_historical_download_url='unknown; existing SRI-matching cache reused' if existing_cache[key] else 'official URL requested by frozen npm lock',license=record.get('license')))
    omitted = sorted(set(records)-set(installed))
    if any(not derived['packages'][key].get('optional') for key in omitted): raise ValueError('Required package omitted')
    save(output/'installed-distributions.json',dict(installed=actual,omitted_optional=omitted,scripts_disabled=True,all_cached_sri_match=True))
    child([exe,npm,'run','build','--ignore-scripts'],frontend,output,'frontend-build',env)
    if not (frontend/'dist/index.html').is_file(): raise ValueError('No actual build output')
    built = [dict(path=p.relative_to(frontend).as_posix(),bytes=p.stat().st_size,sha256=digest(p)) for p in sorted((frontend/'dist').rglob('*')) if p.is_file()]
    for name,item in python_sources.items():
        if digest(project/name) != item['sha256']: raise ValueError('Original frontend source changed')
        if name != 'frontend/package-lock.json' and digest(output/name) != item['sha256']: raise ValueError('Copied frontend source changed')
    result = dict(status='passed_isolated_frontend_install_and_build_not_browser_or_new_machine',created_utc=datetime.now(timezone.utc).isoformat(),api_base=args.api_base.rstrip('/'),node_prefix=str(prefix),node=read(prefix/'delivery-source.json'),frontend=str(frontend),source_files=len(python_sources),installed_distributions=len(actual),omitted_optional_entries=len(omitted),original_lock_unchanged=True,original_frontend_source_unchanged=True,candidate_lock_unchanged=True,all_installed_identity_version_source_and_tarball_sri_match=True,cache_reused_entries=sum(p['cache_was_already_verified'] for p in actual),actual_installed_tarball_file_bytes=sum(p['tarball_bytes'] for p in actual),build_files=built,no_install_scripts_global_path_service_model_data_or_research_change=True,scope='Same-workstation portable official Node and fresh source/derived-URL lock npm installation plus real build. Existing SRI cache origins remain unknown where reused. No frontend browser/deployment/new-machine or npm signature/security certification.')
    save(output/'validation.json',result)
    save(output/'process.json',dict(pid=os.getpid(),state='completed',finished_utc=result['created_utc'],command=sys.argv))
    print(json.dumps({key:result[key] for key in ('status','installed_distributions','omitted_optional_entries','cache_reused_entries','actual_installed_tarball_file_bytes','node_prefix','frontend')},ensure_ascii=False))


if __name__ == '__main__': main()
