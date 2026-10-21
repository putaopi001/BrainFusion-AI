"""Read local source snapshots; save a new E-drive planning receipt; no network/DB."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.dicom_input_plan import plan_report


def unique_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def reject_constant(_value):
    raise ValueError('Nonfinite JSON value')


def read(path, cap):
    resolved = Path(path).resolve(strict=True)
    if resolved.drive.upper() != 'E:' or not resolved.is_file() or resolved.stat().st_size > cap:
        raise ValueError('Bounded E-drive input required')
    with resolved.open('rb') as handle:
        raw = handle.read(cap+1)
    if len(raw) > cap:
        raise ValueError('Input changed size')
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique_pairs, parse_constant=reject_constant), hashlib.sha256(raw).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proposal', required=True)
    parser.add_argument('--snapshots', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    output = Path(args.output).resolve()
    if output.drive.upper() != 'E:' or output.suffix.lower() != '.json' or not output.parent.is_dir() or output.exists():
        parser.error('Use a new .json file in an existing E-drive directory; never overwrite.')
    try:
        proposal, psha = read(args.proposal, 4*1024*1024)
        snapshots, ssha = read(args.snapshots, 16*1024*1024)
        report = plan_report(proposal, snapshots)
        report['input_file_sha256'] = {'proposal': psha, 'snapshots': ssha}
    except (OSError, ValueError, UnicodeError, RecursionError):
        report = {'format': 'dicom-model-input-plan-v1', 'status': 'rejected',
                  'reason': 'invalid_input_files', 'message': '本地输入文件不可读、过大或JSON不合法。',
                  'model_input_eligible': False, 'conversion_performed': False}
    with output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({'status': report['status'], 'reason': report.get('reason'),
                      'model_input_eligible': False, 'source_unchanged_by_tool': True}))
    return 0 if report['status'] == 'metadata_plan_ready' else 3


if __name__ == '__main__':
    raise SystemExit(main())
