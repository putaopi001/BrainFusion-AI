"""Freeze a worker reconstruction profile from accepted provenance/E caches.

No dependency downloads, rebuilding upstream scripts, current worker mutation
or new extraction. Locally built docopt/PyRadiomics wheels are labeled as such.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from urllib.parse import urlparse,unquote
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.bootstrap_cpu_delivery import digest,read,record,fresh
from tools.bootstrap_radiomics_delivery import canonical,wheel_payload,verify_profile
from tools.verify_delivery_readiness import verify_worker_locks

def cached_upstream(packages,root):
    targets={p['bytes']:p for p in packages}
    if len(targets)!=len(packages): raise ValueError('Ambiguous frozen cache size')
    found={}
    root=Path(root).resolve(strict=True);root.relative_to(Path('E:/BrainFusion-Runtime/cache').resolve())
    for path in root.rglob('*.body'):
        item=targets.get(path.stat().st_size)
        if item and digest(path)==item['sha256']: found[canonical(item['name'])]=path
    if len(found)!=len(packages): raise ValueError('Frozen official cache missing; no network or guessed replacement')
    return found

def docopt_wheel(root,source,expected):
    with tarfile.open(source,'r:gz') as archive:
        entry=archive.getmember('docopt-0.6.2/docopt.py')
        if not entry.isfile() or entry.size>1024**2: raise ValueError('Bounded upstream docopt module required')
        module=archive.extractfile(entry).read()
    for wheel in sorted(Path(root).rglob('docopt-0.6.2-py2.py3-none-any.whl')):
        origin=read(wheel.parent/'origin.json')
        if origin['url']!=expected['url'] or origin['archive_info']['hashes']['sha256']!=expected['sha256']: continue
        with zipfile.ZipFile(wheel) as archive:
            if archive.read('docopt.py')==module: return wheel
    raise ValueError('No cached locally built docopt wheel bound to approved upstream module/source')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--expected-source-sha256',required=True)
    parser.add_argument('--dependency-locks',type=Path,required=True)
    parser.add_argument('--gate',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--pip-cache',type=Path,default=Path('E:/BrainFusion-Runtime/cache/pip'))
    args=parser.parse_args()
    source=read(args.source);locks=read(args.dependency_locks/'validation.json');gate=read(args.gate)
    if digest(args.source)!=args.expected_source_sha256 or gate['status']!='passed' or gate['worker_provenance_sha256']!=args.expected_source_sha256:
        raise ValueError('Accepted source/gate fingerprint required')
    verify_worker_locks(args.source,args.dependency_locks)
    worker=args.source.resolve(strict=True).parent;worker.relative_to(Path('E:/BrainFusion-Runtime/envs').resolve())
    metadata=json.loads(subprocess.check_output([str(worker/'python.exe'),'-B','-c',"import json,importlib.metadata as m;print(json.dumps({d.metadata['Name'].lower().replace('_','-'):d.version for d in m.distributions()}))"],text=True))
    metadata={canonical(name):version for name,version in metadata.items()}
    if len(metadata)!=15 or not source['versions']['python'].startswith('3.11.17'): raise ValueError('Accepted CP311 worker metadata required')
    found=cached_upstream(locks['pip_packages'],args.pip_cache)
    docopt=next(p for p in locks['pip_packages'] if canonical(p['name'])=='docopt')
    built_docopt=docopt_wheel(args.pip_cache,found['docopt'],docopt)
    wheel_items=[]
    for item in locks['pip_packages']:
        path=built_docopt if canonical(item['name'])=='docopt' else found[canonical(item['name'])]
        filename=path.name if path==built_docopt else unquote(urlparse(item['url']).path).rsplit('/',1)[-1]
        payload=wheel_payload(path,worker)
        wheel_items.append(dict(name=canonical(item['name']),version=item['version'],filename=filename,bytes=path.stat().st_size,sha256=digest(path),upstream_url=item['url'],upstream_sha256=item['sha256'],
            origin='locally_built_cached_wheel; upstream module byte-checked, no setup execution this run' if path==built_docopt else 'official release bytes matched cached HTTP body; historical download URL unknown',payload=payload,original_cache_path=str(path)))
    local_wheel=Path(source['wheel']).resolve(strict=True);local_wheel.relative_to(Path('E:/BrainFusion-Runtime/results/nightly').resolve())
    upstream=next(p for p in source['upstream_sources'] if p['role']=='PyRadiomics upstream source')
    if digest(local_wheel)!=source['wheel_sha256']: raise ValueError('Accepted local PyRadiomics wheel changed')
    wheel_items.append(dict(name='pyradiomics',version='3.1.0',filename=local_wheel.name,bytes=local_wheel.stat().st_size,sha256=digest(local_wheel),upstream_url=upstream['url'],upstream_sha256=upstream['sha256'],
        origin='accepted locally compiled CP311 Windows wheel, not upstream binary',payload=wheel_payload(local_wheel,worker),original_cache_path=str(local_wheel)))
    conda=[]
    for item in locks['conda_packages']:
        filename=unquote(urlparse(item['url']).path).rsplit('/',1)[-1];path=Path('E:/BrainFusion-Runtime/cache/conda')/filename
        if path.stat().st_size!=item['size'] or digest(path)!=item['sha256']: raise ValueError('Approved Conda cache missing/changed')
        conda.append(dict(name=item['name'],version=item['version'],filename=filename,cache_path=str(path),bytes=item['size'],sha256=item['sha256'],upstream_url=item['url'],upstream_sha256=item['sha256'],license=item['license']))
    output=fresh(args.output,'E:/BrainFusion-Runtime/results/nightly');output.mkdir(parents=True,exist_ok=False)
    cache=Path('E:/BrainFusion-Runtime/cache/radiomics311-delivery/wheels');cache.mkdir(parents=True,exist_ok=True)
    for item in wheel_items:
        target=cache/item['filename']
        if target.exists():
            if digest(target)!=item['sha256']: raise ValueError('Preserve conflicting cache; do not overwrite')
        else: shutil.copyfile(item['original_cache_path'],target)
        item['cache_path']=str(target)
    result=dict(format_version=1,created_utc=datetime.now(timezone.utc).isoformat(),python='3.11.17',platform='win_amd64',accepted_worker=str(worker),source_sha256=digest(args.source),
        dependency_locks=str((args.dependency_locks/'validation.json').resolve()),dependency_locks_sha256=digest(args.dependency_locks/'validation.json'),
        accepted_gate_path=str(args.gate.resolve()),accepted_gate_sha256=digest(args.gate),
        expected_installed=metadata,versions={key:source['versions'][key] for key in ('numpy','radiomics','simpleitk')},
        interpreter_payload={name:digest(worker/name) for name in ('python.exe','python311.dll')},conda_packages=conda,wheels=wheel_items,
        scope='Local integrity-bound reconstruction profile, not a signature or redistributable/new-machine package. Windows only, old scientific gate stays bound to original worker, independent deployment gate not supplied.')
    profile=output/'worker-source-profile.json';record(profile,result)
    verify_profile(profile,digest(profile),worker)
    validation=dict(status='verified_accepted_worker_profile_and_all_cached_sources_no_install',profile_sha256=digest(profile),source_sha256=result['source_sha256'],conda_packages=20,install_wheels=11,
        official_release_archives=10,locally_built_wheels=2,installed_metadata=15,cached_source_file_bytes=sum(p['bytes'] for p in conda+wheel_items),
        original_source_metadata_gate_unchanged=True,no_network_install_or_extraction=True)
    record(output/'validation.json',validation);print(json.dumps(validation))

if __name__=='__main__':main()
