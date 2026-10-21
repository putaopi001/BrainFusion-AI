"""Read-only final audit against the immutable pre-run SQLite/artifact snapshot."""
import argparse
import json
from pathlib import Path
import sqlite3
from snapshot_database import sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--source-features', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    root.relative_to(Path('E:/BrainFusion-Runtime/results/nightly').resolve())
    fixture = json.loads((root / 'fixture.json').read_text(encoding='utf-8'))
    artifacts = {}
    for key, path in {**fixture['sequences'], 'mask': fixture['mask']}.items():
        resolved = Path(path).resolve(strict=True)
        resolved.relative_to(root / 'e2-fixture')
        digest = sha256(resolved)
        assert digest == sha256(Path(fixture['originals'][key])), key
        artifacts[key] = digest
    tables = {}
    with sqlite3.connect((root / 'database-backup/snapshot.db').as_uri() + '?mode=ro', uri=True) as saved:
        with sqlite3.connect((root / 'database-backup/restored-validation.db').as_uri() + '?mode=ro', uri=True) as current:
            assert current.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            for (table,) in saved.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
                query = 'SELECT * FROM "' + table.replace('"', '""') + '"'
                original_rows, current_rows = set(saved.execute(query)), set(current.execute(query))
                assert original_rows.issubset(current_rows), f'Original row changed or removed: {table}'
                tables[table] = {'original_rows_unchanged': len(original_rows), 'new_fixture_rows': len(current_rows) - len(original_rows)}
    features = 0
    for source in args.source_features.resolve(strict=True).rglob('*'):
        if source.is_file():
            target = root / 'feature_jobs' / source.relative_to(args.source_features.resolve())
            assert sha256(source) == sha256(target), str(source.relative_to(args.source_features))
            features += 1
    print(json.dumps({'status': 'passed', 'fixture_restored_sha256': artifacts, 'tables': tables,
                      'original_feature_files_unchanged': features, 'database_integrity': 'ok',
                      'scope': 'Every pre-run database row and copied original feature file retained; owned input/mask copies equal restore originals.'}, indent=2))


if __name__ == '__main__':
    main()
