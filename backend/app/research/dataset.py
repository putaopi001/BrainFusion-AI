import csv
import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
import numpy as np

DEVELOPMENT_IDS = {'4', '13', '16', '17', '19'}
CLINICAL_FEATURES = ('age', 'female')


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def numeric(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else np.nan
    except (TypeError, ValueError):
        return np.nan


@dataclass
class ResearchDataset:
    ids: list
    clinical: np.ndarray
    radiomics: np.ndarray
    labels: np.ndarray
    clinical_rows: dict
    regions: dict
    feature_names: list
    audit: dict

    def matrices(self, ids):
        clinical = np.asarray([[numeric(self.clinical_rows[i][key]) for key in CLINICAL_FEATURES] for i in ids])
        radiomics = np.asarray([[numeric(self.regions.get((i, label), {}).get(key))
                                for label in ('1', '2', '3') for key in self.feature_names] for i in ids])
        return clinical, radiomics


def load_dataset(root):
    directory = Path(root) / 'downloads'
    names = ['1_0_clinical_molecular_data.csv', '4_radiomics_preop.csv']
    tables = []
    for name in names:
        with (directory / name).open(encoding='utf-8-sig', newline='') as handle:
            tables.append(list(csv.DictReader(handle, delimiter=';')))
    clinical, rows = tables
    if len({r['id'] for r in clinical}) != len(clinical):
        raise ValueError('Duplicate clinical patient IDs')
    by_id = {r['id']: r for r in clinical}
    regions = {}
    errors = set()
    for row in rows:
        key = (row['identifier'], row['mask_label'])
        if key in regions or key[1] not in ('1', '2', '3'):
            raise ValueError('Duplicate or unsupported patient/region')
        regions[key] = row
        if any(row[k].strip() not in ('', '-', 'nan', 'NaN', 'None') for k in row if k.startswith('error.')):
            errors.add(key[0])
    candidates = {key[0] for key in regions}
    unknown = {i for i in candidates if i not in by_id or by_id[i]['idh1/2'] not in ('0', '1')}
    ids = sorted(candidates - unknown - DEVELOPMENT_IDS - errors)
    # Strict allowlists exclude pathology, molecular fields, outcomes and diagnostics.
    features = sorted(k for k in rows[0] if k.startswith('original_'))
    result = ResearchDataset(ids, np.empty(0), np.empty(0), np.asarray([int(by_id[i]['idh1/2']) for i in ids]),
                             by_id, regions, features,
                             {'clinical_rows': len(clinical), 'radiomics_rows': len(rows),
                              'radiomics_patients': len(candidates), 'cohort_patients': len(ids),
                              'unknown_label_ids': sorted(unknown), 'error_patient_ids': sorted(errors),
                              'excluded_development_ids': sorted(DEVELOPMENT_IDS),
                              'clinical_features': list(CLINICAL_FEATURES),
                              'features_per_region': len(features), 'radiomics_columns': len(features) * 3,
                              'input_sha256': {name: sha256(directory / name) for name in names},
                              'feature_source': 'published reference-mask radiomics'})
    result.clinical, result.radiomics = result.matrices(ids)
    return result
