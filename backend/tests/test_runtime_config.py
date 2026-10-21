import json
import pytest
from app.core.runtime_config import load_runtime_config, PATH_KEYS, PATH_KEYS_V1


def test_relative_runtime_config_v2_resolves_all_paths_under_bundle(tmp_path):
    paths = {key: key.lower() for key in PATH_KEYS}
    filename = tmp_path / 'runtime.json'
    filename.write_text(json.dumps({'format_version': 2, 'paths': paths}), encoding='utf-8')
    values = load_runtime_config(filename)
    assert set(values) == PATH_KEYS
    assert all(value.startswith(str(tmp_path)) for value in values.values())


def test_legacy_v1_runtime_config_remains_supported(tmp_path):
    paths = {key: key.lower() for key in PATH_KEYS_V1}
    filename = tmp_path / 'runtime-v1.json'
    filename.write_text(json.dumps({'format_version': 1, 'paths': paths}), encoding='utf-8')
    values = load_runtime_config(filename)
    assert set(values) == PATH_KEYS_V1
    assert all(value.startswith(str(tmp_path)) for value in values.values())


@pytest.mark.parametrize('mutation', ['escape', 'unknown', 'version', 'boolean_version', 'empty', 'outside_drive', 'v1_with_v2_keys'])
def test_invalid_config_rejected_before_env_or_app_write(tmp_path, mutation):
    value = {'format_version': 2, 'paths': {key: key.lower() for key in PATH_KEYS}}
    if mutation == 'escape': value['paths']['UPLOAD_DIR'] = '../outside'
    if mutation == 'unknown': value['paths']['EXECUTE'] = 'do-not-run'
    if mutation == 'version': value['format_version'] = 999
    if mutation == 'boolean_version': value['format_version'] = True
    if mutation == 'empty': value['paths']['MODEL_DIR'] = ''
    if mutation == 'outside_drive': value['paths']['LOCAL_AUTH_FILE'] = 'C:/outside/users.json'
    if mutation == 'v1_with_v2_keys': value['format_version'] = 1
    filename = tmp_path / 'runtime.json'
    filename.write_text(json.dumps(value), encoding='utf-8')
    with pytest.raises((ValueError,)):
        load_runtime_config(filename)
