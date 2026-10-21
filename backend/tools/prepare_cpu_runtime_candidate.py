"""Freeze/download/install a separate supported CPU main runtime, never switch services.

Reuse historical observed versions as constraints, not original-install provenance.
All wheels come from official PyPI or exact already-verified PyTorch CPU sources.
Each phase writes fresh evidence; downloads resume and verified cache is reused.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.parse import urlparse, unquote
from urllib.request import Request, urlopen
from packaging.tags import cpython_tags, compatible_tags
from packaging.utils import parse_wheel_filename
from packaging.specifiers import SpecifierSet

CACHE = Path('E:/BrainFusion-Runtime/cache/runtime311-cpu/wheels')
SKIP = {'torchaudio'}  # Unused by this MRI/web/research application, not a GPU replacement.


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''): value.update(block)
    return value.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def validate_distribution(item):
    parsed = urlparse(item['url'])
    if parsed.scheme != 'https' or parsed.hostname not in {'files.pythonhosted.org', 'download.pytorch.org'} or parsed.username or parsed.password:
        raise ValueError('Distribution must use the verified official HTTPS origin')
    filename = item['filename']
    if Path(filename).name != filename or '/' in filename or '\\' in filename or not filename.endswith('.whl'):
        raise ValueError('Unsafe wheel filename')
    if unquote(parsed.path).split('/')[-1] != filename:
        raise ValueError('Wheel URL filename mismatch')
    if len(item['sha256']) != 64 or any(c not in '0123456789abcdef' for c in item['sha256']) or not 0 < item['bytes'] < 1024**3:
        raise ValueError('Invalid distribution checksum/size')


def select_wheel(metadata):
    if not SpecifierSet(metadata['info'].get('requires_python') or '').contains('3.11.17'):
        raise ValueError('Declared Python excludes candidate version')
    ordered = list(cpython_tags((3, 11), platforms=['win_amd64'])) + list(compatible_tags((3, 11), interpreter='cp311', platforms=['win_amd64']))
    ranks = {tag: i for i, tag in reversed(list(enumerate(ordered)))}
    candidates = []
    for item in metadata['urls']:
        if item['packagetype'] != 'bdist_wheel' or item.get('yanked'): continue
        tags = parse_wheel_filename(item['filename'])[3]
        compatible = set(tags) & ranks.keys()
        if compatible: candidates.append((min(ranks[t] for t in compatible), item['filename'], item))
    if not candidates: raise ValueError('No compatible CPython3.11 Windows wheel')
    return min(candidates)[2]


def plan(args, output):
    inventory = read(args.inventory)['installed_packages']
    probe = read(args.source_probe)
    if probe['status'] != 'source_availability_checked' or not probe['budget_complete']:
        raise ValueError('Accepted CPU source probe required')
    records = {item['name']: item for item in probe['records']}
    source = read(args.worker_source)
    locks = read(args.conda_lock.parent / 'validation.json')
    if locks['source_sha256'] != digest(args.worker_source) or locks['conda_packages'] != source['conda_packages']:
        raise ValueError('Interpreter lock source mismatch')
    expected = '@EXPLICIT\n' + '\n'.join(p['url'] + '#sha256:' + p['sha256'] for p in source['conda_packages']) + '\n'
    if args.conda_lock.read_text(encoding='utf-8') != expected:
        raise ValueError('Interpreter lock text mismatch')
    def get_package(pair):
        name, version = pair
        if name in {'torch','torchvision'}:
            item = records[name]
            if not item['metadata_index_hash_matched']: raise ValueError('CPU metadata gate mismatch')
            result = dict(name=name, version=item['version'], filename=item['filename'], url=item['origin_url'],
                          bytes=item['bytes'], sha256=item['publisher_sha256'], requires_dist=item['requires_dist'],
                          metadata_url=item['metadata_url'], metadata_sha256=item['metadata_sha256'], license='See upstream PyTorch/torchvision distribution licenses')
        else:
            endpoint = f'https://pypi.org/pypi/{name}/{version}/json'
            # Reuse the exact previously captured metadata, not refetch 16 files.
            previous = args.source_probe.parent.parent / 'runtime311-cpu-source-probe' / (name + '.json')
            if name in records and previous.exists():
                raw = previous.read_bytes()
                if hashlib.sha256(raw).hexdigest() != records[name]['metadata_sha256']:
                    raise ValueError('Previous official metadata changed')
            else:
                with urlopen(endpoint, timeout=25) as response: raw = response.read(4*1024**2+1)
                if len(raw)>4*1024**2: raise ValueError('Metadata too large')
            (output / (name + '-pypi.json')).write_bytes(raw)
            metadata = json.loads(raw)
            item = select_wheel(metadata)
            result = dict(name=name, version=version, filename=item['filename'], url=item['url'], bytes=item['size'],
                          sha256=item['digests']['sha256'], requires_dist=metadata['info']['requires_dist'], metadata_url=endpoint,
                          metadata_sha256=hashlib.sha256(raw).hexdigest(), license=metadata['info'].get('license_expression') or metadata['info'].get('license'))
        validate_distribution(result)
        return result
    with ThreadPoolExecutor(max_workers=4) as pool:
        packages = list(pool.map(get_package, sorted((n,v) for n,v in inventory.items() if n not in SKIP)))
    # Check the frozen complete package graph, including environment-specific
    # markers. No extras requested, no newest-version resolver substitutions.
    from packaging.requirements import Requirement
    from packaging.markers import default_environment
    marker_env = default_environment()
    marker_env.update(python_version='3.11', python_full_version='3.11.17', platform_system='Windows', sys_platform='win32', os_name='nt', extra='')
    versions = {p['name'].lower().replace('_','-'): p['version'] for p in packages}
    missing = []
    for package in packages:
        for value in package.get('requires_dist') or []:
            requirement = Requirement(value)
            if requirement.marker and not requirement.marker.evaluate(marker_env): continue
            key = requirement.name.lower().replace('_','-')
            if key not in versions or not requirement.specifier.contains(versions[key]):
                missing.append(dict(package=package['name'], requirement=str(requirement), selected=versions.get(key)))
    result = dict(status='planned' if not missing else 'dependency_graph_rejected', python='3.11.17', platform='win_amd64',
                  packages=packages, missing_or_incompatible=missing, excluded_optional=sorted(SKIP),
                  conda_packages=source['conda_packages'], conda_lock=dict(path=str(args.conda_lock.resolve()),sha256=digest(args.conda_lock)),
                  bootstrap_source_sha256=digest(args.worker_source), total_wheel_bytes=sum(p['bytes'] for p in packages),
                  interpreter_package_bytes=sum(p['size'] for p in source['conda_packages']), free_e_bytes=shutil.disk_usage('E:/').free,
                  budget_scope='Full frozen Python dependency graph plus exact 20 Conda interpreter bootstrap packages. File sizes, not newly transferred bytes; cached distributions may be reused.',
                  original_main_install_provenance='Unknown; these are proposed independent candidate distributions, not historical installation claims',
                  no_environment_switch=True, created_utc=datetime.now(timezone.utc).isoformat())
    (output / 'plan.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    if missing: raise ValueError('Frozen candidate graph incomplete; inspect plan, do not install')
    if result['free_e_bytes'] < 4*1024**3: raise ValueError('Need 4GiB free before candidate download/install')
    return result


def download(item):
    validate_distribution(item)
    target = CACHE / item['filename']
    if target.exists():
        if target.stat().st_size != item['bytes'] or digest(target) != item['sha256']:
            raise ValueError('Existing cache mismatch; preserve and investigate')
        return dict(name=item['name'],path=str(target),sha256=item['sha256'],bytes=item['bytes'],reused=True)
    partial = target.with_name(target.name + '.part')
    offset = partial.stat().st_size if partial.exists() else 0
    if offset > item['bytes']: raise ValueError('Partial exceeds published size')
    if offset == item['bytes'] and digest(partial) == item['sha256']:
        partial.replace(target)
        return dict(name=item['name'],path=str(target),sha256=item['sha256'],bytes=item['bytes'],reused=True)
    with urlopen(Request(item['url'],headers={'Range':f'bytes={offset}-'} if offset else {}),timeout=30) as response:
        if urlparse(response.url).hostname not in {'download.pytorch.org','files.pythonhosted.org'}:
            raise ValueError('Unexpected distribution redirect; no unknown mirror')
        resumed = bool(offset and response.status == 206)
        if resumed and not response.headers.get('Content-Range','').startswith(f'bytes {offset}-'):
            raise ValueError('Invalid resume offset')
        written = offset if resumed else 0
        with partial.open('ab' if resumed else 'wb') as stream:
            while True:
                block = response.read(1024**2)
                if not block: break
                stream.write(block); written += len(block)
                if written > item['bytes']: raise ValueError('Downloaded file too large')
    if partial.stat().st_size != item['bytes'] or digest(partial) != item['sha256']:
        raise ValueError('Incomplete/checksum mismatch; partial retained')
    partial.replace(target)
    print('Verified wheel: ' + item['name'], flush=True)
    return dict(name=item['name'],path=str(target),sha256=item['sha256'],bytes=item['bytes'],reused=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['plan','download','install'])
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--inventory',type=Path); parser.add_argument('--source-probe',type=Path)
    parser.add_argument('--worker-source',type=Path); parser.add_argument('--conda-lock',type=Path)
    parser.add_argument('--plan',type=Path); parser.add_argument('--downloads',type=Path)
    parser.add_argument('--prefix',type=Path)
    args = parser.parse_args()
    output = args.output.resolve(); output.relative_to(Path('E:/BrainFusion-Runtime/results/nightly').resolve())
    output.mkdir(exist_ok=False)
    started = dict(pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),phase=args.phase,output=str(output),prefix=str(args.prefix) if args.prefix else None)
    (output/'process.json').write_text(json.dumps(started,indent=2),encoding='utf-8')
    if args.phase == 'plan': result = plan(args,output)
    else:
        value=read(args.plan)
        if value['status']!='planned': raise ValueError('Accepted frozen graph required')
        if args.phase=='download':
            CACHE.mkdir(parents=True,exist_ok=True)
            with ThreadPoolExecutor(max_workers=3) as pool: files=list(pool.map(download,value['packages']))
            result=dict(status='downloaded_and_sha_verified',plan_sha256=digest(args.plan),files=files,new_environment=False)
        else:
            prefix=args.prefix.resolve(); prefix.relative_to(Path('E:/BrainFusion-Runtime/envs').resolve())
            if not prefix.name.startswith('runtime311-cpu-candidate') or prefix.exists():
                raise ValueError('Fresh owned runtime311-cpu-candidate prefix required; never overwrite')
            files=read(args.downloads)
            if files['status']!='downloaded_and_sha_verified' or files['plan_sha256']!=digest(args.plan):
                raise ValueError('Downloads differ from frozen plan')
            for item in files['files']:
                path=Path(item['path']).resolve();path.relative_to(CACHE.resolve())
                if digest(path)!=item['sha256'] or path.stat().st_size!=item['bytes']:raise ValueError('Verified wheel changed')
            lock=Path(value['conda_lock']['path'])
            if digest(lock)!=value['conda_lock']['sha256']:raise ValueError('Interpreter lock changed')
            env=dict(os.environ,CONDA_PKGS_DIRS='E:/BrainFusion-Runtime/cache/conda',CONDA_ENVS_PATH='E:/BrainFusion-Runtime/envs',CONDA_REGISTER_ENVS='false',CONDA_NUMBER_CHANNEL_NOTICES='0',PYTHONDONTWRITEBYTECODE='1')
            command=['E:/Anaconda3/python.exe','-B','-m','conda','create','-p',str(prefix),'--file',str(lock),'--no-default-packages','--no-shortcuts','-y']
            with (output/'conda-create.log').open('x',encoding='utf-8') as log:
                subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
            requirements=output/'pip-wheel-hash-lock.txt'
            requirements.write_text('\n'.join(item['name']+' @ '+Path(item['path']).as_uri()+' --hash=sha256:'+item['sha256'] for item in files['files'])+'\n',encoding='utf-8')
            python=prefix/'python.exe'
            # Replace same-version Conda bootstrap packages too: otherwise pip
            # omits them from the report, and the observed source is not the
            # selected wheel despite an identical version string.
            install=[sys.executable,'-B','-m','pip','--python',str(python),'install','--force-reinstall','--no-index','--no-deps','--no-compile','--require-hashes','--report',str(output/'pip-install-report.json'),'-r',str(requirements)]
            with (output/'pip-install.log').open('x',encoding='utf-8') as log:
                subprocess.run(install,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
            checked=subprocess.run([str(python),'-B','-m','pip','check'],env=env,capture_output=True,text=True,timeout=60)
            (output/'pip-check.log').write_text(checked.stdout+checked.stderr,encoding='utf-8')
            if checked.returncode:raise ValueError('Candidate pip check failed; never switch')
            result=dict(status='installed_not_model_accepted',prefix=str(prefix),python=str(python),plan_sha256=digest(args.plan),download_record_sha256=digest(args.downloads),
                        conda_bootstrap_packages=len(value['conda_packages']),pip_packages=len(files['files']),bootstrap_note='Conda interpreter bootstrap exact; pip locks explicitly override observed pip/setuptools/wheel distributions. Record final installed metadata separately.',
                        no_current_environment_or_service_switch=True,acceptance='Imports/tests/real model/feature/persistence comparisons still required')
            (prefix/'candidate-source.json').write_text(json.dumps(dict(result,packages=value['packages'],conda_bootstrap=value['conda_packages']),ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in {'packages','conda_packages','files'}},ensure_ascii=False))


if __name__=='__main__': main()
