"""Layer byte boundaries; real interpreter/service acceptance is separate."""
import hashlib
from pathlib import Path
import zipfile
import pytest
from tools.validate_pacs_runtime_layer import check_site


@pytest.fixture
def layer(tmp_path):
    site=tmp_path/'site';site.mkdir();wheel=tmp_path/'synthetic.whl'
    entries={'pydicom/__init__.py':b'PINNED SYNTHETIC CODE',
             'pydicom-3.0.2.dist-info/METADATA':b'SYNTHETIC METADATA',
             'pydicom-3.0.2.dist-info/RECORD':b'INSTALLER REWRITES THIS'}
    with zipfile.ZipFile(wheel,'w') as z:
        for name,raw in entries.items():
            z.writestr(name,raw);p=site/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    return site,wheel


def test_installed_code_roundtrip_and_same_size_mutation_rejected(layer):
    site,wheel=layer
    assert len(check_site(site,wheel))==3
    p=site/'pydicom/__init__.py';raw=p.read_bytes();p.write_bytes(b'X'+raw[1:])
    with pytest.raises(ValueError,match='differs from pinned wheel'):check_site(site,wheel)


@pytest.mark.parametrize('name',['arbitrary.pth','__pycache__/injected.pyc','other_package.py'])
def test_extra_import_mechanisms_are_rejected_without_mutating_layer(layer,name):
    site,wheel=layer;p=site/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'owned synthetic injection')
    before={p.relative_to(site).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in site.rglob('*') if p.is_file()}
    with pytest.raises(ValueError,match='Unexpected installed layer member'):check_site(site,wheel)
    assert before=={p.relative_to(site).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in site.rglob('*') if p.is_file()}


def test_missing_pinned_module_is_rejected(layer):
    site,wheel=layer;(site/'pydicom/__init__.py').unlink()
    with pytest.raises(ValueError,match='incomplete'):check_site(site,wheel)
