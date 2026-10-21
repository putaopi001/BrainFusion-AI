"""Run the frozen six-method, three-seed CPU federated simulation locally.

Outputs stay separate from the deployed models and original research pointer.
"""
import argparse
import csv
import hashlib
import json
import os
import platform
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[name] = '2'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import joblib
import numpy as np
import sklearn
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.research.dataset import DEVELOPMENT_IDS, load_dataset
from app.research.federated_full import METHODS, SCENARIOS, SETTINGS, evaluate_model, fit_condition


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)


def transform(preprocessing, data, ids):
    clinical, radiomics = data.matrices(ids)
    return np.column_stack([preprocessing['clinical'].transform(clinical),
                            preprocessing['radiomics'].transform(radiomics), np.ones(len(ids))])


def run(config_path, config_sha256, protocol_sha256, output):
    started = time.perf_counter()
    config_path, output = Path(config_path), Path(output)
    if output.exists():
        raise ValueError('Existing output is never overwritten')
    if output.resolve().drive.upper() != 'E:':
        raise ValueError('Outputs must remain on E:')
    protocol = Path(__file__).resolve().parents[2] / 'docs/R3_FULL_PROTOCOL.md'
    if sha(config_path) != config_sha256.lower() or sha(protocol) != protocol_sha256.lower():
        raise ValueError('Frozen configuration/protocol SHA mismatch')
    config = read(config_path)
    expected = {'protocol', 'data_root', 'split_file', 'split_sha256', 'source_summary', 'source_summary_sha256',
                'input_sha256', 'seeds', 'scenarios', 'methods', 'settings', 'selected_radiomics_features',
                'clinical_features', 'threshold', 'selection_allowed', 'evaluation_role'}
    if (set(config) != expected or config['protocol'] != 'brainfusion_federated_full_v1'
            or config['seeds'] != [20261016, 20261017, 20261018] or config['methods'] != list(METHODS)
            or config['scenarios'] != list(SCENARIOS) or config['settings'] != SETTINGS
            or config['selected_radiomics_features'] != 20 or config['clinical_features'] != ['age', 'female']
            or config['threshold'] != .5 or config['selection_allowed'] is not False
            or config['evaluation_role'] != 'already_observed_exploratory_test'):
        raise ValueError('Configuration differs from the frozen full simulation protocol')
    if sha(config['split_file']) != config['split_sha256'] or sha(config['source_summary']) != config['source_summary_sha256']:
        raise ValueError('Source split/summary SHA mismatch')
    split, source = read(config['split_file']), read(config['source_summary'])
    if split != source['split'] or split['data_sha256'] != config['input_sha256'] or source['target'] != 'idh1/2=1':
        raise ValueError('Source roles/target do not match the original exploratory cohort')
    data = load_dataset(config['data_root'])
    if data.audit['input_sha256'] != config['input_sha256']:
        raise ValueError('Source CSV SHA mismatch')
    ids = split['patient_ids']
    combined = ids['train'] + ids['validation'] + ids['test']
    if (set(ids) != {'train', 'validation', 'test'} or [len(ids[k]) for k in ('train', 'validation', 'test')] != [98, 21, 22]
            or len(set(combined)) != len(combined) or set(combined) != set(data.ids) or set(combined) & DEVELOPMENT_IDS):
        raise ValueError('Patient partitions differ, overlap, or contain excluded development patients')
    files = [config_path, protocol, Path(config['split_file']), Path(config['source_summary'])]
    files += [Path(config['data_root']) / 'downloads' / name for name in data.audit['input_sha256']]
    research_root = Path(config['split_file']).parent
    files += [research_root / 'latest.json', Path(config['source_summary']).parent / 'models.joblib']
    files += [Path(__file__).resolve()] + [Path(__file__).resolve().parents[1] / 'app/research' / name
                                         for name in ('federated_full.py', 'federated.py', 'dataset.py', 'entropy_topsis.py', 'topsis.py')]
    source_hashes = {str(path): sha(path) for path in files}
    if sha(Path(config['source_summary']).parent / 'models.joblib') != source['artifact_sha256']['models.joblib']:
        raise ValueError('Original deployed research bundle SHA mismatch')
    output.mkdir(parents=True)
    write(output / 'job.json', {'pid': os.getpid(), 'started_utc': datetime.now(timezone.utc).isoformat(),
                               'config_sha256': config_sha256.lower(), 'device': 'cpu', 'synchronous': True})
    write(output / 'config.json', config)
    preprocessing_started = time.perf_counter()
    positions = {patient: i for i, patient in enumerate(data.ids)}
    training_y = data.labels[[positions[p] for p in ids['train']]]
    validation_y = data.labels[[positions[p] for p in ids['validation']]]
    clinical, radiomics = data.matrices(ids['train'])
    preprocessing = {'clinical': make_pipeline(SimpleImputer(strategy='median', keep_empty_features=True), StandardScaler()),
                     'radiomics': make_pipeline(SimpleImputer(strategy='median', keep_empty_features=True), StandardScaler(), SelectKBest(f_classif, k=20)),
                     'training_patient_ids': ids['train'], 'feature_names': data.feature_names,
                     'source': 'published reference-mask radiomics'}
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter('always')
        preprocessing['clinical'].fit(clinical)
        preprocessing['radiomics'].fit(radiomics, training_y)
        tx, vx = transform(preprocessing, data, ids['train']), transform(preprocessing, data, ids['validation'])
    preprocessing_warnings = [{'category': type(w.message).__name__, 'message': str(w.message)} for w in seen]
    if tx.shape != (98, 23) or vx.shape != (21, 23) or not np.isfinite(tx).all() or not np.isfinite(vx).all():
        raise ValueError('Preprocessed feature contract failed')
    preprocessing['selected_radiomics_column_indices'] = preprocessing['radiomics'][-1].get_support(indices=True).tolist()
    joblib.dump(preprocessing, output / 'preprocessing.joblib', compress=3)
    preprocessing_seconds = time.perf_counter() - preprocessing_started
    training_started = time.perf_counter()
    traces, parameters, keymap = {}, {}, {}
    for seed in config['seeds']:
        for scenario in config['scenarios']:
            condition = f'{seed}_{scenario}'
            trace, models, initial = fit_condition(tx, training_y, vx, validation_y,
                train_ids=ids['train'], validation_ids=ids['validation'],
                excluded_patient_ids=ids['train'] + ids['test'] + sorted(DEVELOPMENT_IDS),
                seed=seed, scenario=scenario, settings=config['settings'])
            traces[condition] = trace
            parameters[condition + '_initial'] = initial
            keymap[condition] = {}
            for method in METHODS:
                key = condition + '__' + method
                parameters[key] = models[method]
                keymap[condition][method] = key
            print(json.dumps({'stage': 'fitted', 'seed': seed, 'scenario': scenario, 'methods': len(models)}), flush=True)
    np.savez_compressed(output / 'parameters.npz', **parameters)
    write(output / 'training-trace.json', traces)
    training_seconds = time.perf_counter() - training_started
    training_hashes = {name: sha(output / name) for name in ('preprocessing.joblib', 'parameters.npz', 'training-trace.json')}
    training_index = {'status': 'fitted_before_evaluation', 'frozen_utc': datetime.now(timezone.utc).isoformat(),
                      'artifact_sha256': training_hashes, 'parameter_keys': keymap,
                      'source_hashes': source_hashes, 'validation_patient_ids': ids['validation'],
                      'training_patient_ids': ids['train'], 'evaluation_metrics_computed': False}
    write(output / 'training-index.json', training_index)
    index_sha256 = sha(output / 'training-index.json')
    # The evaluation matrix/labels enter only after all methods, seeds and scenarios are frozen on disk.
    evaluation_started = time.perf_counter()
    ex = transform(preprocessing, data, ids['test'])
    evaluation_y = data.labels[[positions[p] for p in ids['test']]]
    if sha(output / 'preprocessing.joblib') != training_hashes['preprocessing.joblib']:
        raise ValueError('Preprocessing artifact changed before reload')
    restored = joblib.load(output / 'preprocessing.joblib')  # Only our just-written, SHA-bound local artifact.
    for subset, expected_matrix in [('train', tx), ('validation', vx), ('test', ex)]:
        np.testing.assert_array_equal(transform(restored, data, ids[subset]), expected_matrix)
    evaluations = {}
    with np.load(output / 'parameters.npz', allow_pickle=False) as loaded:
        for condition, mapping in keymap.items():
            seed = traces[condition]['seed']
            evaluations[condition] = {}
            for method, key in mapping.items():
                np.testing.assert_array_equal(loaded[key], parameters[key])
                result = evaluate_model(loaded[key], ex, evaluation_y, ids['test'], seed)
                assert result == evaluate_model(parameters[key], ex, evaluation_y, ids['test'], seed)
                evaluations[condition][method] = result
    write(output / 'evaluations.json', evaluations)
    with (output / 'predictions.csv').open('x', encoding='utf-8', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['seed', 'scenario', 'method', 'role', 'patient_id', 'simulated_center', 'target', 'probability'])
        for condition, methods in evaluations.items():
            for method, result in methods.items():
                for row in result['predictions']:
                    writer.writerow([traces[condition]['seed'], traces[condition]['scenario'], method,
                                     config['evaluation_role'], row['patient_id'], row['simulated_center'], row['target'], row['probability']])
    evaluation_seconds = time.perf_counter() - evaluation_started
    for path, digest in source_hashes.items():
        if sha(path) != digest:
            raise ValueError(f'Source changed during simulation: {path}')
    for name, digest in training_hashes.items():
        if sha(output / name) != digest:
            raise ValueError(f'Frozen training artifact changed: {name}')
    if sha(output / 'training-index.json') != index_sha256:
        raise ValueError('Training index changed during evaluation')
    result = {'status': 'passed', 'protocol': config['protocol'], 'protocol_sha256': protocol_sha256.lower(),
              'config_sha256': config_sha256.lower(), 'completed_utc': datetime.now(timezone.utc).isoformat(),
              'source_hashes': source_hashes, 'training_index_sha256': index_sha256,
              'architecture': 'homogeneous logistic model: 22 transformed features plus intercept, float64',
              'target': 'original idh1/2=1; clinical polarity unresolved', 'feature_source': data.audit['feature_source'],
              'role': config['evaluation_role'], 'seeds': config['seeds'], 'scenarios': config['scenarios'], 'methods': list(METHODS),
              'split_sizes': {name: len(values) for name, values in ids.items()}, 'device': 'cpu', 'gpu_used': False,
              'preprocessing_warnings': preprocessing_warnings,
              'timings_seconds': {'preprocessing': preprocessing_seconds, 'training': training_seconds,
                                  'evaluation_and_reload': evaluation_seconds, 'total': time.perf_counter() - started},
              'versions': {'python': platform.python_version(), 'numpy': np.__version__, 'sklearn': sklearn.__version__,
                           'blas_thread_environment': {name: os.environ[name] for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS')}},
              'summary': {condition: {method: {'pooled': result['pooled'], 'worst_center': result['worst_center'],
                                              'parameter_payload_bytes': traces[condition]['methods'][method]['parameter_payload_bytes'],
                                              'sample_gradient_evaluations': traces[condition]['methods'][method]['sample_gradient_evaluations']}
                                       for method, result in methods.items()} for condition, methods in evaluations.items()},
              'model_reload_verified': True, 'production_activated': False, 'selection_allowed': False,
              'communication_scope': 'estimated float64 model vectors only; excludes centralized preprocessing/data/public validation/control/encryption/transport',
              'limitations': ['Already observed 22-patient exploratory evaluation, no independent final test.',
                              'Training-only centralized preprocessing and a common public validation pool; no privacy guarantee.',
                              'Simulated training-label skew; evaluation center assignment uses identity hashes, not held-out labels.',
                              'Repeated validation for TOPSIS can overfit; no superiority assumed or hyperparameters selected.',
                              'No full-cohort same-protocol automatic-mask classification or clinical label polarity.',
                              'Equal sample-gradient budgets do not equate wall-clock/metric-call/proximal arithmetic budgets.'],
              'output_sha256': {name: sha(output / name) for name in ('config.json', 'job.json', 'preprocessing.joblib', 'parameters.npz', 'training-trace.json', 'training-index.json', 'evaluations.json', 'predictions.csv')}}
    write(output / 'summary.json', result)
    print(json.dumps({'stage': 'verified', 'method_fits': 36, 'distinct_evaluation_patients': 22, 'seconds': result['timings_seconds'],
                      'preprocessing_warning_count': len(preprocessing_warnings)}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--config-sha256', required=True)
    parser.add_argument('--protocol-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    run(args.config, args.config_sha256, args.protocol_sha256, args.output)


if __name__ == '__main__':
    main()
