"""Read-only replay of trusted local branch models on the already observed split.

No training, resplitting, latest-pointer update or production-model activation.
Only load an existing locally trusted joblib bundle after its recorded SHA matches.
"""
import argparse
import csv
import json
import os
import platform
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault('OMP_NUM_THREADS', '2')
os.environ.setdefault('MKL_NUM_THREADS', '2')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
import numpy as np
import sklearn

from app.research.dataset import DEVELOPMENT_IDS, load_dataset, sha256
from app.research.entropy_topsis import CRITERIA, apply_entropy_fusion, fit_entropy_topsis, load_entropy_state
from app.research.federated import metrics
from app.research.topsis import fuse, topsis_weights

BRANCHES = ['clinical', 'reference_mask_radiomics']


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    with path.open('x', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)


def compare(data_root, research_root, output, protocol_sha256):
    protocol = Path(__file__).resolve().parents[2] / 'docs/R2_ENTROPY_PROTOCOL.md'
    if sha256(protocol).lower() != protocol_sha256.lower():
        raise ValueError('Frozen protocol SHA mismatch')
    output = Path(output)
    if output.exists():
        raise ValueError('Output must be a new directory; existing artifacts are never overwritten')
    root = Path(research_root)
    pointer = read(root / 'latest.json')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', pointer['run_id']):
        raise ValueError('Invalid source run ID')
    source = root / pointer['run_id']
    if sha256(source / 'summary.json') != pointer['summary_sha256']:
        raise ValueError('Source summary SHA mismatch')
    summary = read(source / 'summary.json')
    if summary['target'] != 'idh1/2=1' or summary['feature_source'] != 'published reference-mask radiomics':
        raise ValueError('Unsupported source target or feature protocol')
    if summary['run_id'] != pointer['run_id']:
        raise ValueError('Run identity mismatch')
    if sha256(source / 'models.joblib') != summary['artifact_sha256']['models.joblib']:
        raise ValueError('Source model SHA mismatch')
    split = read(root / 'split_20261006.json')
    if split != summary['split']:
        raise ValueError('Source split differs from the trained-model split')
    data = load_dataset(data_root)
    if data.audit['input_sha256'] != split['data_sha256'] or data.audit['input_sha256'] != summary['audit']['input_sha256']:
        raise ValueError('Input CSV SHA differs from the original fit')
    ids = split['patient_ids']
    if set(ids) != {'train', 'validation', 'test'} or [len(ids[k]) for k in ('train', 'validation', 'test')] != [98, 21, 22]:
        raise ValueError('This replay supports only the registered 98/21/22 observed split')
    combined = ids['train'] + ids['validation'] + ids['test']
    if len(set(combined)) != len(combined) or set(combined) != set(data.ids) or set(combined) & DEVELOPMENT_IDS:
        raise ValueError('Patient partitions are not disjoint or source cohort differs')
    files = [root / 'latest.json', root / 'split_20261006.json', source / 'summary.json',
             source / 'models.joblib', source / 'predictions.csv', protocol,
             Path(__file__).resolve(), Path(__file__).resolve().parents[1] / 'app/research/entropy_topsis.py',
             Path(__file__).resolve().parents[1] / 'app/research/topsis.py',
             Path(__file__).resolve().parents[1] / 'app/research/dataset.py',
             Path(__file__).resolve().parents[1] / 'app/research/federated.py']
    files += [Path(data_root) / 'downloads' / name for name in data.audit['input_sha256']]
    source_hashes = {str(path): sha256(path) for path in files}
    # joblib can execute code: only the pre-existing trusted local bundle is permitted.
    bundle = joblib.load(source / 'models.joblib')
    if bundle['run_id'] != summary['run_id'] or bundle['data_sha256'] != data.audit['input_sha256']:
        raise ValueError('Bundle provenance mismatch')
    if bundle['feature_names'] != data.feature_names:
        raise ValueError('Bundle feature ordering differs from dataset')
    if list(bundle['models']) != BRANCHES:
        raise ValueError('Unsupported branch identities/order')
    positions = {patient: n for n, patient in enumerate(data.ids)}
    validation_rows = [positions[p] for p in ids['validation']]
    validation_inputs = data.matrices(ids['validation'])
    validation_probabilities = np.column_stack([bundle['models'][name].predict_proba(x)[:, 1]
                                               for name, x in zip(BRANCHES, validation_inputs)])
    validation_metrics = [metrics(data.labels[validation_rows], validation_probabilities[:, j]) for j in range(2)]
    for name, result in zip(BRANCHES, validation_metrics):
        for key in CRITERIA:
            np.testing.assert_allclose(result[key], summary['branch_models'][name]['validation'][key], rtol=1e-12, atol=1e-12)
    matrix = [[result[key] for key in CRITERIA] for result in validation_metrics]
    state = fit_entropy_topsis(matrix, branch_ids=BRANCHES, validation_patient_ids=ids['validation'],
                               excluded_patient_ids=ids['train'] + ids['test'] + sorted(DEVELOPMENT_IDS))
    legacy = topsis_weights(matrix)
    np.testing.assert_allclose(legacy, bundle['topsis_weights'], rtol=1e-12, atol=1e-12)
    output.mkdir(parents=True)
    write(output / 'entropy-state.json', state)
    frozen_hash = sha256(output / 'entropy-state.json')
    fitted_utc = datetime.now(timezone.utc).isoformat()
    restored = load_entropy_state(read(output / 'entropy-state.json'))
    # Only after the state is frozen/reloaded are the observed evaluation predictions used.
    evaluation_inputs = data.matrices(ids['test'])
    probabilities = np.column_stack([bundle['models'][name].predict_proba(x)[:, 1]
                                      for name, x in zip(BRANCHES, evaluation_inputs)])
    with (source / 'predictions.csv').open(encoding='utf-8-sig', newline='') as handle:
        old_rows = list(csv.DictReader(handle))
    if [row['patient_id'] for row in old_rows] != ids['test'] or any(row['subset'] != 'exploratory_test' for row in old_rows):
        raise ValueError('Original evaluation identities/roles differ')
    labels = data.labels[[positions[p] for p in ids['test']]]
    np.testing.assert_array_equal(labels, [int(row['target']) for row in old_rows])
    for j, name in enumerate(BRANCHES):
        np.testing.assert_allclose(probabilities[:, j], [float(row[name]) for row in old_rows], rtol=1e-12, atol=1e-12)
    entropy = apply_entropy_fusion(restored, probabilities, branch_ids=BRANCHES)
    methods = {'clinical': ([1., 0.], probabilities[:, 0]),
               'reference_mask_radiomics': ([0., 1.], probabilities[:, 1]),
               'average': ([.5, .5], fuse(probabilities, [.5, .5])),
               'fixed_clinical_0.6_radiomics_0.4': ([.6, .4], fuse(probabilities, [.6, .4])),
               'validation_topsis': (legacy.tolist(), fuse(probabilities, legacy)),
               'validation_entropy_topsis': (state['branch_weights'], np.asarray(entropy['probabilities']))}
    results = {name: {'weights': weights, 'exploratory_test': metrics(labels, predictions)}
               for name, (weights, predictions) in methods.items()}
    for name in BRANCHES:
        for key in CRITERIA:
            np.testing.assert_allclose(results[name]['exploratory_test'][key], summary['branch_models'][name]['test'][key], rtol=1e-12, atol=1e-12)
    for name in ('average', 'fixed_clinical_0.6_radiomics_0.4', 'validation_topsis'):
        for key in CRITERIA:
            np.testing.assert_allclose(results[name]['exploratory_test'][key], summary['fusion'][name]['test'][key], rtol=1e-12, atol=1e-12)
    with (output / 'predictions.csv').open('x', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['patient_id', 'role', 'target'] + list(methods))
        for row, patient in enumerate(ids['test']):
            writer.writerow([patient, 'already_observed_exploratory_test', int(labels[row])] +
                            [float(predictions[row]) for _, predictions in methods.values()])
    write(output / 'application-audit.json', entropy)
    if sha256(output / 'entropy-state.json') != frozen_hash:
        raise ValueError('Fitted entropy state changed during evaluation')
    for path, digest in source_hashes.items():
        if sha256(path) != digest:
            raise ValueError(f'Source changed during replay: {path}')
    result = {'status': 'passed', 'protocol_sha256': protocol_sha256.lower(), 'source_run_id': summary['run_id'],
              'fitted_before_evaluation_utc': fitted_utc, 'completed_utc': datetime.now(timezone.utc).isoformat(),
              'target': 'original idh1/2=1, clinical polarity unresolved', 'feature_source': summary['feature_source'],
              'role': 'already observed exploratory split; no independent evaluation', 'split_sizes': {k: len(v) for k, v in ids.items()},
              'source_hashes': source_hashes, 'state_sha256': frozen_hash, 'validation_metrics': validation_metrics,
              'methods': results, 'fit_reasons': state['reasons'], 'criterion_weights': state['criterion_weights'],
              'source_artifacts_unchanged': True, 'training_performed': False, 'production_activated': False,
              'versions': {'python': platform.python_version(), 'numpy': np.__version__, 'sklearn': sklearn.__version__},
              'limitations': ['Entropy dispersion is not demonstrated criterion reliability; two branches are unstable.',
                              'Reference masks only, no full-cohort same-protocol automatic-mask comparison.',
                              'No patient confidence/clinical interpretation, calibration, intervals or independence claim.',
                              'No superiority assumed; zeros and adverse comparisons retained.']}
    write(output / 'comparison.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', required=True)
    parser.add_argument('--research-root', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--protocol-sha256', required=True)
    args = parser.parse_args()
    result = compare(args.data_root, args.research_root, args.output, args.protocol_sha256)
    print(json.dumps({'status': result['status'], 'output': args.output, 'methods': result['methods']}, indent=2))


if __name__ == '__main__':
    main()
