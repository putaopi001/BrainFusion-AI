"""Read actual authenticated archive bytes and audit business UID links.

Produces hashes and relationship counts, never credentials or clinical fields.
Use --reference to compare the restored server to a pre-backup observation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.pacs_client import PacsConfig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--pacs-config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reference', type=Path)
    args = parser.parse_args()
    if args.output.exists(): raise FileExistsError('Verification output already exists')
    try:
        config = PacsConfig.model_validate_json(args.pacs_config.read_text(encoding='utf-8-sig'))
    except Exception:
        raise ValueError('Invalid private PACS configuration; credential values omitted') from None
    with httpx.Client(base_url=config.base_url, auth=(config.username, config.password.get_secret_value()),
                      trust_env=False, timeout=20) as client:
        def get(path, binary=False):
            response = client.get(path)
            response.raise_for_status()
            return response.content if binary else response.json()
        system = get('/system')
        if system.get('DatabaseServerIdentifier') != config.expected_database_server_identifier:
            raise ValueError('Archive database identity does not match backend pin')
        studies = {get('/studies/' + key)['MainDicomTags']['StudyInstanceUID'] for key in get('/studies')}
        instances = {}
        for key in sorted(get('/instances')):
            instances[key] = hashlib.sha256(get('/instances/' + key + '/file', True)).hexdigest()
    with sqlite3.connect(args.database.resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise ValueError('Business DB integrity failure')
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        counts = {name: db.execute('SELECT count(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0] for name in tables}
        links = [dict(row) for row in db.execute('SELECT * FROM pacs_study_links ORDER BY id')]
        current = [row for row in links if row['archive_id'] == config.archive_id]
        for row in current:
            if row['endpoint_fingerprint'] != config.endpoint_fingerprint or row['study_uid'] not in studies:
                raise ValueError('Dangling archive/study mapping')
            if not db.execute('SELECT 1 FROM cases WHERE id=?', (row['case_id'],)).fetchone():
                raise ValueError('Dangling case mapping')
    value = {'status': 'passed', 'instance_count': len(instances), 'instance_sha256': instances,
             'study_uids': sorted(studies), 'database_server_identifier': system['DatabaseServerIdentifier'],
             'archive_version': system['Version'], 'row_counts': counts,
             'pacs_links_sha256': hashlib.sha256(json.dumps(links, sort_keys=True).encode()).hexdigest(),
             'current_archive_link_count': len(current), 'all_current_archive_links_resolve': True}
    if args.reference:
        original = json.loads(args.reference.read_text(encoding='utf-8'))
        if value != original: raise ValueError('Restored/live archive and business relations differ from reference')
    with args.output.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2)
    print(json.dumps({'status': 'passed', 'instances_verified': len(instances), 'links_verified': len(current),
                      'reference_equal': bool(args.reference)}))


if __name__ == '__main__': main()
