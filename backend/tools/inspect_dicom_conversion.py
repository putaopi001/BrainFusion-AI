"""Read-only local conversion reopening; never activates a case or model."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.dicom_conversion_integrity import inspect_conversion_version
from plan_dicom_model_input import read


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version-dir', required=True)
    parser.add_argument('--report-sha256', required=True)
    parser.add_argument('--proposal', required=True)
    parser.add_argument('--snapshots', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    output = Path(args.output).resolve()
    version = Path(args.version_dir).resolve()
    if (output.drive.upper() != 'E:' or output.suffix.lower() != '.json'
            or not output.parent.is_dir() or output.exists() or output.is_relative_to(version)):
        parser.error('Use a new E-drive .json outside the inspected version; never overwrite.')
    try:
        proposal, psha = read(args.proposal, 4 * 1024 * 1024)
        snapshots, ssha = read(args.snapshots, 16 * 1024 * 1024)
        if output in [Path(args.proposal).resolve(), Path(args.snapshots).resolve()]:
            parser.error('Do not overwrite inputs.')
        report = inspect_conversion_version(args.version_dir, args.report_sha256, proposal, snapshots)
        report['input_file_sha256'] = {'proposal': psha, 'snapshots': ssha}
    except (OSError, ValueError, UnicodeError, RecursionError):
        report = {'format': 'dicom-conversion-inspection-v1', 'status': 'invalid',
                  'reason': 'invalid_input_files', 'model_input_eligible': False,
                  'source_files_written': False, 'archive_or_business_database_written': False}
    with output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({'status': report['status'], 'reason': report.get('reason'), 'model_input_eligible': False}))
    return 0 if report['status'] == 'verified_readonly' else 3


if __name__ == '__main__':
    raise SystemExit(main())
