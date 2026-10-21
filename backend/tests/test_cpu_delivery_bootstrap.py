from io import BytesIO
import hashlib
import zipfile
import pytest
from tools.bootstrap_cpu_delivery import members, safe_member, verify_bundle, fresh, verify_cache


@pytest.mark.parametrize('path',['../model.pt','C:/patient.db','/absolute.py','folder\\script.py','a/../b.py','a//b.py'])
def test_unsafe_zip_paths_rejected(path):
    with pytest.raises(ValueError):safe_member(path)


def archive(items):
    value=BytesIO()
    with zipfile.ZipFile(value,'w') as z:
        for name,raw in items:z.writestr(name,raw)
    value.seek(0)
    return zipfile.ZipFile(value)


def entry(name,raw):return dict(path=name,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def test_rogue_member_and_changed_member_rejected_without_extraction():
    with archive([('app.py',b'code'),('unexpected.py',b'execute')]) as z:
        with pytest.raises(ValueError,match='set mismatch'):members(z,[entry('app.py',b'code')])
    with archive([('app.py',b'changed')]) as z:
        with pytest.raises(ValueError,match='checksum'):members(z,[entry('app.py',b'code')])


def test_duplicate_and_symlink_members_rejected():
    with pytest.warns(UserWarning,match='Duplicate name'):
        duplicate=archive([('app.py',b'a'),('app.py',b'a')])
    with duplicate as z:
        with pytest.raises(ValueError,match='set mismatch'):members(z,[entry('app.py',b'a')])
    value=BytesIO()
    with zipfile.ZipFile(value,'w') as z:
        info=zipfile.ZipInfo('app.py');info.external_attr=(0o120777<<16);z.writestr(info,b'target')
    value.seek(0)
    with zipfile.ZipFile(value) as z:
        with pytest.raises(ValueError,match='symlink'):members(z,[entry('app.py',b'target')])


def test_untrusted_bundle_sha_is_rejected_before_unzip(tmp_path):
    path=tmp_path/'bundle.zip';path.write_bytes(b'not a zip')
    with pytest.raises(ValueError,match='external bundle SHA'):verify_bundle(path,'a'*64)


def test_existing_owned_prefix_and_outside_targets_are_rejected(tmp_path):
    with pytest.raises(ValueError,match='Fresh owned'):fresh(tmp_path,tmp_path.parent)
    with pytest.raises(ValueError):fresh(tmp_path.parent/'other',tmp_path)


def test_modified_cache_file_is_rejected_without_environment_write(tmp_path):
    wheel=tmp_path/'safe-1.0-py3-none-any.whl';wheel.write_bytes(b'bad')
    lock=dict(packages=[dict(name='safe',filename=wheel.name,url='https://files.pythonhosted.org/'+wheel.name,bytes=3,sha256='a'*64)],conda_bootstrap=[])
    with pytest.raises(ValueError,match='Missing/changed'):verify_cache(lock,tmp_path,tmp_path)
    assert list(tmp_path.iterdir())==[wheel]
