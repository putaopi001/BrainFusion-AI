"""Retain a DICOM candidate in local quarantine. Never uploads to PACS."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.dicom_custody import CustodyError, inspect_custody, retain_candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, required=True)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--source-manifest', type=Path)
    parser.add_argument('--inspect', action='store_true')
    args = parser.parse_args()
    try:
        if args.inspect:
            if args.input or args.source_manifest:
                parser.error('Inspection accepts only a store')
            result = inspect_custody(args.store)
        else:
            if not args.input or not args.source_manifest:
                parser.error('Input and source manifest required')
            if args.source_manifest.stat().st_size > 65536:
                raise CustodyError('manifest_too_large')
            source = json.loads(args.source_manifest.read_text(encoding='utf-8-sig'))
            result = retain_candidate(args.input, source, args.store)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as error:
        reason = error.reason if isinstance(error, CustodyError) else 'custody_input_or_storage_invalid'
        print(json.dumps({'reason': reason, 'archive_imported': False}))
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
