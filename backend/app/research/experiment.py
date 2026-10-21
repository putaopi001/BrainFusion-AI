import json
import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import joblib
import numpy as np
import sklearn
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from .dataset import DEVELOPMENT_IDS, load_dataset, sha256
from .federated import metrics, probability, simulate
from .topsis import fuse, topsis_weights

SEED = 20261006


def split_dataset(dataset, path):
    train, remaining = train_test_split(np.arange(len(dataset.ids)), test_size=.3, stratify=dataset.labels, random_state=SEED)
    validation, test = train_test_split(remaining, test_size=.5, stratify=dataset.labels[remaining], random_state=SEED)
    split = {'seed': SEED, 'data_sha256': dataset.audit['input_sha256'],
             'patient_ids': {name: [dataset.ids[i] for i in index] for name, index in [('train', train), ('validation', validation), ('test', test)]},
             'evaluation_status': 'exploratory: this split was already inspected in the earlier in-memory prototype'}
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8')) != split:
            raise ValueError('Frozen split or source data changed; create a documented new protocol')
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8') as handle:
            json.dump(split, handle, ensure_ascii=False, indent=2)
    return train, validation, test, split


def run_experiment(data_root, output_root, rounds=3, local_steps=2):
    if not 1 <= rounds <= 10 or not 1 <= local_steps <= 10:
        raise ValueError('Smoke experiments allow at most 10 rounds and 10 local steps')
    started = time.perf_counter()
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid4().hex[:8]
    directory = root / run_id
    directory.mkdir()
    dataset = load_dataset(data_root)
    train, validation, test, split = split_dataset(dataset, root / 'split_20261006.json')
    models = {
        'clinical': make_pipeline(SimpleImputer(strategy='median', keep_empty_features=True), StandardScaler(),
                                 LogisticRegression(C=.1, class_weight='balanced', max_iter=1000, random_state=SEED)),
        'reference_mask_radiomics': make_pipeline(SimpleImputer(strategy='median', keep_empty_features=True), StandardScaler(),
                                                SelectKBest(f_classif, k=20), LogisticRegression(C=.1, class_weight='balanced', max_iter=1000, random_state=SEED))}
    values = {'clinical': dataset.clinical, 'reference_mask_radiomics': dataset.radiomics}
    scores, validation_probabilities, test_probabilities = {}, [], []
    for name, model in models.items():
        model.fit(values[name][train], dataset.labels[train])
        val = model.predict_proba(values[name][validation])[:, 1]
        tested = model.predict_proba(values[name][test])[:, 1]
        validation_probabilities.append(val)
        test_probabilities.append(tested)
        scores[name] = {'validation': metrics(dataset.labels[validation], val), 'test': metrics(dataset.labels[test], tested)}
    criteria = [[scores[name]['validation'][key] for key in ('auc', 'balanced_accuracy', 'brier')] for name in models]
    weights = topsis_weights(criteria)
    fusion = {}
    for name, choice in [('average', [.5, .5]), ('fixed_clinical_0.6_radiomics_0.4', [.6, .4]), ('validation_topsis', weights)]:
        fusion[name] = {'weights': list(map(float, choice)), 'test': metrics(dataset.labels[test], fuse(np.asarray(test_probabilities).T, choice))}
    clinical_pre = make_pipeline(SimpleImputer(strategy='median', keep_empty_features=True), StandardScaler())
    radio_pre = make_pipeline(SimpleImputer(strategy='median', keep_empty_features=True), StandardScaler(), SelectKBest(f_classif, k=20))
    clinical_pre.fit(dataset.clinical[train], dataset.labels[train])
    radio_pre.fit(dataset.radiomics[train], dataset.labels[train])
    federation_features = np.column_stack([clinical_pre.transform(dataset.clinical), radio_pre.transform(dataset.radiomics), np.ones(len(dataset.ids))])
    federated, parameters = simulate(federation_features, dataset.labels, train, validation, test, dataset.ids, SEED, rounds, local_steps)
    bundle = {'models': models, 'topsis_weights': weights, 'clinical_preprocessor': clinical_pre,
              'radiomics_preprocessor': radio_pre, 'federated_parameters': parameters,
              'feature_names': dataset.feature_names, 'data_sha256': dataset.audit['input_sha256'], 'run_id': run_id}
    joblib.dump(bundle, directory / 'models.joblib', compress=3)
    loaded = joblib.load(directory / 'models.joblib')
    demo_ids = sorted(DEVELOPMENT_IDS)
    demo_clinical, demo_radio = dataset.matrices(demo_ids)
    branch = np.column_stack([loaded['models'][name].predict_proba(x)[:, 1] for name, x in zip(models, [demo_clinical, demo_radio])])
    if not np.isfinite(branch).all() or ((branch < 0) | (branch > 1)).any():
        raise ValueError('Invalid development predictions after model reload')
    for name, x in zip(models, [demo_clinical, demo_radio]):
        np.testing.assert_allclose(loaded['models'][name].predict_proba(x), models[name].predict_proba(x))
    restored_features = np.column_stack([loaded['clinical_preprocessor'].transform(dataset.clinical[test]),
                                        loaded['radiomics_preprocessor'].transform(dataset.radiomics[test]), np.ones(len(test))])
    for name, fitted in parameters.items():
        np.testing.assert_allclose(probability(restored_features, loaded['federated_parameters'][name]),
                                   probability(federation_features[test], fitted))
    demo = {patient: {'clinical': float(branch[i, 0]), 'reference_mask_radiomics': float(branch[i, 1]),
                      'average': float(branch[i].mean()), 'validation_topsis': float(branch[i] @ weights),
                      'reference_label': int(dataset.clinical_rows[patient]['idh1/2']) if dataset.clinical_rows[patient]['idh1/2'] in ('0', '1') else None,
                      'subset': 'development, excluded from fitting/validation/test'} for i, patient in enumerate(demo_ids)}
    summary = {'status': 'succeeded', 'run_id': run_id, 'created_utc': datetime.now(timezone.utc).isoformat(),
               'target': 'idh1/2=1', 'feature_source': 'published reference-mask radiomics', 'device': 'cpu', 'gpu_used': False,
               'audit': dataset.audit, 'split': split, 'split_sizes': {key: len(ids) for key, ids in split['patient_ids'].items()},
               'branch_models': scores, 'fusion': fusion, 'federated': federated, 'development_predictions': demo,
               'verification': {'model_reload': 'passed', 'federated_reload': 'passed', 'five_development_inputs': 'passed', 'patient_partition': 'passed'},
               'versions': {'python': platform.python_version(), 'numpy': np.__version__, 'sklearn': sklearn.__version__},
               'protocol': {'logistic_C': .1, 'threshold': .5, 'selected_radiomics_features': 20, 'criteria': ['validation_auc_benefit', 'validation_balanced_accuracy_benefit', 'validation_brier_cost']},
               'limitations': ['Reference masks were used to derive published radiomics; not automatic segmentation end-to-end accuracy.',
                               'Single small split already inspected; all metrics are exploratory, no external validation.',
                               'Federated simulation centrally fits training preprocessing and uses a common validation pool; no privacy guarantee.',
                               'TOPSIS can assign zero weight or collapse to one branch; superiority is not assumed.'],
               'seconds': round(time.perf_counter() - started, 3), 'artifact_sha256': {'models.joblib': sha256(directory / 'models.joblib')}}
    (directory / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    with (directory / 'predictions.csv').open('w', encoding='utf-8', newline='') as handle:
        import csv
        writer = csv.writer(handle)
        writer.writerow(['patient_id', 'subset', 'target', 'clinical', 'reference_mask_radiomics', 'average', 'fixed', 'topsis'])
        for n, index in enumerate(test):
            c, r = test_probabilities[0][n], test_probabilities[1][n]
            writer.writerow([dataset.ids[index], 'exploratory_test', int(dataset.labels[index]), c, r, (c + r) / 2, .6 * c + .4 * r, c * weights[0] + r * weights[1]])
    # Publish only after every model/artifact and reload check succeeds.
    pointer = root / ('latest_' + run_id + '.tmp')
    pointer.write_text(json.dumps({'run_id': run_id, 'summary_sha256': sha256(directory / 'summary.json')}), encoding='utf-8')
    os.replace(pointer, root / 'latest.json')
    return summary
