import json
import re
from functools import lru_cache
from pathlib import Path
from app.core.config import settings
from app.research.dataset import DEVELOPMENT_IDS, load_dataset, sha256


def current_summary():
    root = Path(settings.RESEARCH_DIR)
    pointer = json.loads((root / 'latest.json').read_text(encoding='utf-8'))
    run_id = pointer['run_id']
    if not re.fullmatch(r'\d{8}T\d{6}Z_[0-9a-f]{8}', run_id):
        raise ValueError('Invalid research artifact ID')
    path = root / run_id / 'summary.json'
    if sha256(path) != pointer['summary_sha256']:
        raise ValueError('Research summary checksum mismatch')
    summary = json.loads(path.read_text(encoding='utf-8'))
    if summary['run_id'] != run_id or summary['status'] != 'succeeded':
        raise ValueError('Research experiment is incomplete')
    return summary, path.parent


@lru_cache(maxsize=2)
def _bundle(path, modified, size, expected):
    # Only locally produced, checksum-verified artifacts; no pickle uploads.
    if sha256(path) != expected:
        raise ValueError('Research model checksum mismatch')
    import joblib
    return joblib.load(path)


def current_bundle():
    summary, directory = current_summary()
    path = directory / 'models.joblib'
    stat = path.stat()
    bundle = _bundle(str(path), stat.st_mtime_ns, stat.st_size, summary['artifact_sha256']['models.joblib'])
    if bundle['run_id'] != summary['run_id']:
        raise ValueError('Research model version mismatch')
    return summary, bundle


@lru_cache(maxsize=1)
def _dataset(root, fingerprints):
    return load_dataset(root)


def predict_development(patient_id):
    if patient_id not in DEVELOPMENT_IDS:
        raise KeyError('Choose one of the five development source patient IDs')
    summary, bundle = current_bundle()
    root = Path(settings.DATASET_DIR)
    fingerprints = tuple((name, (root / 'downloads' / name).stat().st_mtime_ns,
                          (root / 'downloads' / name).stat().st_size) for name in bundle['data_sha256'])
    dataset = _dataset(str(root), fingerprints)
    if dataset.audit['input_sha256'] != bundle['data_sha256']:
        raise ValueError('Dataset changed since model fitting')
    clinical, radio = dataset.matrices([patient_id])
    c = float(bundle['models']['clinical'].predict_proba(clinical)[0, 1])
    r = float(bundle['models']['reference_mask_radiomics'].predict_proba(radio)[0, 1])
    return {'source_patient_id': patient_id, 'run_id': summary['run_id'], 'target': summary['target'],
            'subset': 'development, excluded from training/validation/test',
            'feature_source': 'published reference-mask radiomics',
            'clinical_input': {'age': float(clinical[0, 0]), 'female': int(clinical[0, 1])},
            'probabilities': {'clinical': c, 'reference_mask_radiomics': r, 'average': (c + r) / 2,
                              'fixed': .6 * c + .4 * r, 'validation_topsis': float(c * bundle['topsis_weights'][0] + r * bundle['topsis_weights'][1])},
            'topsis_weights': bundle['topsis_weights'].tolist(),
            'reference_label': summary['development_predictions'][patient_id]['reference_label'],
            'disclaimer': '研究概率，未校准；影像组学来自参考掩膜，非当前病例自动分割结果。'}


def predict_clinical(age, female):
    summary, bundle = current_bundle()
    return {'run_id': summary['run_id'], 'target': summary['target'],
            'probability': float(bundle['models']['clinical'].predict_proba([[age, int(female)]])[0, 1]),
            'inputs': {'age': age, 'female': female}, 'source': 'fitted clinical logistic model',
            'disclaimer': '仅年龄与性别的研究基线概率，未校准，不能诊断 IDH 状态。'}
