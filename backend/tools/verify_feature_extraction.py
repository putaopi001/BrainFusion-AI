"""Reference reproduction gate before transferring the reference-trained model."""
import csv
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
import nibabel as nib
import joblib

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.research.dataset import load_dataset, sha256
from app.research.feature_contract import PROTOCOL, selected_features, contract_hash, feature_matrix
from app.core.config import settings

DEFAULT_DATA = Path('E:/BrainFusion-Data/WAW-GliomAI-v3')
SCRIPT = BACKEND / 'tools/extract_selected_radiomics.py'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Fresh E: evidence directory; never overwrite an existing gate')
    parser.add_argument('--worker', type=Path, default=Path(settings.RADIOMICS_PYTHON))
    parser.add_argument('--data-dir', type=Path, default=DEFAULT_DATA, help='Reference MRI/mask and published table root')
    parser.add_argument('--research-dir', type=Path, default=Path(settings.RESEARCH_DIR))
    parser.add_argument('--baseline', type=Path, help='Preserved old-environment compatibility.json for direct comparison')
    args = parser.parse_args()
    ROOT, WORKER, DATA = args.output.resolve(), args.worker.resolve(strict=True), args.data_dir.resolve(strict=True)
    if ROOT.drive.upper() != 'E:': raise ValueError('Evidence must remain on E:')
    ROOT.mkdir(parents=True, exist_ok=False)
    baseline = json.loads(args.baseline.read_text(encoding='utf-8')) if args.baseline else None
    research = args.research_dir.resolve(strict=True)
    pointer = json.loads((research / 'latest.json').read_text(encoding='utf-8'))
    directory = research / pointer['run_id']
    summary = json.loads((directory / 'summary.json').read_text(encoding='utf-8'))
    assert sha256(directory / 'summary.json') == pointer['summary_sha256']
    assert sha256(directory / 'models.joblib') == summary['artifact_sha256']['models.joblib']
    bundle = joblib.load(directory / 'models.joblib')
    dataset = load_dataset(DATA)
    assert dataset.audit['input_sha256'] == bundle['data_sha256']
    keys, records, checks = selected_features(bundle), [], []
    if baseline:
        assert baseline['status'] == 'passed' and baseline['contract_sha256'] == contract_hash(bundle)
        assert baseline['model_sha256'] == summary['artifact_sha256']['models.joblib']
        assert baseline['data_sha256'] == bundle['data_sha256'] and baseline['protocol'] == PROTOCOL
    old_comparisons = []
    for identifier in ('4', '13', '16', '17', '19'):
        output = ROOT / 'reference' / identifier
        output.mkdir(parents=True, exist_ok=True)
        mask = DATA / f'sample/reference_masks/preop_masks/{identifier}/{identifier}_0_tumor_mask_pre.nii.gz'
        sequences = {seq: str(DATA / f'sample/images/gliomai_preop_scans_renamed/{identifier}/{identifier}_0_brain_{seq}.nii.gz') for seq in ('t1c', 't1n', 't2w', 't2f')}
        request = {'sequences': sequences, 'mask_path': str(mask), 'selected_features': keys,
                   'protocol': PROTOCOL, 'contract_sha256': contract_hash(bundle), 'feature_source': 'reference mask'}
        request_file, result_file = output / 'request.json', output / 'features.json'
        request_file.write_text(json.dumps(request, indent=2), encoding='utf-8')
        with (output / 'worker.log').open('w', encoding='utf-8') as log:
            subprocess.run([str(WORKER), '-B', str(SCRIPT), '--request', str(request_file), '--output', str(result_file)],
                           cwd=BACKEND, stdout=log, stderr=log, timeout=180, check=True)
        result = json.loads(result_file.read_text(encoding='utf-8'))
        differences = []
        for key in keys:
            label, feature = key.split(':', 1)
            published = dataset.regions.get((identifier, label), {}).get(feature)
            calculated = result['features'][key]
            if published is None or published == '':
                assert calculated is None, key
            else:
                assert calculated is not None, key
                expected = float(published)
                differences.append({'key': key, 'expected': expected, 'computed': calculated,
                                    'absolute_difference': abs(expected - calculated),
                                    'passed': bool(np.isclose(expected, calculated, rtol=1e-5, atol=1e-8))})
        _, original = dataset.matrices([identifier])
        extracted = feature_matrix(bundle, result['features'])
        model = bundle['models']['reference_mask_radiomics']
        first = float(model.predict_proba(original)[0, 1])
        second = float(model.predict_proba(extracted)[0, 1])
        if baseline:
            old = next(row for row in baseline['patients'] if row['source_patient_id'] == identifier)
            comparisons = [{'key': entry['key'], 'old': entry['computed'], 'candidate': result['features'][entry['key']],
                            'passed': bool(np.isclose(entry['computed'], result['features'][entry['key']], rtol=1e-5, atol=1e-8))}
                           for entry in old['features']]
            old_comparisons.append({'patient': identifier, 'features': comparisons,
                                    'probability_matches': abs(old['reextracted_probability'] - second) < 1e-6})
        labels = np.asarray(nib.load(mask).dataobj)
        for seq, path in sequences.items():
            image = nib.load(path).get_fdata()
            scaled = (image - image.min()) / (image.max() - image.min())
            for (patient, label), row in dataset.regions.items():
                if patient != identifier:
                    continue
                roi = scaled[labels == int(label)]
                assert len(roi) == int(float(row[f'diagnostics_Mask-original_VoxelNum.brain_{seq}']))
                statistics = {'Mean': roi.mean(), 'Median': np.median(roi), 'Minimum': roi.min(), 'Maximum': roi.max(),
                              'Variance': roi.var(), '10Percentile': np.percentile(roi, 10), '90Percentile': np.percentile(roi, 90)}
                for name, value in statistics.items():
                    expected = float(row[f'original_firstorder_{name}.brain_{seq}'])
                    checks.append({'patient': identifier, 'region': label, 'sequence': seq, 'statistic': name,
                                   'absolute_difference': abs(float(value) - expected), 'passed': bool(np.isclose(value, expected, rtol=1e-6, atol=1e-9))})
        records.append({'source_patient_id': identifier, 'features': differences, 'published_probability': first,
                        'reextracted_probability': second, 'probability_matches': abs(first - second) < 1e-6,
                        'seconds': result['seconds'], 'versions': result['versions'], 'empty_regions': [key for key, count in result['region_voxel_counts'].items() if count == 0]})
        print(f'Reference {identifier}: {len(differences)} finite selected features checked', flush=True)
    passed = all(c['passed'] for c in checks) and all(r['probability_matches'] and all(c['passed'] for c in r['features']) for r in records)
    if baseline: passed = passed and all(row['probability_matches'] and all(c['passed'] for c in row['features']) for row in old_comparisons)
    audit = {'status': 'passed' if passed else 'failed', 'scope': 'five development reference cases only; not all-cohort or external validation',
             'research_run_id': summary['run_id'], 'model_sha256': summary['artifact_sha256']['models.joblib'],
             'data_sha256': bundle['data_sha256'], 'contract_sha256': contract_hash(bundle), 'protocol': PROTOCOL,
             'worker_script_sha256': sha256(SCRIPT), 'contract_script_sha256': sha256(BACKEND / 'app/research/feature_contract.py'),
             'worker_provenance_sha256': sha256(WORKER.parent / 'source.json'), 'selected_features': keys, 'patients': records,
             'normalization_checks': len(checks), 'normalization_max_error': max(c['absolute_difference'] for c in checks),
             'gpu_used': False, 'baseline_comparisons': old_comparisons,
             'worker_python': str(WORKER), 'baseline': str(args.baseline) if args.baseline else None}
    (ROOT / 'normalization_checks.json').write_text(json.dumps(checks, indent=2), encoding='utf-8')
    (ROOT / 'compatibility.json').write_text(json.dumps(audit, indent=2, allow_nan=False), encoding='utf-8')
    assert passed, 'Reproduction failed; automatic-mask predictions remain disabled. Inspect compatibility.json.'
    print('Reference feature and probability reproduction gate PASS')


if __name__ == '__main__':
    main()
