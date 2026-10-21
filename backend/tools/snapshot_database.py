"""Read-only SQLite backup and restore-copy validation; never overwrite a target."""
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def counts(connection):
    tables = [row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    return {name: connection.execute('SELECT count(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0]
            for name in tables}


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    output = args.output.resolve()
    if output.drive.upper() != 'E:':
        raise ValueError('Backup output must stay on E:')
    output.mkdir(parents=True, exist_ok=False)
    backup, restored = output / 'snapshot.db', output / 'restored-validation.db'
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as original:
        with sqlite3.connect(backup) as saved:
            original.backup(saved)
            source_counts = counts(saved)
            assert saved.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            with sqlite3.connect(restored) as copy:
                saved.backup(copy)
                assert copy.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
                assert counts(copy) == source_counts
    evidence = {
        'status': 'passed', 'created_utc': datetime.now(timezone.utc).isoformat(),
        'source': str(source), 'snapshot': str(backup), 'restored_copy': str(restored),
        'row_counts': source_counts, 'integrity': 'ok', 'restore_counts_equal': True,
        'snapshot_sha256': sha256(backup),
        'scope': 'database only; referenced MRI/model/artifact files remain at original paths',
    }
    (output / 'validation.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
