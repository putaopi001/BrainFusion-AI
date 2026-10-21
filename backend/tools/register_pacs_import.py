"""Register one prepared public MR derivative and pin its technical review.

This is an explicit local operator action, not a clinical certification. Browser
clients cannot register paths or change the pinned source/review materials.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.config import settings
from app.services.pacs_client import load_config
from app.services.pacs_import import checked_candidate, digest, import_lock, now, registry, write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--review-record',type=Path,required=True)
    parser.add_argument('--label',required=True)
    parser.add_argument('--acknowledge-source-and-pixel-review',action='store_true',required=True)
    args=parser.parse_args()
    root=args.directory.resolve(strict=True)
    review=args.review_record.resolve(strict=True)
    if review.drive.upper()!='E:' or not 1<=len(args.label)<=100: raise ValueError('Invalid local review record/label')
    manifest=json.loads((root/'derivative-manifest.json').read_text(encoding='utf-8'))
    report=json.loads((root/'preparation-report.json').read_text(encoding='utf-8'))
    if report.get('format_version') != 2:
        raise ValueError('New registrations require source-bound preparation v2; existing pinned registrations remain historical')
    from app.services.public_mr_preparation import validate_prepared_review
    validate_prepared_review(root,manifest,report)
    if review != (root/'review-evidence'/'technical-review.json').resolve():
        raise ValueError('Register the bundled source-bound technical review record')
    row=dict(directory=str(root),review_record=str(review),label=args.label,
             manifest_sha256=digest((root/'derivative-manifest.json').read_bytes()),
             report_sha256=digest((root/'preparation-report.json').read_bytes()),review_sha256=digest(review.read_bytes()),
             instance_count=manifest['instance_count'],study_uid=manifest['study_uid'],series_uid=manifest['series_uid'],
             collection_doi=report['collection_doi'],license_url=report['license_url'],registered_utc=now())
    row['candidate_id']=digest(json.dumps({k:row[k] for k in ('directory','manifest_sha256','report_sha256','review_sha256')},sort_keys=True).encode())
    with import_lock():
        checked_candidate(row,load_config())
        items=registry()
        if not any(item['candidate_id']==row['candidate_id'] for item in items):
            if len(items)>=64: raise ValueError('The local import registry is full; preserve records for review')
            items.append(row)
        write_json(Path(settings.PACS_IMPORT_REGISTRY_FILE),dict(format_version=1,items=items))
    print(json.dumps(dict(status='registered',candidate_id=row['candidate_id'],instances=row['instance_count'],clinical_certification=False,ai_activation=False)))


if __name__=='__main__': main()
