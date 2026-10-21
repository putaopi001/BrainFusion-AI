"""Exercise actual wheel payload and reconstruction trust boundaries."""
import hashlib
from pathlib import Path
import zipfile
import pytest
from tools.bootstrap_radiomics_delivery import canonical, wheel_payload, wheel_manifest, verify_profile
from tools.prepare_radiomics_delivery import cached_upstream, docopt_wheel

def make_wheel(tmp_path,items):
    path=tmp_path/'example.whl'
    with zipfile.ZipFile(path,'w') as archive:
        for name,raw in items: archive.writestr(name,raw)
    # Windows ZipInfo normalizes backslashes when writing. Corrupt only our
    # fixture's local/central filename bytes to exercise a real hostile ZIP.
    for name,raw in items:
        if '\\' in name:
            path.write_bytes(path.read_bytes().replace(name.replace('\\','/').encode(),name.encode()))
    return path

def test_distribution_names_normalize_dots_underscores_and_hyphens():
    assert canonical('ruamel.yaml.clib')==canonical('ruamel_yaml_clib')=='ruamel-yaml-clib'

def test_payload_checks_installed_and_reference_bytes(tmp_path):
    wheel=make_wheel(tmp_path,[('radiomics/module.py',b'real module'),('example.dist-info/RECORD',b'pip rewrites')])
    for folder in ('installed','accepted'):
        target=tmp_path/folder/'Lib/site-packages/radiomics/module.py'
        target.parent.mkdir(parents=True)
        target.write_bytes(b'real module')
    values=wheel_payload(wheel,tmp_path/'installed',tmp_path/'accepted')
    assert values[0]['path']=='radiomics/module.py' and len(values)==1
    (tmp_path/'accepted/Lib/site-packages/radiomics/module.py').write_bytes(b'changed')
    with pytest.raises(ValueError,match='Accepted worker payload differs'):
        wheel_payload(wheel,tmp_path/'installed',tmp_path/'accepted')

@pytest.mark.parametrize('name',['../outside.py','C:/bad.py','folder\\bad.py'])
def test_unsafe_payload_rejected_before_installed_read(tmp_path,name):
    wheel=make_wheel(tmp_path,[(name,b'invalid')])
    with pytest.raises(ValueError,match='Unsafe archive member'):wheel_payload(wheel,tmp_path/'installed')

def test_actual_changed_installed_payload_rejected(tmp_path):
    wheel=make_wheel(tmp_path,[('module.py',b'approved')])
    target=tmp_path/'Lib/site-packages/module.py';target.parent.mkdir(parents=True);target.write_bytes(b'changed')
    with pytest.raises(ValueError,match='Installed wheel payload differs'):wheel_payload(wheel,tmp_path)

def test_external_profile_hash_checked_before_parsing_or_install(tmp_path):
    profile=tmp_path/'profile.json';profile.write_bytes(b'not valid JSON')
    with pytest.raises(ValueError,match='Trusted worker profile SHA mismatch'):
        verify_profile(profile,'0'*64)

def test_duplicate_wheel_payload_rejected(tmp_path):
    with pytest.warns(UserWarning,match='Duplicate name'):
        wheel=make_wheel(tmp_path,[('module.py',b'a'),('module.py',b'b')])
    with pytest.raises(ValueError,match='Duplicate wheel members'):wheel_payload(wheel,tmp_path)

def test_no_import_payload_is_not_accepted(tmp_path):
    wheel=make_wheel(tmp_path,[('example.dist-info/METADATA',b'only metadata')])
    with pytest.raises(ValueError,match='No checked import payload'):wheel_payload(wheel,tmp_path)

def test_frozen_payload_manifest_does_not_need_prior_environment(tmp_path):
    wheel=make_wheel(tmp_path,[('module.py',b'approved frozen module')])
    result=wheel_manifest(wheel)
    assert result[0]['sha256']==hashlib.sha256(b'approved frozen module').hexdigest()
