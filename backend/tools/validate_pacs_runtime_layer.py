"""Validate the pinned pydicom-only import layer for a direct CPU interpreter.

No installation, service action, arbitrary PYTHONPATH or network access.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.prepare_pacs_cpu_runtime import WHEEL, digest, inspect, verify_wheel


def check_site(site, wheel):
    """Compare importable layer bytes to the approved wheel; reject extra code."""
    site = Path(site).resolve(strict=True)
    with zipfile.ZipFile(wheel) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate wheel members')
        wanted = {}
        for name in names:
            parts = Path(name).parts
            if name.endswith('/'):
                continue
            if name.startswith('/') or '\\' in name or '..' in parts or ':' in name:
                raise ValueError('Unsafe wheel member')
            if parts[0] not in {'pydicom', 'pydicom-3.0.2.dist-info'}:
                raise ValueError('Wheel contains unexpected import namespace')
            wanted[name] = z.read(name)
    record = 'pydicom-3.0.2.dist-info/RECORD'
    extras = {'pydicom-3.0.2.dist-info/'+n for n in ['INSTALLER', 'REQUESTED', 'direct_url.json']}
    actual = {}
    for directory, dirs, files in os.walk(site, followlinks=False):
        for name in dirs+files:
            p = Path(directory)/name
            if p.is_symlink() or getattr(p.stat(), 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError('Import layer cannot contain reparse points')
        for name in files:
            p = Path(directory)/name
            key = p.relative_to(site).as_posix()
            if key not in wanted and key not in extras:
                raise ValueError('Unexpected installed layer member: '+key)
            actual[key] = p.read_bytes()
    if not set(wanted).issubset(actual):
        raise ValueError('Installed layer is incomplete')
    for key, raw in wanted.items():
        if key != record and actual[key] != raw:
            raise ValueError('Installed layer differs from pinned wheel: '+key)
    if actual.get('pydicom-3.0.2.dist-info/INSTALLER', b'pip\n').strip() != b'pip':
        raise ValueError('Unexpected layer installer')
    if actual.get('pydicom-3.0.2.dist-info/REQUESTED', b'') != b'':
        raise ValueError('Unexpected requested marker')
    if 'pydicom-3.0.2.dist-info/direct_url.json' in actual:
        direct = json.loads(actual['pydicom-3.0.2.dist-info/direct_url.json'])
        if direct.get('archive_info', {}).get('hashes', {}).get('sha256') != WHEEL['sha256']:
            raise ValueError('Layer pip provenance differs from pinned wheel')
    return {k:hashlib.sha256(v).hexdigest() for k,v in sorted(actual.items())}


def validate(base_python, layer, wheel):
    base = Path(base_python).resolve(strict=True)
    layer = Path(layer).resolve(strict=True)
    layer.relative_to(Path('E:/BrainFusion-Runtime/envs').resolve())
    if not layer.name.startswith('runtime311-pacs-'):
        raise ValueError('Expected registered runtime311-pacs-* layer')
    receipt_file = layer/'pacs-linked-source.json'
    receipt = json.loads(receipt_file.read_text(encoding='utf-8-sig'))
    if (receipt.get('status') != 'passed_linked_cpu_pacs_environment_not_standalone'
            or Path(receipt['base_python']).resolve() != base
            or digest(base) != receipt['base_executable_sha256']
            or digest(base.parent/'delivery-source.json') != receipt['base_receipt_sha256']
            or receipt['only_new_package'] != WHEEL):
        raise ValueError('Base/layer source identity mismatch')
    wheel = verify_wheel(wheel)
    site = layer/'Lib/site-packages'
    site.resolve(strict=True).relative_to(layer)
    if site.is_symlink() or getattr(site.stat(), 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise ValueError('Layer site root cannot be a reparse point')
    files = check_site(site, wheel)
    env = dict(os.environ, PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1')
    env.pop('PYTHONPATH', None); env.pop('PYTHONHOME', None)
    metadata = inspect(base, env)
    expected = {p['name']:p['version'] for p in json.loads((base.parent/'delivery-source.json').read_text(encoding='utf-8-sig'))['packages']}
    if (metadata['python'] != '3.11.17' or len(expected) != 52
            or expected.get('torch') != '2.11.0+cpu'
            or {k:v['version'] for k,v in metadata['packages'].items()} != expected):
        raise ValueError('CPU base metadata changed')
    env['PYTHONPATH'] = str(site)
    code="import json,os,pydicom;print(json.dumps(dict(pid=os.getpid(),file=pydicom.__file__,version=pydicom.__version__)))"
    process = subprocess.Popen([str(base), '-B', '-c', code], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        stdout, stderr = process.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill(); process.wait(); raise
    if process.returncode:
        raise ValueError('Direct interpreter layer import failed')
    probe = json.loads(stdout)
    if probe['pid'] != process.pid or probe['version'] != WHEEL['version']:
        raise ValueError('Direct interpreter PID/version contract failed')
    Path(probe['file']).resolve().relative_to(site.resolve())
    identity = dict(base_executable=receipt['base_executable_sha256'], base_receipt=receipt['base_receipt_sha256'],
                    layer_receipt=digest(receipt_file), wheel=WHEEL['sha256'], files=files)
    return dict(status='passed', layer=str(layer), site_path=str(site), base_python=str(base),
        identity_sha256=hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest(),
        pinned_layer_files=len(files), direct_process=True, scope='Pinned pydicom namespace only; unchanged CPU base is required')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-python', type=Path, required=True)
    p.add_argument('--layer', type=Path, required=True)
    p.add_argument('--wheel', type=Path, default=Path('E:/BrainFusion-Runtime/cache/dicom-tools/pydicom-3.0.2-py3-none-any.whl'))
    a = p.parse_args()
    print(json.dumps(validate(a.base_python, a.layer, a.wheel)))
