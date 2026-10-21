"""Import registered public MR derivatives through the shared guarded service.

Use register_pacs_import.py first. CLI and case UI share the same OS mutex,
validation, read-only source files, persistent receipts and retry rules.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.pacs_import import execute, registry


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--acknowledge-reviewed-local-viewing-only',action='store_true',required=True)
    args=parser.parse_args()
    root=args.directory.resolve(strict=True)
    rows=[row for row in registry() if Path(row['directory']).resolve()==root]
    if len(rows)!=1:
        parser.error('Directory needs exactly one current registered source/review version; use the registration tool first')
    result=execute(rows[0]['candidate_id'],args.acknowledge_reviewed_local_viewing_only)
    print(json.dumps(result,ensure_ascii=False))
    if result['state']=='failed': raise SystemExit(1)


if __name__=='__main__':main()
