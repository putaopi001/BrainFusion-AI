"""Build the unmodified upstream PyRadiomics C extensions with pinned Zig cc.

Creates an isolated cp311 Windows wheel; does not run upstream setup/data scripts.
No main/legacy environment changes, protocol changes or system installation.
"""
import argparse
import base64
import csv
from datetime import datetime, timezone
from email.parser import Parser
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from fetch_radiomics_build_sources import digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--dependencies-report', type=Path, required=True)
    parser.add_argument('--headers', type=Path, required=True, help='Verified exact-commit missing header evidence directory')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to(Path('E:/BrainFusion-Runtime/results/nightly').resolve())
    output.mkdir(exist_ok=False)
    worker = args.python.resolve(strict=True)
    worker.relative_to(Path('E:/BrainFusion-Runtime/envs').resolve())
    if (worker.parent / 'source.json').exists():
        raise ValueError('Candidate already has provenance; do not overwrite a completed environment')
    sources = json.loads(args.sources.read_text(encoding='utf-8'))
    compiler, source = Path(sources['compiler']), Path(sources['source_root'])
    # Recheck the two downloaded archives against their pinned upstream hashes.
    for item in sources['sources']:
        archive = Path('E:/BrainFusion-Runtime/cache/radiomics-build') / Path(item['url']).name
        assert archive.stat().st_size == item['bytes'] and digest(archive) == item['sha256']
    metadata = Parser().parsestr((source / 'PKG-INFO').read_text(encoding='utf-8'))
    if metadata['Version'] != '3.1.0':
        raise ValueError('Unexpected source version')
    headers = json.loads((args.headers / 'headers.json').read_text(encoding='utf-8'))
    assert headers['status'] == 'passed' and headers['source_c_files_identical'] == 4
    for entry in headers['sources']:
        file = args.headers / 'include' / Path(entry['path']).name if entry['path'].endswith('.h') else source / entry['path']
        assert digest(file) == entry['sha256']
    env = os.environ.copy()
    env.update(ZIG_GLOBAL_CACHE_DIR='E:/BrainFusion-Runtime/cache/zig',
               ZIG_LOCAL_CACHE_DIR=str(output / 'zig-cache'), PYTHONDONTWRITEBYTECODE='1')
    probe_code = "import sys,sysconfig,numpy,json;print(json.dumps(dict(python=sys.version,include=sysconfig.get_path('include'),numpy_include=numpy.get_include(),suffix=sysconfig.get_config_var('EXT_SUFFIX'))))"
    probe = json.loads(subprocess.run([str(worker), '-B', '-c', probe_code], capture_output=True, text=True, check=True, env=env).stdout)
    if not probe['python'].startswith('3.11.') or '1.26' not in subprocess.run([str(worker), '-c', 'import numpy;print(numpy.__version__)'],capture_output=True,text=True,check=True).stdout:
        raise ValueError('Only pinned CPython3.11/NumPy1.26 candidate supported by this build')
    compiler_version = subprocess.run([str(compiler), 'version'],capture_output=True,text=True,check=True,env=env).stdout.strip()
    if compiler_version != '0.15.2':
        raise ValueError('Compiler version does not match pinned provenance')
    staging = output / 'wheel-staging'
    shutil.copytree(source / 'radiomics', staging / 'radiomics')
    original_hashes = {p.relative_to(source).as_posix():digest(p) for p in source.rglob('*') if p.is_file()}
    plan = {'pid': os.getpid(), 'started_utc': datetime.now(timezone.utc).isoformat(), 'worker': str(worker),
            'source_files_sha256': original_hashes, 'compiler': str(compiler), 'compiler_version': compiler_version,
            'target': 'x86_64-windows-gnu', 'optimization': '-O2, no fast-math', 'commands': []}
    for extension, files in {'_cmatrices': ['_cmatrices.c', 'cmatrices.c'], '_cshape': ['_cshape.c', 'cshape.c']}.items():
        artifact = staging / 'radiomics' / (extension + probe['suffix'])
        command = [str(compiler), 'cc', '-target', 'x86_64-windows-gnu', '-shared', '-O2', '-DNDEBUG',
                   '-I' + probe['include'], '-I' + probe['numpy_include'], '-I' + str(args.headers / 'include'),
                   *[str(source / 'radiomics/src' / name) for name in files],
                   str(worker.parent / 'libs/python311.lib'), '-o', str(artifact)]
        plan['commands'].append(command)
        (output / 'build-plan.json').write_text(json.dumps(plan, indent=2),encoding='utf-8')
        print('Compiling unmodified upstream ' + extension, flush=True)
        with (output / (extension + '.log')).open('w', encoding='utf-8') as log:
            subprocess.run(command, cwd=output, env=env, stdout=log, stderr=log, timeout=240, check=True)
    assert all(digest(source / name) == value for name,value in original_hashes.items())
    dist_info = staging / 'pyradiomics-3.1.0.dist-info'
    dist_info.mkdir()
    (dist_info / 'METADATA').write_text((source / 'PKG-INFO').read_text(encoding='utf-8'),encoding='utf-8')
    (dist_info / 'WHEEL').write_text('Wheel-Version: 1.0\nGenerator: BrainFusion verified upstream C build\nRoot-Is-Purelib: false\nTag: cp311-cp311-win_amd64\n',encoding='utf-8')
    for filename in ('LICENSE.txt', 'LICENSE'):
        if (source / filename).is_file():
            shutil.copyfile(source / filename, dist_info / filename)
    records = []
    for file in sorted(staging.rglob('*')):
        if file.is_file():
            raw = file.read_bytes()
            checksum = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')
            records.append([file.relative_to(staging).as_posix(), 'sha256=' + checksum, len(raw)])
    records.append(['pyradiomics-3.1.0.dist-info/RECORD', '', ''])
    # Disable Windows newline translation: CRLF translated twice creates empty
    # RECORD rows and pip's installer cannot read that wheel.
    with (dist_info / 'RECORD').open('w', encoding='utf-8', newline='') as record_file:
        csv.writer(record_file, lineterminator='\n').writerows(records)
    wheel = output / 'pyradiomics-3.1.0-cp311-cp311-win_amd64.whl'
    with zipfile.ZipFile(wheel, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(staging.rglob('*')):
            if file.is_file():
                info = zipfile.ZipInfo(file.relative_to(staging).as_posix(), date_time=(1980,1,1,0,0,0))
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, file.read_bytes())
    # This is our unfinished isolated candidate only; do not uninstall an
    # interrupted wheel using its potentially incomplete RECORD.
    install = [str(worker), '-B', '-m', 'pip', 'install', '--ignore-installed', '--no-deps', '--no-compile', '--disable-pip-version-check', str(wheel)]
    with (output / 'wheel-install.log').open('w',encoding='utf-8') as log:
        subprocess.run(install,env=env,stdout=log,stderr=log,timeout=60,check=True)
    version_code = "import sys,radiomics,numpy,SimpleITK,json;print(json.dumps(dict(python=sys.version,radiomics=radiomics.__version__,numpy=numpy.__version__,simpleitk=SimpleITK.Version_VersionString())))"
    versions = json.loads(subprocess.run([str(worker),'-B','-c',version_code],capture_output=True,text=True,check=True,env=env).stdout)
    packages = [json.loads(p.read_text(encoding='utf-8')) for p in (worker.parent/'conda-meta').glob('*.json')]
    dependencies = json.loads(args.dependencies_report.read_text(encoding='utf-8'))
    provenance = {'versions': versions, 'legacy_runtime': False, 'role': 'isolated CPU extraction, not a network service',
                  'main_environment_changed': False, 'upstream_sources': sources['sources'],
                  'headers_provenance': headers,
                  'conda_packages': [{key:p.get(key) for key in ('name','version','build','url','sha256','size','license')} for p in packages],
                  'pypi_dependencies': dependencies['install'], 'compiler': plan, 'wheel': str(wheel),
                  'wheel_sha256': digest(wheel), 'wheel_bytes': wheel.stat().st_size,
                  'extension_sha256': {file.name:digest(file) for file in (staging/'radiomics').glob('*.pyd')},
                  'status': 'built_and_imported; acceptance is determined by the separate feature/probability compatibility gate'}
    (worker.parent / 'source.json').write_text(json.dumps(provenance, indent=2),encoding='utf-8')
    (output / 'build-result.json').write_text(json.dumps(provenance, indent=2),encoding='utf-8')
    print(json.dumps({'status':'built_and_imported','versions':versions,'wheel_sha256':digest(wheel),'sources_unchanged':True}),flush=True)


if __name__ == '__main__':
    main()
