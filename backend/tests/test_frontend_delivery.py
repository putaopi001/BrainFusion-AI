import base64
from copy import deepcopy
from pathlib import Path
import re
import hashlib
import zipfile
from urllib.parse import urlunsplit

import pytest

from tools.prepare_frontend_delivery import origin, sri_matches, sri_path, unpack_node, verify_lock
from tools.lock_docker_requirements import wheel_identity


@pytest.fixture
def locks():
    integrity = 'sha512-'+base64.b64encode(hashlib.sha512(b'fixture archive').digest()).decode()
    packages, records = {}, []
    for index in range(422):
        directory = '@popperjs/core' if index == 0 else 'fixture-'+str(index)
        name = '@sxzz/popperjs-es' if index == 0 else directory
        key = 'node_modules/'+directory
        item = dict(version='2.11.8',integrity=integrity,resolved='https://registry.npmmirror.com/'+name+'/-/fixture.tgz')
        if index == 0: item['name'] = name
        packages[key] = item
        records.append(dict(path=key,name=name,version=item['version'],sri=integrity,matched=True,official_tarball_url='https://registry.npmjs.org/'+name+'/-/fixture.tgz'))
    original = dict(packages=packages)
    derived = deepcopy(original)
    for record in records: derived['packages'][record['path']]['resolved'] = record['official_tarball_url']
    probe = dict(status='official_source_mapping_checked_not_installed',matched_entries=422,packages=records)
    return original,derived,probe


def test_explicit_npm_alias_preserved(locks):
    original,derived,probe = locks
    assert verify_lock(original,derived,probe)['node_modules/@popperjs/core']['name'] == '@sxzz/popperjs-es'
    assert original['packages']['node_modules/@popperjs/core']['resolved'].startswith('https://registry.npmmirror.com/')


@pytest.mark.parametrize('field,value',[('name','@popperjs/core'),('version','3.0.0'),('integrity','sha512-YQ==')])
def test_identity_version_or_sri_mutation_rejected(locks,field,value):
    original,derived,probe = locks
    derived['packages']['node_modules/@popperjs/core'][field] = value
    with pytest.raises(ValueError): verify_lock(original,derived,probe)


def test_non_origin_or_credential_url_rejected():
    credential_fixture = urlunsplit(('https','user:secret@registry.npmjs.org','/x','',''))
    for value in ('http://registry.npmjs.org/x','https://registry.npmmirror.com/x',credential_fixture,'https://registry.npmjs.org/x?q=1'):
        with pytest.raises(ValueError): origin(value,'registry.npmjs.org')


def test_actual_sri_detects_corrupt_cached_file(tmp_path):
    raw = b'actual cached tarball fixture'
    integrity = 'sha512-'+base64.b64encode(hashlib.sha512(raw).digest()).decode()
    canonical = sri_path(tmp_path,integrity)
    assert canonical.name == hashlib.sha512(raw).hexdigest()[4:]
    # The real E-cache root is short; don't exceed Win32 MAX_PATH in pytest's long fixture path.
    target = tmp_path/'cached.tgz'
    target.write_bytes(raw)
    assert sri_matches(target,integrity)
    target.write_bytes(raw+b'changed')
    assert not sri_matches(target,integrity)


def test_node_root_directory_allowed_but_traversal_rejected(tmp_path):
    archive = tmp_path/'fixture-node.zip'
    with zipfile.ZipFile(archive,'w') as output:
        output.writestr('node-v24.21.0-win-x64/','')
        output.writestr('node-v24.21.0-win-x64/node.exe',b'not executed fixture')
    prefix = tmp_path/'owned-valid-prefix'
    unpack_node(archive,prefix)
    assert (prefix/'node.exe').read_bytes() == b'not executed fixture'
    bad = tmp_path/'bad-node.zip'
    with zipfile.ZipFile(bad,'w') as output: output.writestr('node-v24.21.0-win-x64/../outside',b'x')
    rejected = tmp_path/'owned-rejected-prefix'
    with pytest.raises(ValueError): unpack_node(bad,rejected)
    assert not rejected.exists() and not (tmp_path/'outside').exists()


def test_docker_base_images_are_digest_pinned():
    root = Path(__file__).resolve().parents[2]
    backend = (root / 'backend/Dockerfile').read_text(encoding='utf-8')
    frontend = (root / 'frontend/Dockerfile').read_text(encoding='utf-8')
    refs = []
    for source in (backend, frontend):
        refs.extend(line.split()[1] for line in source.splitlines() if line.startswith('FROM '))
    external = [ref for ref in refs if '@sha256:' in ref]
    internal = [ref for ref in refs if '@sha256:' not in ref]
    assert len(external) == 4
    assert internal == ['api', 'api']
    assert all(re.fullmatch(r'[^\s]+@sha256:[0-9a-f]{64}', ref) for ref in external)
    assert external[0].startswith('python:3.9-slim-bookworm@')
    assert external[1].startswith('python:3.10-slim-bookworm@')
    assert external[2].startswith('node:24-alpine3.24@')
    assert external[3].startswith('nginx:1.30.6-alpine3.24@')


def test_docker_core_dependencies_are_hash_locked_for_python310_linux():
    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / 'backend/Dockerfile').read_text(encoding='utf-8')
    core = (root / 'backend/requirements-core.txt').read_text(encoding='utf-8')
    lock = (root / 'backend/requirements-docker-core-py310-linux-amd64.txt').read_text(encoding='utf-8')
    assert 'requirements-docker-core-py310-linux-amd64.txt' in dockerfile
    assert '--only-binary=:all:' in dockerfile and '--require-hashes' in dockerfile
    assert 'Target: CPython 3.10, Linux x86_64, manylinux_2_17' in lock
    lock_entries = {}
    for line in lock.splitlines():
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([^ ]+) --hash=sha256:([0-9a-f]{64})', line)
        assert match, f'Invalid hash lock line: {line}'
        name = re.sub(r'[-_.]+', '-', match.group(1)).lower()
        assert name not in lock_entries
        lock_entries[name] = match.group(2)
    direct_entries = {}
    for line in core.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([^ ]+)', line)
        assert match, f'Core requirements must remain exact pins: {line}'
        direct_entries[re.sub(r'[-_.]+', '-', match.group(1)).lower()] = match.group(2)
    assert direct_entries.items() <= lock_entries.items()
    assert len(lock_entries) >= len(direct_entries)


def test_docker_full_profile_locks_compose_ai_and_research_dependencies():
    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / 'backend/Dockerfile').read_text(encoding='utf-8')
    compose = (root / 'docker-compose.yml').read_text(encoding='utf-8')
    lock = (root / 'backend/requirements-docker-full-py310-linux-amd64.txt').read_text(encoding='utf-8')
    extras = (root / 'backend/requirements-docker-extras.txt').read_text(encoding='utf-8')
    assert 'INSTALL_PROFILE: "full"' in compose
    assert 'ARG INSTALL_PROFILE=core' in dockerfile
    assert 'requirements-docker-full-py310-linux-amd64.txt' in dockerfile
    assert 'https://download.pytorch.org/whl/cpu' in dockerfile
    assert 'https://pypi.org/simple' in dockerfile
    assert 'INSTALL_INFERENCE' not in dockerfile and 'INSTALL_RESEARCH' not in dockerfile
    assert compose.count('platform: linux/amd64') == 2
    entries = {}
    for line in lock.splitlines():
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)==([^ ]+) --hash=sha256:([0-9a-f]{64})', line)
        assert match, f'Invalid full-profile lock line: {line}'
        name = re.sub(r'[-_.]+', '-', match.group(1)).lower()
        assert name not in entries
        entries[name] = match.group(2)
    assert len(entries) == 44
    for package in ('torch', 'monai', 'scikit-learn', 'joblib'):
        assert package in entries
    assert entries['torch'] == '2.11.0+cpu'
    assert 'manylinux_2_28_x86_64' in lock and 'manylinux_2_17_x86_64' in lock
    core = (root / 'backend/requirements-core.txt').read_text(encoding='utf-8')
    for requirements in (core, extras):
        for line in requirements.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            name, version = line.split('==', 1)
            name = re.sub(r'[-_.]+', '-', name).lower()
            assert name in entries
            assert entries[name].removesuffix('+cpu') == version


def test_wheel_identity_ignores_vendored_distribution_metadata(tmp_path):
    wheel = tmp_path / 'fixture-1.2.3-py3-none-any.whl'
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('fixture-1.2.3.dist-info/METADATA', 'Name: fixture\nVersion: 1.2.3\n')
        archive.writestr('fixture/_vendor/other-4.5.dist-info/METADATA', 'Name: other\nVersion: 4.5\n')
    assert wheel_identity(wheel) == ('fixture', '1.2.3')
