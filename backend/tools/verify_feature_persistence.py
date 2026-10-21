"""Capture completed feature results, then compare after a service restart."""
import argparse
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path('E:/BrainFusion-Runtime/results/stage6')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--api-base', default='http://127.0.0.1:8012')
    parser.add_argument('--capture', action='store_true')
    args = parser.parse_args()
    def get(path):
        with urlopen(args.api_base + path, timeout=20) as response:
            return json.load(response)['data']
    evidence = json.loads((ROOT / 'automatic_validation.json').read_text(encoding='utf-8'))
    records = []
    for sample in evidence['samples']:
        case_id = sample['case_id']
        job = get(f'/research/cases/{case_id}/features')
        detail = get(f'/cases/{case_id}/detail')
        assert job['state'] == 'succeeded'
        assert job['analysis_run_id'] == detail['mri']['analysis_run_id']
        records.append({'case_id': case_id, 'job_id': job['id'], 'analysis_run_id': job['analysis_run_id'],
                        'research_run_id': job['research_run_id'], 'result': job['result'],
                        'report': detail['report'], 'verified_run_id': detail['mri']['verified_run_id']})
    if args.capture:
        (ROOT / 'before_restart.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Five completed feature jobs captured; no extraction or training')
    else:
        before = json.loads((ROOT / 'before_restart.json').read_text(encoding='utf-8'))
        assert records == before, 'Feature results, report or confirmation changed across restart'
        (ROOT / 'persistence_validation.json').write_text(json.dumps({'status': 'passed', 'samples': records, 'new_extraction_or_training': False}, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Five feature results, versions, reports and confirmations persist across restart PASS')


if __name__ == '__main__':
    main()
