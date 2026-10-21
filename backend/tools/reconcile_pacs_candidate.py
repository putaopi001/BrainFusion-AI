"""Read-only reconciliation of a retained candidate. No upload or source rewrite."""
import argparse
import json
import sqlite3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.dicom_custody import CustodyError, inspect_custody
from app.services.pacs_reconcile import reconcile_archive_instance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, required=True)
    parser.add_argument('--receipt-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.drive.upper() != 'E:' or output.exists():
        parser.error('Fresh output on E: required; no output overwritten')
    try:
        inspect_custody(args.store)
        # Receipts are read only, no custody schema or business DB migration.
        with sqlite3.connect((args.store.resolve() / 'custody.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
            row = db.execute('SELECT manifest_json,audit_json,audit_sha256 FROM receipts WHERE receipt_id=?',
                             (args.receipt_id,)).fetchone()
        if row is None:
            raise CustodyError('custody_receipt_not_found')
        manifest, audit = json.loads(row[0]), json.loads(row[1])
        binding = {key: manifest[key] for key in ('study_uid', 'series_uid', 'sop_uid')}
        binding.update(source_sha256=audit['source_sha256'], source_bytes=audit['source_bytes'])
        result = reconcile_archive_instance(binding)
        result.update(custody_receipt_id=args.receipt_id, custody_audit_sha256=row[2],
                      candidate_preflight_decision=audit['decision'],
                      candidate_approval_verified=False)
    except Exception as error:
        result = {'format': 'pacs-read-only-reconciliation-v1', 'state': 'unresolved',
                  'reason': error.reason if isinstance(error, CustodyError) else 'candidate_check_failed',
                  'verified_present_at_check': None, 'archive_imported_by_tool': False,
                  'upload_allowed': False, 'observation_only': True}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({key: result.get(key) for key in
                      ('state', 'reason', 'verified_present_at_check', 'archive_imported_by_tool', 'upload_allowed')}))
    return 0 if result['state'] in ('matched_existing', 'absent_at_check') else 3


if __name__ == '__main__':
    raise SystemExit(main())
