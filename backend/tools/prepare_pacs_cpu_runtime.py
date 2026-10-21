"""Build a small CPU venv with pinned PACS support over an unchanged trusted base.

Offline only. The 52-package base remains an explicit external dependency;
this is not a standalone/new-machine installation or a service switch.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

WHEEL = dict(name='pydicom', version='3.0.2', filename='pydicom-3.0.2-py3-none-any.whl',
    bytes=2376822, sha256='abf971a5440f84dbaf42c4b6758e30e62480902584f8b270b9a5d146e278a07b',
    url='https://files.pythonhosted.org/packages/46/e0/60466c6d712dad2cf807df315e39863e91609ffd1064ecb835994460bbda/pydicom-3.0.2-py3-none-any.whl',
    source='Official PyPI metadata and wheel already verified on 2026-10-13; no network access here')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_wheel(path):
    path = Path(path).resolve(strict=True)
    if (path.drive.upper() != 'E:' or path.name != WHEEL['filename']
            or path.stat().st_size != WHEEL['bytes'] or digest(path) != WHEEL['sha256']):
        raise ValueError('Missing or changed pinned pydicom wheel; no installation')
    return path


def fresh(path, parent):
    path = Path(path).resolve()
    path.relative_to(Path(parent).resolve())
    if path == Path(parent).resolve() or path.exists():
        raise ValueError('Fresh owned directory required')
    return path


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


INSPECT = '''import sys,json,hashlib,importlib.metadata as m
from pathlib import Path
rows={}
for d in m.distributions():
    name=d.metadata['Name'].lower().replace('_','-')
    record=Path(d._path)/'RECORD'
    rows[name]=dict(version=d.version,record_sha256=hashlib.sha256(record.read_bytes()).hexdigest() if record.is_file() else None,metadata_path=str(d._path))
print(json.dumps(dict(python=sys.version.split()[0],prefix=sys.prefix,base_prefix=sys.base_prefix,packages=rows)))
'''


def inspect(python, env):
    result = subprocess.run([str(python), '-B', '-c', INSPECT], env=env, capture_output=True,
                            text=True, check=True, timeout=60)
    return json.loads(result.stdout)


def run(command, output, label, env):
    with (output/(label+'.log')).open('x', encoding='utf-8') as log:
        process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
        identity = dict(pid=process.pid, started_utc=datetime.now(timezone.utc).isoformat(), command=command)
        save(output/(label+'-process.json'), dict(identity, state='running'))
        try:
            code = process.wait(timeout=180)
        except subprocess.TimeoutExpired:
            # These two commands have no detached builds: venv without ensurepip,
            # then a cached pure-Python wheel with --no-deps and --no-compile.
            process.kill(); process.wait()
            save(output/(label+'-process.json'), dict(identity, state='timed_out_and_reaped'))
            raise
        save(output/(label+'-process.json'), dict(identity, state='completed', returncode=code,
            finished_utc=datetime.now(timezone.utc).isoformat()))
    if code:
        raise ValueError(label+' failed; retain output and do not retry into the same prefix')


def prepare(base_python, receipt_sha256, wheel, prefix, output):
    base = Path(base_python).resolve(strict=True)
    base.relative_to(Path('E:/BrainFusion-Runtime/envs').resolve())
    receipt = base.parent/'delivery-source.json'
    if base.name.lower() != 'python.exe' or digest(receipt) != receipt_sha256:
        raise ValueError('Trusted base receipt SHA mismatch')
    source = json.loads(receipt.read_text(encoding='utf-8-sig'))
    expected = {p['name']:p['version'] for p in source['packages']}
    if len(expected) != 52 or expected.get('torch') != '2.11.0+cpu' or 'pydicom' in expected:
        raise ValueError('Only the accepted unchanged 52-package CPU base is supported')
    wheel = verify_wheel(wheel)
    prefix = fresh(prefix, 'E:/BrainFusion-Runtime/envs')
    output = fresh(output, 'E:/BrainFusion-Runtime/results/nightly')
    if not prefix.name.startswith('runtime311-pacs-'):
        raise ValueError('Fresh runtime311-pacs-* venv required')
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1',
        TEMP='E:/BrainFusion-Runtime/tmp', TMP='E:/BrainFusion-Runtime/tmp',
        PIP_CACHE_DIR='E:/BrainFusion-Runtime/cache/pip', PIP_DISABLE_PIP_VERSION_CHECK='1')
    for name in ['PYTHONHOME', 'PYTHONPATH']:
        env.pop(name, None)
    before = inspect(base, env)
    if before['python'] != '3.11.17' or {k:v['version'] for k,v in before['packages'].items()} != expected:
        raise ValueError('Installed base metadata differs from accepted receipt')
    executable_sha = digest(base)
    output.mkdir(parents=True, exist_ok=False)
    save(output/'base-before.json', before)
    save(output/'pydicom-source.json', WHEEL)
    run([str(base), '-B', '-m', 'venv', '--copies', '--without-pip', '--system-site-packages', str(prefix)], output, 'venv-create', env)
    python = prefix/'Scripts/python.exe'
    wheel_lock = output/'pydicom-hash-lock.txt'
    wheel_lock.write_text('pydicom @ '+wheel.as_uri()+' --hash=sha256:'+WHEEL['sha256']+'\n', encoding='utf-8')
    pip_config = output/'empty-pip.ini'; pip_config.write_text('', encoding='utf-8')
    env['PIP_CONFIG_FILE'] = str(pip_config)
    run([str(python), '-B', '-m', 'pip', 'install', '--ignore-installed', '--no-index', '--no-deps',
        '--no-compile', '--require-hashes', '--report', str(output/'pip-install-report.json'), '-r', str(wheel_lock)], output, 'pydicom-install', env)
    run([str(python), '-B', '-m', 'pip', 'check'], output, 'pip-check', env)
    installed = inspect(python, env)
    expected['pydicom'] = WHEEL['version']
    if {k:v['version'] for k,v in installed['packages'].items()} != expected:
        raise ValueError('Resulting linked environment differs from base plus pinned pydicom')
    Path(installed['packages']['pydicom']['metadata_path']).resolve().relative_to(prefix)
    after = inspect(base, env)
    if before != after or digest(base) != executable_sha or digest(receipt) != receipt_sha256:
        raise ValueError('Base changed; retain evidence and investigate')
    report = json.loads((output/'pip-install-report.json').read_text(encoding='utf-8'))['install']
    if (len(report) != 1 or report[0]['metadata']['name'].lower() != 'pydicom'
            or report[0]['download_info']['archive_info']['hashes']['sha256'] != WHEEL['sha256']):
        raise ValueError('Actual pip source report differs from pinned wheel')
    save(output/'installed-metadata.json', installed)
    save(output/'base-after.json', after)
    result = dict(status='passed_linked_cpu_pacs_environment_not_standalone', python=str(python),
        base_python=str(base), base_receipt_sha256=receipt_sha256, base_executable_sha256=executable_sha,
        packages=53, only_new_package=WHEEL, base_metadata_records_unchanged=True,
        no_network_download=True, no_service_switch=True, base_required_at_original_path=True,
        scope='Windows CPU venv using an existing trusted 52-package base; application/data/model/live gates separate')
    save(prefix/'pacs-linked-source.json', result)
    save(output/'validation.json', result)
    print(json.dumps(dict(status=result['status'], python=str(python), packages=53)))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-python', type=Path, required=True)
    p.add_argument('--base-receipt-sha256', required=True)
    p.add_argument('--wheel', type=Path, required=True)
    p.add_argument('--prefix', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    prepare(a.base_python, a.base_receipt_sha256, a.wheel, a.prefix, a.output)


if __name__ == '__main__':
    main()
