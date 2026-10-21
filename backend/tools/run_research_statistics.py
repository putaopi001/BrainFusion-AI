"""Frozen, posthoc patient-level statistics and exact per-model logit accounting.

No retraining of predictors, new cohort selection, or production activation.
"""
import argparse
import csv
import hashlib
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[key] = '2'
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import joblib
import numpy as np
import scipy
import sklearn

from app.research.dataset import DEVELOPMENT_IDS, load_dataset
from app.research.federated import probability
from app.research.federated_full import METHODS, SCENARIOS, assign_centers
from app.research.patient_statistics import (METRICS, additive_logistic_explanation, apply_temperature,
    bootstrap_metrics, fit_temperature, paired_difference, reliability_bins, stratified_patient_indices)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)


def transformed(preprocessing, data, ids):
    clinical, radio = data.matrices(ids)
    return np.column_stack([preprocessing['clinical'].transform(clinical), preprocessing['radiomics'].transform(radio), np.ones(len(ids))])


def predict(parameters, x, ids, seed):
    if parameters.ndim == 1:
        return probability(x, parameters)
    centers = assign_centers(ids, seed)
    return np.asarray([probability(x[i:i+1], parameters[centers[i]])[0] for i in range(len(ids))])


def run(config_path, config_sha256, protocol_sha256, output):
    started = time.perf_counter()
    config_path, output = Path(config_path), Path(output)
    if output.exists():
        raise ValueError('Existing output is never overwritten')
    if output.resolve().drive.upper() != 'E:':
        raise ValueError('Outputs must remain on E:')
    protocol = Path(__file__).resolve().parents[2] / 'docs/R4_STATISTICS_PROTOCOL.md'
    if sha(config_path) != config_sha256.lower() or sha(protocol) != protocol_sha256.lower():
        raise ValueError('Frozen protocol/configuration SHA mismatch')
    config = read(config_path)
    expected_keys = {'protocol', 'source_directory', 'source_sha256', 'bootstrap_samples', 'bootstrap_seed',
                     'confidence_level', 'reliability_bins', 'seed_aggregation', 'temperature', 'primary',
                     'selection_allowed', 'evaluation_role'}
    if (set(config) != expected_keys or config['protocol'] != 'brainfusion_patient_statistics_v1'
            or config['bootstrap_samples'] != 2000 or config['bootstrap_seed'] != 20261016
            or config['confidence_level'] != .95 or config['reliability_bins'] != 5
            or config['seed_aggregation'] != 'patient_probability_mean'
            or config['temperature'] != {'log_bounds': [-3., 3.], 'epsilon': 1e-6, 'xatol': 1e-8, 'maxiter': 200}
            or config['primary'] != {'scenario': 'iid', 'left': 'fedprox', 'right': 'fedavg', 'metric': 'auc', 'version': 'uncalibrated'}
            or config['selection_allowed'] is not False or config['evaluation_role'] != 'already_observed_exploratory_test'):
        raise ValueError('Configuration differs from the frozen statistical protocol')
    source = Path(config['source_directory'])
    if output.resolve().is_relative_to(source.resolve()):
        raise ValueError('Output cannot modify source model artifacts')
    required = {'summary': 'summary.json', 'training_index': 'training-index.json', 'parameters': 'parameters.npz',
                'preprocessing': 'preprocessing.joblib', 'predictions': 'predictions.csv'}
    if set(config['source_sha256']) != set(required):
        raise ValueError('Incomplete source binding')
    for name, filename in required.items():
        if sha(source / filename) != config['source_sha256'][name]:
            raise ValueError('Source artifact SHA mismatch: ' + name)
    r3 = read(source / 'summary.json')
    if (r3['status'] != 'passed' or r3['role'] != config['evaluation_role'] or r3['seeds'] != [20261016,20261017,20261018]
            or r3['scenarios'] != list(SCENARIOS) or r3['methods'] != list(METHODS) or r3['production_activated'] is not False):
        raise ValueError('Source cohort/method role differs from the accepted exploratory model')
    source_hashes = dict(r3['source_hashes'])
    source_hashes.update({str(source / filename): digest for filename, digest in r3['output_sha256'].items()})
    source_hashes[str(source / 'summary.json')] = sha(source / 'summary.json')
    for path, digest in source_hashes.items():
        if sha(path) != digest:
            raise ValueError('Source lineage changed: ' + path)
    source_config = read(source / 'config.json')
    split = read(source_config['split_file'])
    data = load_dataset(source_config['data_root'])
    ids = split['patient_ids']
    combined = ids['train'] + ids['validation'] + ids['test']
    if (data.audit['input_sha256'] != source_config['input_sha256'] or len(set(combined)) != 141
            or set(combined) != set(data.ids) or set(combined) & DEVELOPMENT_IDS
            or [len(ids[k]) for k in ('train','validation','test')] != [98,21,22]):
        raise ValueError('Patient roles or CSV lineage differ')
    pre = joblib.load(source / 'preprocessing.joblib')  # Existing locally trusted SHA-bound artifact only.
    if pre['training_patient_ids'] != ids['train']:
        raise ValueError('Preprocessing was not bound to the original training patients')
    positions = {p:i for i,p in enumerate(data.ids)}
    vy = data.labels[[positions[p] for p in ids['validation']]]
    vx = transformed(pre, data, ids['validation'])
    index = read(source / 'training-index.json')
    if index['evaluation_metrics_computed'] is not False or sha(source / 'training-index.json') != r3['training_index_sha256']:
        raise ValueError('Original training freeze is not consistent')
    output.mkdir(parents=True)
    write(output / 'config.json', config)
    write(output / 'job.json', {'pid': os.getpid(), 'started_utc': datetime.now(timezone.utc).isoformat(),
                               'predictor_training': False, 'temperature_fitting': '21 validation patients only'})
    calibration = {}
    with np.load(source / 'parameters.npz', allow_pickle=False) as models:
        for scenario in SCENARIOS:
            for method in METHODS:
                key = scenario + '__' + method
                vp = np.mean([predict(models[index['parameter_keys'][f'{seed}_{scenario}'][method]], vx, ids['validation'], seed)
                              for seed in r3['seeds']], axis=0)
                calibration[key] = fit_temperature(vp, vy, validation_ids=ids['validation'],
                                                   excluded_ids=ids['train'] + ids['test'] + sorted(DEVELOPMENT_IDS))
        write(output / 'temperature-states.json', calibration)
        calibration_sha = sha(output / 'temperature-states.json')
        write(output / 'calibration-index.json', {'frozen_utc': datetime.now(timezone.utc).isoformat(),
            'states_sha256': calibration_sha, 'state_count': 12, 'fit_patient_count': 21,
            'evaluation_metrics_computed': False, 'fit_role': 'validation', 'source_parameter_sha256': config['source_sha256']['parameters']})
        calibration = read(output / 'temperature-states.json')
        # Evaluation matrices/labels enter after freezing all validation calibration states.
        ex = transformed(pre, data, ids['test'])
        ey = data.labels[[positions[p] for p in ids['test']]]
        with (source / 'predictions.csv').open(encoding='utf-8-sig', newline='') as handle:
            old = list(csv.DictReader(handle))
        if len(old) != 792 or any(row['role'] != config['evaluation_role'] for row in old):
            raise ValueError('Original prediction rows have an unsupported role/count')
        lookup = {(int(row['seed']), row['scenario'], row['method'], row['patient_id']): row for row in old}
        if len(lookup) != 792:
            raise ValueError('Original prediction rows contain duplicates')
        indices = stratified_patient_indices(ey, samples=config['bootstrap_samples'], seed=config['bootstrap_seed'])
        np.save(output / 'patient-bootstrap-indices.npy', indices, allow_pickle=False)
        selected = pre['selected_radiomics_column_indices']
        per_region = len(pre['feature_names'])
        feature_names = ['clinical:age', 'clinical:female'] + [f"radiomics:region{j // per_region + 1}:{pre['feature_names'][j % per_region]}" for j in selected]
        if ex.shape[1] != 23 or len(feature_names) != 22:
            raise ValueError('Explanation feature layout differs from the trained 23-parameter model')
        statistics, draws, probability_rows, explanations, temperature_audit, results = {}, {}, [], [], {}, {}
        for scenario in SCENARIOS:
            for method in METHODS:
                base_key = scenario + '__' + method
                seed_predictions = []
                for seed in r3['seeds']:
                    parameter_key = index['parameter_keys'][f'{seed}_{scenario}'][method]
                    parameter = models[parameter_key]
                    ep = predict(parameter, ex, ids['test'], seed)
                    centers = assign_centers(ids['test'], seed)
                    for i, patient in enumerate(ids['test']):
                        saved = lookup[(seed, scenario, method, patient)]
                        if int(saved['target']) != int(ey[i]) or int(saved['simulated_center']) != centers[i]:
                            raise ValueError('Original patient target/center differs')
                        np.testing.assert_allclose(ep[i], float(saved['probability']), rtol=0, atol=1e-14)
                        coefficients = parameter if parameter.ndim == 1 else parameter[centers[i]]
                        explained = additive_logistic_explanation(ex[i,:-1], coefficients, feature_names)
                        np.testing.assert_allclose(explained['probability'], ep[i], rtol=0, atol=1e-12)
                        explanations.append({'seed': seed, 'scenario': scenario, 'method': method, 'patient_id': patient,
                            'simulated_center': int(centers[i]), 'parameter_key': parameter_key,
                            'source_npz_sha256': config['source_sha256']['parameters'], **explained})
                    seed_predictions.append(ep)
                mean_p = np.mean(seed_predictions, axis=0)
                calibrated, audit = apply_temperature(calibration[base_key], mean_p)
                temperature_audit[base_key] = audit
                for version, p in [('uncalibrated', mean_p), ('temperature_calibrated', calibrated)]:
                    key = base_key + '__' + version
                    result = bootstrap_metrics(ey, p, ids['test'], indices)
                    results[key] = result
                    draws[key] = result['samples']
                    statistics[key] = {**{name: value for name, value in result.items() if name != 'samples'},
                                       'reliability_bins': reliability_bins(ey, p), 'role': config['evaluation_role'],
                                       'seed_aggregation': config['seed_aggregation']}
                    probability_rows += [{'scenario':scenario,'method':method,'version':version,'patient_id':patient,
                        'target':int(ey[i]),'probability':float(p[i]),'role':config['evaluation_role']} for i,patient in enumerate(ids['test'])]
    comparisons = {}
    for scenario,left,right,tier in [('iid','fedprox','fedavg','primary'),('label_skew','fedprox','fedavg','secondary'),
                                    ('iid','validation_entropy_topsis','fedavg','secondary'),('label_skew','validation_entropy_topsis','fedavg','secondary')]:
        key = f'{scenario}__{left}_minus_{right}'
        comparisons[key] = {'tier':tier,'version':'uncalibrated',**paired_difference(results[scenario+'__'+left+'__uncalibrated'],results[scenario+'__'+right+'__uncalibrated'])}
    calibration_comparisons = {key: paired_difference(results[key+'__temperature_calibrated'],results[key+'__uncalibrated']) for key in calibration}
    write(output / 'statistics.json', statistics)
    write(output / 'paired-comparisons.json', comparisons)
    write(output / 'calibration-comparisons.json', calibration_comparisons)
    write(output / 'temperature-application.json', temperature_audit)
    write(output / 'per-model-explanations.json', explanations)
    np.savez_compressed(output / 'bootstrap-draws.npz', **draws)
    with (output / 'patient-probabilities.csv').open('x',encoding='utf-8',newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(probability_rows[0]));writer.writeheader();writer.writerows(probability_rows)
    failure_audit = {'scope':'original R3 reference-mask tabular cohort, not segmentation end-to-end',
        'distinct_evaluation_patients':22,'original_repeated_prediction_rows':792,'original_failed_prediction_rows':0,
        'source_exclusions':data.audit, 'exclusion_reason_sets_can_overlap':True,
        'calibration_fallbacks':{k:s['reason'] for k,s in calibration.items() if s['status']!='fitted'},
        'segmentation_empty_regions':{'status':'not_evaluated','paired_evaluation_mri_masks_available':False,
            'reason':'No same-patient MRI/reference/automatic-mask pairs are mapped to these 22 tabular evaluation patients; do not substitute engineering cases or zero counts.'},
        'synthetic_R2_failures_are_not_observed_patient_failures':True,
        'independent_external_evaluation':'not_performed; source/overlap/role gates unresolved'}
    write(output / 'failure-audit.json', failure_audit)
    if sha(output / 'temperature-states.json') != calibration_sha:
        raise ValueError('Calibration state changed during evaluation')
    for path,digest in source_hashes.items():
        if sha(path) != digest:
            raise ValueError('Source changed during analysis: '+path)
    if sha(config_path) != config_sha256.lower() or sha(protocol) != protocol_sha256.lower():
        raise ValueError('Frozen statistical inputs changed during analysis')
    for path in [config_path,protocol,Path(__file__).resolve(),Path(__file__).resolve().parents[1]/'app/research/patient_statistics.py']:
        source_hashes[str(path)] = sha(path)
    output_names = [p.name for p in output.iterdir() if p.is_file()]
    summary = {'status':'passed','protocol':config['protocol'],'protocol_sha256':protocol_sha256.lower(),
        'config_sha256':config_sha256.lower(),'source_hashes':source_hashes,'completed_utc':datetime.now(timezone.utc).isoformat(),
        'analysis_role':'posthoc exploratory, not independent clinical evaluation','distinct_evaluation_patients':22,
        'bootstrap_samples':2000,'statistical_vectors':24,'validation_calibrators':12,'calibration_fit_patients':21,
        'per_model_explanation_rows':len(explanations),'patient_probability_rows':len(probability_rows),
        'conditional_intervals':True,'clinical_label_polarity_resolved':False,'production_activated':False,'predictors_retrained':False,
        'segmentation_empty_region_audit_complete':False,'independent_external_evaluation':False,
        'temperature_fallbacks':failure_audit['calibration_fallbacks'],
        'versions':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__,'sklearn':sklearn.__version__},
        'seconds':time.perf_counter()-started,'output_sha256':{name:sha(output/name) for name in output_names},
        'method_sources':['https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html',
                          'https://scikit-learn.org/stable/modules/calibration.html',
                          'https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.minimize_scalar.html'],
        'limitations':['Observed class-stratified conditional percentile intervals exclude training/calibration-fit uncertainty.',
            'Seeds/centers/rows are not independent patients; only 22 patients and posthoc choices.',
            'Reusing the common validation pool for TOPSIS and temperature can overfit.',
            'Coefficients/contributions are not causal; explanations apply to individual uncalibrated models, not seed-mean/calibrated vectors.',
            'Segmentation empty-region/failure evaluation on a complete automatic-mask cohort remains unverified.']}
    write(output / 'summary.json', summary)
    print(json.dumps({k:summary[k] for k in ('status','distinct_evaluation_patients','statistical_vectors','validation_calibrators','per_model_explanation_rows','seconds','temperature_fallbacks')},indent=2))
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True);parser.add_argument('--config-sha256',required=True)
    parser.add_argument('--protocol-sha256',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();run(args.config,args.config_sha256,args.protocol_sha256,args.output)


if __name__=='__main__':main()
