"""Run frozen descriptive R2 diagnostics from an existing trusted local replay.

Reads no model pickle, fits no predictor, and never updates a latest pointer.
"""
import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np

from app.research.entropy_topsis import apply_entropy_fusion, load_entropy_state
from app.research.fusion_ablation import (BRANCHES, CLINICAL_GRID, SCENARIOS, SHIFTS,
    evaluate_available_fusion, missing_scenarios, validation_sensitivity_plan)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)


def csv_rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def run(config_path, config_sha256, protocol_sha256, output):
    config_path, output = Path(config_path), Path(output)
    if output.exists():
        raise ValueError('Existing output is never overwritten')
    if output.resolve().drive.upper() != 'E:':
        raise ValueError('Output must remain on E:')
    if sha(config_path) != config_sha256.lower():
        raise ValueError('Frozen configuration SHA mismatch')
    protocol = Path(__file__).resolve().parents[2] / 'docs/R2_ABLATION_PROTOCOL.md'
    if sha(protocol) != protocol_sha256.lower():
        raise ValueError('Frozen ablation protocol SHA mismatch')
    config = read(config_path)
    expected_keys = {'protocol', 'source_directory', 'source_sha256', 'metric_shifts', 'clinical_weight_grid',
                     'scenarios', 'threshold', 'evaluation_role', 'selection_allowed'}
    if (set(config) != expected_keys or config['protocol'] != 'brainfusion_fusion_ablation_v1'
            or config['metric_shifts'] != list(SHIFTS) or config['clinical_weight_grid'] != list(CLINICAL_GRID)
            or config['scenarios'] != list(SCENARIOS) or config['threshold'] != .5
            or config['evaluation_role'] != 'already_observed_exploratory_test' or config['selection_allowed'] is not False):
        raise ValueError('Configuration differs from the frozen ablation protocol')
    source = Path(config['source_directory'])
    if output.resolve().is_relative_to(source.resolve()):
        raise ValueError('Output cannot modify the source comparison directory')
    source_files = {'comparison': source / 'comparison.json', 'state': source / 'entropy-state.json',
                    'predictions': source / 'predictions.csv'}
    if set(config['source_sha256']) != set(source_files):
        raise ValueError('Incomplete source binding')
    for name, path in source_files.items():
        if sha(path) != config['source_sha256'][name]:
            raise ValueError(f'Source {name} SHA mismatch')
    comparison = read(source_files['comparison'])
    if (comparison['status'] != 'passed' or comparison['production_activated'] is not False
            or comparison['split_sizes'] != {'train': 98, 'validation': 21, 'test': 22}
            or comparison['feature_source'] != 'published reference-mask radiomics'
            or comparison['role'] != 'already observed exploratory split; no independent evaluation'):
        raise ValueError('Source role or protocol differs from the registered exploratory replay')
    source_hashes = dict(comparison['source_hashes'])
    source_hashes.update({str(path): sha(path) for path in source_files.values()})
    for path, digest in source_hashes.items():
        if sha(path) != digest:
            raise ValueError(f'Source lineage SHA mismatch: {path}')
    if sha(source_files['state']) != comparison['state_sha256']:
        raise ValueError('State differs from the prior accepted replay')
    state = load_entropy_state(read(source_files['state']))
    methods = comparison['methods']
    expected_methods = ['clinical', 'reference_mask_radiomics', 'average', 'fixed_clinical_0.6_radiomics_0.4',
                        'validation_topsis', 'validation_entropy_topsis']
    if list(methods) != expected_methods or methods['validation_entropy_topsis']['weights'] != state['branch_weights']:
        raise ValueError('Branch methods/order/entropy weights differ')
    # No evaluation labels are passed to this plan. Freeze all validation states first.
    plan = validation_sensitivity_plan(state)
    output.mkdir(parents=True)
    write(output / 'validation-plan.json', plan)
    write(output / 'config.json', config)
    plan_sha256 = sha(output / 'validation-plan.json')
    planned_utc = datetime.now(timezone.utc).isoformat()
    # Parse patient probabilities and labels only after freezing the validation-only plan.
    records = csv_rows(source_files['predictions'])
    originals = [Path(path) for path in comparison['source_hashes'] if Path(path).name == 'predictions.csv']
    if len(originals) != 1:
        raise ValueError('Ambiguous original prediction provenance')
    original_rows = csv_rows(originals[0])
    ids = [row['patient_id'] for row in records]
    if len(ids) != 22 or len(set(ids)) != 22 or ids != [row['patient_id'] for row in original_rows]:
        raise ValueError('Patient identities/order differ from the registered 22')
    if set(ids) & set(state['validation_patient_ids']) or not set(ids) <= set(state['excluded_patient_ids']):
        raise ValueError('Evaluation patients overlap fitting roles or are not explicitly excluded')
    if any(row['role'] != 'already_observed_exploratory_test' for row in records):
        raise ValueError('Evaluation rows are not marked as already observed exploratory')
    labels = np.asarray([int(row['target']) for row in records])
    probabilities = np.asarray([[float(row[name]) for name in BRANCHES] for row in records])
    np.testing.assert_array_equal(labels, [int(row['target']) for row in original_rows])
    np.testing.assert_allclose(probabilities, [[float(row[name]) for name in BRANCHES] for row in original_rows], rtol=1e-12, atol=1e-12)
    if not np.isfinite(probabilities).all():
        raise ValueError('Registered complete-source probabilities must be finite')
    availability_results = {}
    for scenario, present in missing_scenarios(ids).items():
        masked = np.where(present, probabilities, np.nan)
        results = {}
        for method, saved in methods.items():
            allowed = (True, False) if method == 'clinical' else ((False, True) if method == 'reference_mask_radiomics' else (True, True))
            results[method] = evaluate_available_fusion(masked, labels, ids, saved['weights'], allowed_branches=allowed)
        successful = [i for i, row in enumerate(results['validation_entropy_topsis']['rows']) if row['status'] == 'succeeded']
        if successful:
            applied = apply_entropy_fusion(state, masked[successful], branch_ids=list(BRANCHES))
            audited = [results['validation_entropy_topsis']['rows'][i] for i in successful]
            np.testing.assert_allclose([row['probability'] for row in audited], applied['probabilities'], rtol=0, atol=1e-14)
            np.testing.assert_allclose([row['effective_weights'] for row in audited], applied['effective_weights'], rtol=0, atol=1e-14)
            assert [row['reasons'] for row in audited] == applied['reasons']
        if scenario == 'complete':
            for method, result in results.items():
                assert result['successful_patients'] == 22 and result['failed_patients'] == 0
                for key, value in result['metrics'].items():
                    np.testing.assert_allclose(value, methods[method]['exploratory_test'][key], rtol=1e-12, atol=1e-12)
                np.testing.assert_allclose([row['probability'] for row in result['rows']], [float(row[method]) for row in records], rtol=1e-12, atol=1e-12)
        availability_results[scenario] = results
    weight_curve = []
    for clinical_weight in CLINICAL_GRID:
        weights = [clinical_weight, 1 - clinical_weight]
        result = evaluate_available_fusion(probabilities, labels, ids, weights)
        weight_curve.append({'weights': weights, 'evaluation_role': 'posthoc_descriptive_already_observed',
                             'selection_allowed': False, 'result': result})
    validation_summary = {'variants': len(plan['variants']), 'variants_with_changed_branch_weights': sum(v['branch_weight_max_abs_from_baseline'] > 1e-12 for v in plan['variants']),
                          'maximum_branch_weight_change': max(v['branch_weight_max_abs_from_baseline'] for v in plan['variants']),
                          'criterion_drops': {v['name']: v['state']['branch_weights'] for v in plan['variants'] if v['kind'] == 'criterion_drop'}}
    write(output / 'availability-results.json', availability_results)
    write(output / 'weight-curve.json', weight_curve)
    if sha(output / 'validation-plan.json') != plan_sha256:
        raise ValueError('Validation plan changed during evaluation')
    for path, digest in source_hashes.items():
        if sha(path) != digest:
            raise ValueError(f'Source changed during evaluation: {path}')
    if sha(config_path) != config_sha256.lower() or sha(protocol) != protocol_sha256.lower():
        raise ValueError('Frozen inputs changed during evaluation')
    for path in [config_path, protocol, Path(__file__).resolve(), Path(__file__).resolve().parents[1] / 'app/research/fusion_ablation.py']:
        source_hashes[str(path)] = sha(path)
    result = {'status': 'passed', 'protocol': config['protocol'], 'protocol_sha256': protocol_sha256.lower(),
              'config_sha256': config_sha256.lower(), 'validation_plan_sha256': plan_sha256,
              'validation_plan_frozen_utc': planned_utc, 'completed_utc': datetime.now(timezone.utc).isoformat(),
              'source_hashes': source_hashes, 'validation_summary': validation_summary,
              'availability_scenarios': len(availability_results), 'methods_per_scenario': len(methods),
              'patients_per_scenario': len(ids), 'global_weight_grid_points': len(weight_curve),
              'selection_allowed': False, 'models_fitted': False, 'production_activated': False,
              'limitations': ['Posthoc descriptive diagnostics on the already observed 22 patients.',
                              'Synthetic missingness is not observed real-world missingness.',
                              'Conditional metrics on successful patients never replace the full denominator.',
                              'Reference-mask features only; no same-protocol automatic-mask cohort result.',
                              'No clinical label polarity, independent evaluation, uncertainty interval, or superiority claim.'],
              'output_sha256': {name: sha(output / name) for name in ('validation-plan.json', 'config.json', 'availability-results.json', 'weight-curve.json')}}
    write(output / 'summary.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--config-sha256', required=True)
    parser.add_argument('--protocol-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run(args.config, args.config_sha256, args.protocol_sha256, args.output)
    print(json.dumps({key: result[key] for key in ('status', 'validation_summary', 'availability_scenarios', 'methods_per_scenario', 'global_weight_grid_points')}, indent=2))


if __name__ == '__main__':
    main()
