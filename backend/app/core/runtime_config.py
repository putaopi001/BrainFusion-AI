"""Read only an explicit runtime JSON; never execute or import its contents."""
import json
from pathlib import Path

PATH_KEYS_V1 = {'DATABASE_PATH', 'UPLOAD_DIR', 'FEATURE_JOBS_DIR', 'MODEL_DIR', 'RESEARCH_DIR',
                'DATASET_DIR', 'RADIOMICS_COMPATIBILITY', 'RADIOMICS_PYTHON'}
EXTRA_PATH_KEYS_V2 = {'PACS_CONFIG_FILE', 'PACS_IMPORT_REGISTRY_FILE', 'PACS_IMPORT_JOBS_DIR',
                      'LOCAL_AUTH_FILE', 'DICOM_CONVERSION_INDEX_FILE'}
PATH_KEYS = PATH_KEYS_V1 | EXTRA_PATH_KEYS_V2


def load_runtime_config(filename):
    filename = Path(filename).resolve(strict=True)
    value = json.loads(filename.read_text(encoding='utf-8-sig'))
    version = value.get('format_version')
    paths = value.get('paths')
    expected = PATH_KEYS_V1 if type(version) is int and version == 1 else PATH_KEYS if type(version) is int and version == 2 else None
    if expected is None or not isinstance(paths, dict) or set(paths) != expected:
        raise ValueError('Runtime config requires a supported format_version and exactly its documented path keys')
    result = {}
    for key, raw in paths.items():
        if not isinstance(raw, str) or not raw:
            raise ValueError('Invalid runtime path: ' + key)
        path = Path(raw)
        if not path.is_absolute():
            path = (filename.parent / path).resolve()
            path.relative_to(filename.parent)  # Relative config cannot escape its bundle.
        else:
            path = path.resolve()
        if path.drive and path.drive.upper() != 'E:':
            raise ValueError('This workstation stores runtime paths on E:')
        result[key] = str(path)
    return result
