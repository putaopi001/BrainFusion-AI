"""Persistent local DICOM conversion jobs; never activates an MRI or runs inference."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.dicom_conversion_jobs import create_job, run_job, retry_job
from app.services.dicom_input_plan import PlanError


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proposal')
    parser.add_argument('--snapshots')
    parser.add_argument('--source-files')
    parser.add_argument('--output-dir')
    parser.add_argument('--register-version-id')
    parser.add_argument('--job-id')
    parser.add_argument('--retry-job-id')
    parser.add_argument('--prepare-only', action='store_true', help='Persist a queued job for explicit doctor start from the case page; do not convert.')
    args = parser.parse_args(argv)
    try:
        if args.retry_job_id:
            if any((args.proposal, args.snapshots, args.source_files, args.output_dir,
                    args.register_version_id, args.job_id, args.prepare_only)):
                parser.error('--retry-job-id cannot be combined with creation arguments')
            result = run_job(args.retry_job_id)
        else:
            if not all((args.proposal, args.snapshots, args.source_files, args.output_dir)):
                parser.error('new jobs require --proposal, --snapshots, --source-files and --output-dir')
            created = create_job(args.proposal, args.snapshots, args.source_files, args.output_dir,
                                 args.register_version_id, args.job_id)
            result = created if args.prepare_only else run_job(created['job_id'])
    except PlanError as error:
        print(json.dumps({'status': 'rejected', 'reason': error.reason,
                          'model_input_eligible': False, 'current_mri_replaced': False,
                          'inference_performed': False}))
        return 3
    print(json.dumps({'status': result['state'], 'job': result,
                      'all_voxels_compared': result.get('all_voxels_compared'),
                      'model_input_eligible': False, 'current_mri_replaced': False,
                      'inference_performed': False}, ensure_ascii=False))
    return 0 if result['state'] == 'succeeded' or (args.prepare_only and result['state'] == 'queued') else 3


if __name__ == '__main__':
    raise SystemExit(main())
