"""Private checksum snapshot/restore of import registrations and all receipts.

The same OS mutex excludes imports while copying. Source DICOM/review materials
remain pinned external dependencies, not silently copied or re-approved here.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.config import settings
from app.services.pacs_import import import_lock, read_json, registry, now
from tools.snapshot_pacs_joint import PRIVATE_ROOT, private_target, entries, copy_verified, write_new
from tools.snapshot_database import sha256


def backup(output):
    output=private_target(output)
    with import_lock() as jobs:
        source=Path(settings.PACS_IMPORT_REGISTRY_FILE).resolve(strict=True)
        rows=registry()
        if output.is_relative_to(jobs): raise ValueError('Snapshot cannot be inside active import records')
        for state in jobs.glob('*/state.json'):
            if read_json(state)['state'] in ('queued','running'): raise ValueError('Active/interrupted import must be resolved before snapshot')
        records=entries(jobs,'jobs',exclude={'import.lock'})
        records.append(dict(source=str(source),relative='registry.json',bytes=source.stat().st_size,sha256=sha256(source)))
        output.parent.mkdir(parents=True,exist_ok=True);output.mkdir()
        copy_verified(records,output)
        write_new(output/'manifest.json',dict(format_version=1,status='passed',created_utc=now(),files=records,
              external_reviewed_materials=[dict(directory=row['directory'],review_record=row['review_record'],
                    manifest_sha256=row['manifest_sha256'],report_sha256=row['report_sha256'],review_sha256=row['review_sha256']) for row in rows],
              scope='Import registry and all receipts, including failed-attempt diagnostics; source DICOM and review files remain external pinned dependencies'))
    return dict(status='passed',files=len(records),active_import_excluded_by_os_lock=True)


def restore(snapshot,output):
    output=private_target(output);snapshot=Path(snapshot).resolve(strict=True)
    if not snapshot.is_relative_to(PRIVATE_ROOT):raise ValueError('Import snapshot must remain in private Runtime backups')
    if snapshot.is_relative_to(output) or output.is_relative_to(snapshot):raise ValueError('Snapshot and restore paths must be separate')
    value=read_json(snapshot/'manifest.json')
    if value.get('format_version')!=1 or value.get('status')!='passed':raise ValueError('Incomplete import snapshot')
    output.parent.mkdir(parents=True,exist_ok=True);output.mkdir()
    copy_verified(value['files'],output,snapshot)
    write_new(output/'runtime.json',dict(format_version=1,paths=dict(PACS_IMPORT_REGISTRY_FILE=str(output/'registry.json'),PACS_IMPORT_JOBS_DIR=str(output/'jobs')),
               scope='Extra process environment paths; distinct from the eight-path application runtime configuration'))
    write_new(output/'restore-validation.json',dict(status='passed',files_verified=len(value['files']),
               external_materials_still_required=True,scope=value['scope']))
    return dict(status='passed',files_verified=len(value['files']))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--action',choices=['backup','restore'],required=True)
    parser.add_argument('--snapshot',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.action=='restore' and not args.snapshot:parser.error('--snapshot required')
    print(json.dumps(backup(args.output) if args.action=='backup' else restore(args.snapshot,args.output)))


if __name__=='__main__':main()
