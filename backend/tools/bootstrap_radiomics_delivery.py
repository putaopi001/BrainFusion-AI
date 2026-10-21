"""Rebuild a frozen Windows feature worker offline, using its own new pip.

Standard-library entry. Requires an independently trusted profile SHA. No web
server, legacy/project pip, protocol change, compatibility-gate rewrite or download.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlparse, unquote
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.bootstrap_cpu_delivery import digest, fresh, read, record, safe_member

def canonical(name): return re.sub('[-_.]+','-',name).lower()

def wheel_manifest(wheel):
    """Fingerprint importable payloads without needing a prior installed worker."""
    checked=[]
    with zipfile.ZipFile(wheel) as archive:
        names=archive.namelist()
        if len(names)!=len(set(names)): raise ValueError('Duplicate wheel members')
        for info in archive.infolist():
            # CPython 3.10 on Windows normalizes separators in filename while
            # orig_filename retains the actual untrusted central-directory name.
            safe_member(info.orig_filename.rstrip('/') if info.is_dir() else info.orig_filename)
            name=info.filename.rstrip('/') if info.is_dir() else info.filename
            safe_member(name)
            if info.is_dir(): continue
            if (info.external_attr >> 16)&0o170000 == 0o120000: raise ValueError('Wheel links rejected')
            if '.dist-info/' in name: continue
            if '.data/' in name:
                tail=name.split('.data/',1)[1]
                group,relative=tail.split('/',1)
                if group not in ('purelib','platlib'): continue  # pip rewrites script launchers.
                name=relative
            raw=archive.read(info)
            expected=__import__('hashlib').sha256(raw).hexdigest()
            checked.append(dict(path=name,sha256=expected,bytes=len(raw)))
    if not checked: raise ValueError('No checked import payload')
    return checked

def wheel_payload(wheel,prefix,compare_root=None):
    checked=wheel_manifest(wheel)
    for item in checked:
        name=item['path'];target=Path(prefix)/'Lib/site-packages'/name
        target.resolve(strict=True).relative_to(Path(prefix).resolve())
        if digest(target)!=item['sha256']: raise ValueError('Installed wheel payload differs: '+name)
        if compare_root and digest(Path(compare_root)/'Lib/site-packages'/name)!=item['sha256']:
            raise ValueError('Accepted worker payload differs: '+name)
    return checked

def verify_profile(profile_path, expected_sha, compare_accepted=None):
    if not re.fullmatch('[0-9a-f]{64}',expected_sha) or digest(profile_path)!=expected_sha:
        raise ValueError('Trusted worker profile SHA mismatch')
    profile=read(profile_path)
    if profile.get('format_version')!=1 or profile.get('python')!='3.11.17' or profile.get('platform')!='win_amd64':
        raise ValueError('Only frozen Windows CP311 worker supported')
    if len(profile['conda_packages'])!=20 or len(profile['wheels'])!=11: raise ValueError('Incomplete worker profile')
    if len(profile['expected_installed'])!=15: raise ValueError('Incomplete installed metadata profile')
    # Old paths describe provenance, not new-machine installation prerequisites.
    # Explicit trusted profile SHA binds frozen payloads even without old env.
    accepted=Path(compare_accepted).resolve(strict=True) if compare_accepted else None
    if accepted:
        accepted.relative_to(Path('E:/BrainFusion-Runtime/envs').resolve())
        if digest(accepted/'source.json')!=profile['source_sha256']: raise ValueError('Accepted worker provenance changed')
        if digest(profile['dependency_locks'])!=profile['dependency_locks_sha256']: raise ValueError('Dependency locks changed')
        if digest(profile['accepted_gate_path'])!=profile['accepted_gate_sha256']: raise ValueError('Original compatibility gate changed')
    names=set()
    for item in profile['conda_packages']+profile['wheels']:
        url=urlparse(item['upstream_url'])
        if url.scheme!='https' or url.hostname not in ('conda.anaconda.org','files.pythonhosted.org') or url.username or url.password or url.port not in (None,443) or url.query or url.fragment:
            raise ValueError('Unapproved official upstream source')
        if url.hostname=='conda.anaconda.org' and not url.path.startswith('/conda-forge/'):
            raise ValueError('Unapproved Conda channel')
        path=Path(item['cache_path']).resolve(strict=True)
        path.relative_to(Path('E:/BrainFusion-Runtime/cache').resolve())
        if path.stat().st_size!=item['bytes'] or digest(path)!=item['sha256']: raise ValueError('Missing/changed approved cache')
        if not re.fullmatch('[0-9a-f]{64}',item['upstream_sha256']): raise ValueError('Missing upstream hash')
        if item in profile['wheels']:
            name=canonical(item['name'])
            if name in names or not path.name.endswith('.whl'): raise ValueError('Duplicate/non-wheel distribution')
            names.add(name)
            if profile['expected_installed'].get(name)!=item['version']: raise ValueError('Wheel version changed')
            payload=wheel_payload(path,accepted) if accepted else wheel_manifest(path)
            if payload!=item['payload']: raise ValueError('Accepted wheel payload manifest changed')
    if names!={canonical(n) for n in ('numpy','SimpleITK','PyWavelets','pykwalify','PyYAML','ruamel.yaml','python-dateutil','six','docopt','ruamel.yaml.clib','pyradiomics')}:
        raise ValueError('Worker dependency identity changed')
    if accepted:
        for filename,sha in profile['interpreter_payload'].items():
            if digest(accepted/filename)!=sha: raise ValueError('Accepted interpreter payload changed')
    return profile

def child(command, output, label, env):
    with (output/(label+'.log')).open('x',encoding='utf-8') as log:
        process=subprocess.Popen(command,env=env,stdout=log,stderr=subprocess.STDOUT)
        started=subprocess.check_output(['powershell.exe','-NoProfile','-Command',f"(Get-Process -Id {process.pid}).StartTime.ToUniversalTime().ToString('o')"],text=True).strip()
        state=dict(pid=process.pid,started_utc=started,command=command,state='running')
        record(output/(label+'-process.json'),state)
        code=process.wait(timeout=300)
        record(output/(label+'-process.json'),dict(state,state='completed',returncode=code,finished_utc=datetime.now(timezone.utc).isoformat()))
    if code: raise ValueError(label+' failed; preserve evidence, never retry into same partial prefix')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',type=Path,required=True)
    parser.add_argument('--expected-profile-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--install-prefix',type=Path,required=True)
    parser.add_argument('--conda-python',type=Path,default=Path('E:/Anaconda3/python.exe'))
    parser.add_argument('--compare-accepted',type=Path,help='Optional local reference check; never required on a new machine')
    args=parser.parse_args()
    profile=verify_profile(args.profile,args.expected_profile_sha256,args.compare_accepted)
    output=fresh(args.output,'E:/BrainFusion-Runtime/results/nightly')
    prefix=fresh(args.install_prefix,'E:/BrainFusion-Runtime/envs')
    if not prefix.name.startswith('radiomics311-delivery-'): raise ValueError('Fresh dedicated worker prefix required')
    conda=args.conda_python.resolve(strict=True)
    if conda.drive.upper()!='E:' or conda.name.lower()!='python.exe': raise ValueError('Trusted E-drive Conda interpreter required')
    if __import__('shutil').disk_usage('E:/').free < 1024**3: raise ValueError('Insufficient conservative disk reserve')
    output.mkdir(parents=True,exist_ok=False)
    record(output/'process.json',dict(pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),command=sys.argv,state='running'))
    temporary=Path('E:/BrainFusion-Runtime/tmp/radiomics-delivery');temporary.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,TEMP=str(temporary),TMP=str(temporary),PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',
        CONDA_PKGS_DIRS='E:/BrainFusion-Runtime/cache/conda',CONDA_ENVS_PATH='E:/BrainFusion-Runtime/envs',CONDA_REGISTER_ENVS='false',CONDA_NUMBER_CHANNEL_NOTICES='0',PIP_CACHE_DIR='E:/BrainFusion-Runtime/cache/pip')
    explicit=output/'local-conda-explicit.txt'
    explicit.write_text('@EXPLICIT\n'+'\n'.join(Path(p['cache_path']).as_uri()+'#sha256:'+p['sha256'] for p in profile['conda_packages'])+'\n',encoding='utf-8')
    child([str(conda),'-B','-m','conda','create','--offline','--no-default-packages','--no-shortcuts','-y','-p',str(prefix),'--file',str(explicit)],output,'conda-create',env)
    wheel_lock=output/'local-wheel-hash-lock.txt'
    wheel_lock.write_text('\n'.join(p['name']+' @ '+Path(p['cache_path']).as_uri()+' --hash=sha256:'+p['sha256'] for p in profile['wheels'])+'\n',encoding='utf-8')
    python=prefix/'python.exe'
    child([str(python),'-B','-m','pip','install','--no-index','--no-deps','--no-compile','--require-hashes','--report',str(output/'pip-install-report.json'),'-r',str(wheel_lock)],output,'pip-install',env)
    child([str(python),'-B','-m','pip','check'],output,'pip-check',env)
    probe="import sys,json,importlib.metadata as m,numpy,SimpleITK,radiomics;print(json.dumps(dict(python=sys.version.split()[0],packages={d.metadata['Name'].lower().replace('_','-'):d.version for d in m.distributions()},versions=dict(numpy=numpy.__version__,simpleitk=SimpleITK.Version_VersionString(),radiomics=radiomics.__version__))))"
    installed=json.loads(subprocess.check_output([str(python),'-B','-c',probe],env=env,text=True))
    installed['packages']={canonical(name):version for name,version in installed['packages'].items()}
    if installed['python']!=profile['python'] or installed['packages']!=profile['expected_installed'] or installed['versions']!=profile['versions']: raise ValueError('Installed worker metadata/import differs')
    report={canonical(p['metadata']['name']):p for p in read(output/'pip-install-report.json')['install']}
    payload=[]
    for item in profile['wheels']:
        if report[canonical(item['name'])]['download_info']['archive_info']['hashes']['sha256']!=item['sha256']: raise ValueError('Pip actual installation SHA differs')
        checked=wheel_payload(item['cache_path'],prefix,args.compare_accepted)
        if checked!=item['payload']: raise ValueError('Actual installed payload differs')
        payload.extend(checked)
    if len(report)!=11: raise ValueError('Incomplete pip install source report')
    for filename,sha in profile['interpreter_payload'].items():
        if digest(prefix/filename)!=sha: raise ValueError('Actual interpreter binary differs')
    record(output/'installed-metadata.json',installed)
    record(output/'installed-payload.json',payload)
    # New provenance remains a candidate; do not impersonate the original gate.
    record(prefix/'source.json',dict(versions=dict(python=installed['python'],**installed['versions']),legacy_runtime=False,role='isolated CPU extraction candidate, not a network service',main_environment_changed=False,
        source_profile_sha256=args.expected_profile_sha256,accepted_worker_source_sha256=profile['source_sha256'],
        packages=profile['wheels'],conda_packages=profile['conda_packages'],installed_payload_count=len(payload),
        status='byte_identical_installed_payload; deployment compatibility gate and service switch not performed'))
    result=dict(status='passed_offline_independent_worker_bootstrap_not_live_gate_or_new_machine',created_utc=datetime.now(timezone.utc).isoformat(),profile_sha256=args.expected_profile_sha256,prefix=str(prefix),
        python=installed['python'],installed_packages=len(installed['packages']),installed_wheels=11,conda_packages=20,
        installed_import_payload_files=len(payload),installed_interpreter_binaries_match_accepted=True,installed_payload_matches_accepted_worker=True,all_install_report_sha_match=True,
        no_network_legacy_pip_protocol_gate_service_or_current_worker_change=True,
        scope='Same-workstation offline worker reconstruction and byte/metadata equivalence. Historical scientific gate remains unchanged and bound to original source; no new extraction, live deployment or new-machine/container acceptance.')
    record(output/'validation.json',result)
    record(output/'process.json',dict(pid=os.getpid(),state='completed',finished_utc=result['created_utc'],command=sys.argv))
    print(json.dumps(result))

if __name__=='__main__':main()
