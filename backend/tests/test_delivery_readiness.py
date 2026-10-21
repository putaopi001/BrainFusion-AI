import hashlib
import json
import sqlite3
import zipfile
import pytest
from tools.verify_delivery_readiness import database_signatures, delivery_gaps, sha256, source_changes, verify_archive, verify_files, verify_worker_locks


def entry(name, content):
    return dict(path=name, bytes=len(content), sha256=hashlib.sha256(content).hexdigest())


def test_archive_roundtrip_is_read_only_and_rejects_payload_drift(tmp_path):
    archive = tmp_path / 'candidate.zip'
    with zipfile.ZipFile(archive, 'w') as stream:
        stream.writestr('source/example.py', b'print(1)')
    checksum = sha256(archive)
    assert verify_archive(archive, [entry('source/example.py', b'print(1)')], checksum)['no_extraction']
    assert not (tmp_path / 'source').exists()
    with pytest.raises(ValueError, match='member checksum'):
        verify_archive(archive, [entry('source/example.py', b'print(2)')], checksum)


@pytest.mark.parametrize('name', ['../escape.py', 'C:/outside.py', 'source\\bad.py'])
def test_unsafe_manifest_paths_are_rejected(tmp_path, name):
    archive = tmp_path / 'candidate.zip'
    with zipfile.ZipFile(archive, 'w') as stream:
        stream.writestr(name, b'x')
    with pytest.raises(ValueError, match='Unsafe'):
        verify_archive(archive, [entry(name, b'x')], sha256(archive))


def test_unlisted_and_duplicate_archive_members_are_rejected(tmp_path):
    archive = tmp_path / 'candidate.zip'
    with zipfile.ZipFile(archive, 'w') as stream:
        stream.writestr('README.md', b'x')
        stream.writestr('database.db', b'unlisted')
    with pytest.raises(ValueError, match='member set'):
        verify_archive(archive, [entry('README.md', b'x')], sha256(archive))
    with pytest.raises(ValueError, match='Duplicate'):
        verify_archive(archive, [entry('README.md', b'x')] * 2, sha256(archive))


def test_historical_source_is_not_misreported_as_current():
    old = [entry('same.py', b'0'), entry('changed.py', b'1'), entry('removed.py', b'2')]
    new = [entry('same.py', b'0'), entry('changed.py', b'2'), entry('added.py', b'3')]
    result = source_changes(old, new)
    assert result == dict(added=['added.py'], removed=['removed.py'], changed=['changed.py'], unchanged=1, is_current=False)
    assert source_changes(new, new)['is_current']


def test_missing_database_is_not_created_and_active_tasks_reject(tmp_path):
    path = tmp_path / 'test.db'
    with pytest.raises(FileNotFoundError):
        database_signatures(path)
    assert not path.exists()
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE analysis_runs (id INTEGER, state TEXT)')
        db.execute("INSERT INTO analysis_runs VALUES (1, 'succeeded')")
    original = sha256(path)
    assert database_signatures(path)['analysis_runs']['rows'] == 1
    assert sha256(path) == original
    with sqlite3.connect(path) as db:
        db.execute("UPDATE analysis_runs SET state='running'")
    with pytest.raises(ValueError, match='Active analysis'):
        database_signatures(path)


def test_material_source_drift_is_rejected_without_changing_file(tmp_path):
    path = tmp_path / 'script.py'
    path.write_bytes(b'print(1)')
    original = sha256(path)
    verify_files(tmp_path, [entry('script.py', b'print(1)')])
    with pytest.raises(ValueError, match='evidence file changed'):
        verify_files(tmp_path, [entry('script.py', b'print(2)')])
    assert sha256(path) == original


def test_worker_lock_text_drift_rejects_without_installation(tmp_path):
    wheel = tmp_path / 'example.whl'; wheel.write_bytes(b'synthetic wheel')
    source_path = tmp_path / 'source.json'
    conda = [dict(url='https://conda.anaconda.org/conda-forge/win-64/example.conda', sha256='a' * 64)]
    pip = [dict(name='example', version='1.0', url='https://files.pythonhosted.org/example.whl', sha256='b' * 64)]
    source = dict(conda_packages=conda, wheel=str(wheel), wheel_sha256=sha256(wheel),
                  pypi_dependencies=[dict(metadata=dict(name='example', version='1.0'),
                      download_info=dict(url=pip[0]['url'], archive_info=dict(hashes=dict(sha256=pip[0]['sha256']))))])
    source_path.write_text(json.dumps(source), encoding='utf-8')
    (tmp_path / 'validation.json').write_text(json.dumps(dict(status='passed', source_sha256=sha256(source_path), conda_packages=conda,
        pip_packages=pip, wheel=dict(sha256=sha256(wheel), bytes=wheel.stat().st_size))), encoding='utf-8')
    (tmp_path / 'conda-explicit.txt').write_text('@EXPLICIT\n' + conda[0]['url'] + '#sha256:' + conda[0]['sha256'] + '\n', encoding='utf-8')
    (tmp_path / 'pip-dependencies.txt').write_text('example @ ' + pip[0]['url'] + ' --hash=sha256:' + pip[0]['sha256'] + '\n', encoding='utf-8')
    (tmp_path / 'pyradiomics-wheel.txt').write_text('pyradiomics @ ' + wheel.as_uri() + ' --hash=sha256:' + sha256(wheel) + '\n', encoding='utf-8')
    assert verify_worker_locks(source_path, tmp_path)['no_install_or_network']
    (tmp_path / 'conda-explicit.txt').write_text('@EXPLICIT\n', encoding='utf-8')
    with pytest.raises(ValueError, match='CPU lock text changed'):
        verify_worker_locks(source_path, tmp_path)


def test_current_delivery_gaps_match_unfinished_scope():
    gaps = delivery_gaps(source_is_current=True)
    assert not any('E5' in item or 'Docker/Linux' in item for item in gaps)
    assert any('four-sequence DICOM' in item for item in gaps)
    assert any('mentor rehearsal' in item for item in gaps)
    historical = delivery_gaps(source_is_current=False)
    assert any('Source ZIP differs' in item for item in historical)
