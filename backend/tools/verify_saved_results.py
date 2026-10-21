"""Validate real saved results through a freshly started service, without training."""
import argparse
import io
import json
from pathlib import Path
import sys
from urllib.request import urlopen
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.segmentation_metrics import evaluate


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--api-base', default='http://127.0.0.1:8000')
    parser.add_argument('--comparison-api')
    args = parser.parse_args()
    def get(path, base=None):
        with urlopen((base or args.api_base) + path, timeout=30) as response:
            return json.load(response)['data']
    source = Path('E:/BrainFusion-Runtime/results/stage2/workflow_validation.json')
    workflow = json.loads(source.read_text(encoding='utf-8'))
    assert workflow['status'] == 'passed'
    records = []
    for sample in workflow['samples']:
        case_id, sample_id = sample['case_id'], sample['sample_id']
        run = get(f'/analysis/{case_id}')
        assert run['state'] == 'succeeded'
        if args.comparison_api:
            other = get(f'/analysis/{case_id}', args.comparison_api)
            assert run['id'] == other['id'] and run['result']['mask_sha256'] == other['result']['mask_sha256']
        detail = get(f'/cases/{case_id}/detail')
        assert detail['report']['analysis_run_id'] == run['id']
        if detail['mri']['doctor_verified']:
            assert detail['mri']['verified_run_id'] == run['id']
        meta = get(f'/mri/{case_id}/volume')
        for view, axis in (('axial', 0), ('coronal', 1), ('sagittal', 2)):
            index = meta['shape'][axis] // 2
            for kind in ('slice', 'mask'):
                with urlopen(f'{args.api_base}/mri/{case_id}/{kind}/{view}/{index}', timeout=30) as response:
                    image = Image.open(io.BytesIO(response.read()))
                    image.load()
                    assert min(image.size) > 0
        reference = Path(f'E:/BrainFusion-Data/WAW-GliomAI-v3/sample/reference_masks/preop_masks/{sample_id}/{sample_id}_0_tumor_mask_pre.nii.gz')
        metrics = evaluate(Path(run['result']['mask_path']), reference)
        records.append({'sample_id': sample_id, 'case_id': case_id, 'run_id': run['id'], 'saved_result': 'passed', 'metrics': metrics})
        print(f'Sample {sample_id}: saved report, verification version, three-view slices and masks PASS', flush=True)
    output = Path('E:/BrainFusion-Runtime/results/stage5')
    output.mkdir(parents=True, exist_ok=True)
    research_evidence = json.loads(Path('E:/BrainFusion-Runtime/results/stage4/api_validation.json').read_text(encoding='utf-8'))
    summary = get('/research/summary')
    assert summary['run_id'] == research_evidence['run_id']
    for saved in research_evidence['samples']:
        restored = get('/research/patients/' + saved['source_patient_id'])
        assert restored['run_id'] == saved['run_id']
        assert restored['probabilities'] == saved['probabilities']
    (output / 'persistence_validation.json').write_text(json.dumps({'status': 'passed', 'api_base': args.api_base, 'comparison_api': args.comparison_api, 'samples': records,
                                                                  'research_restart': 'passed', 'research_run_id': summary['run_id']}, indent=2), encoding='utf-8')
    print('Research models reloaded after service restart; five probabilities match saved evidence PASS')


if __name__ == '__main__':
    main()
