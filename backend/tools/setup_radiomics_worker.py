"""Install a pinned, isolated legacy radiomics worker entirely on E:.

The main Python/CUDA environment is unchanged. Python's embeddable distribution
does not create Windows registry entries, shortcuts, or user environment files.
This archived interpreter is an offline feature worker, never the web server.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path('E:/BrainFusion-Runtime/envs/radiomics39')
CACHE = Path('E:/BrainFusion-Runtime/cache/radiomics')
PYTHON_URL = 'https://www.python.org/ftp/python/3.9.13/python-3.9.13-embed-amd64.zip'


def main():
    source_file = ROOT / 'source.json'
    probe = 'import sys,radiomics,numpy,SimpleITK,json; print(json.dumps(dict(python=sys.version,radiomics=radiomics.__version__,numpy=numpy.__version__,simpleitk=SimpleITK.Version_VersionString())))'
    if source_file.is_file() and (ROOT / 'python.exe').is_file():
        cached = json.loads(source_file.read_text(encoding='utf-8'))
        checked = subprocess.run([str(ROOT / 'python.exe'), '-B', '-c', probe], capture_output=True, text=True)
        if checked.returncode == 0 and json.loads(checked.stdout) == cached['versions']:
            print('Pinned radiomics worker already available; no installation or file changes')
            return
    ROOT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    archive = CACHE / 'python-3.9.13-embed-amd64.zip'
    if not archive.exists():
        with urllib.request.urlopen(PYTHON_URL, timeout=30) as source, archive.with_suffix('.part').open('wb') as target:
            import shutil
            shutil.copyfileobj(source, target)
        archive.with_suffix('.part').replace(archive)
    with zipfile.ZipFile(archive) as package:
        for member in package.infolist():
            path = (ROOT / member.filename).resolve()
            path.relative_to(ROOT.resolve())
            if not path.exists():
                package.extract(member, ROOT)
    site = ROOT / 'Lib/site-packages'
    site.mkdir(parents=True, exist_ok=True)
    (ROOT / 'python39._pth').write_text('python39.zip\n.\nLib/site-packages\nimport site\n', encoding='ascii')
    base = [sys.executable, '-m', 'pip', 'install', '--target', str(site), '--no-compile', '--disable-pip-version-check']
    # C extensions must target CPython 3.9; pure-Python docopt has no wheel.
    subprocess.run(base + ['--python-version', '3.9', '--platform', 'win_amd64', '--implementation', 'cp', '--abi', 'cp39',
                          '--only-binary=:all:', 'numpy==1.26.4', 'SimpleITK==2.5.2', 'PyWavelets==1.6.0',
                          'pyradiomics==3.1.0', 'pykwalify==1.8.0', 'PyYAML==6.0.2', 'ruamel.yaml==0.18.6',
                          'python-dateutil==2.9.0.post0', 'six==1.17.0', '--no-deps'], check=True)
    subprocess.run(base + ['docopt==0.6.2', '--no-deps'], check=True)
    result = subprocess.run([str(ROOT / 'python.exe'), '-B', '-c',
                             probe],
                            check=True, capture_output=True, text=True)
    provenance = {'python_download': PYTHON_URL, 'python_zip_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                  'versions': json.loads(result.stdout), 'role': 'offline CPU extraction subprocess, not a network service',
                  'main_environment_changed': False, 'legacy_runtime': True}
    (ROOT / 'source.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    print(json.dumps(provenance, indent=2))


if __name__ == '__main__':
    main()
