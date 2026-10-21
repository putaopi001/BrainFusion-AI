"""Audit immutable backup/source files and relocated DB scientific fields."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.snapshot_database import sha256, counts
from tools.snapshot_system import PATH_COLUMNS, JSON_COLUMNS


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',type=Path,required=True);parser.add_argument('--restored',type=Path,required=True)
    args=parser.parse_args(); snapshot=args.snapshot.resolve(strict=True);restored=args.restored.resolve(strict=True)
    manifest=json.loads((snapshot/'manifest.json').read_text(encoding='utf-8'))
    assert sha256(snapshot/'database.db')==manifest['snapshot_database_sha256']
    exact={}; mapping=sorted(manifest['root_mapping'],key=lambda m:len(m['relative']),reverse=True)
    assert len({item['relative'] for item in manifest['files']})==len(manifest['files'])
    for item in manifest['files']:
        assert sha256(snapshot/item['relative'])==item['sha256']
        assert sha256(Path(item['source']))==item['sha256'], 'Original file was changed: '+item['relative']
        if not (item['relative'].startswith('feature_jobs/') and Path(item['relative']).name in {'state.json','request.json'}):
            assert sha256(restored/item['relative'])==item['sha256'], 'Restored asset changed: '+item['relative']
        exact[str((restored/item['relative']).resolve()).casefold()]=str(Path(item['source']).resolve()).casefold()
    def canonical(value,undo=False):
        if isinstance(value,dict):return {k:canonical(v,undo) for k,v in value.items()}
        if isinstance(value,list):return [canonical(v,undo) for v in value]
        if not isinstance(value,str) or not Path(value).is_absolute():return value
        path=Path(value).resolve()
        if undo:
            if str(path).casefold() in exact:return exact[str(path).casefold()]
            for item in mapping:
                try:relative=path.relative_to(restored/item['relative'])
                except ValueError:continue
                return str((Path(item['source'])/relative).resolve()).casefold()
        return str(path).casefold()
    checked={}
    with sqlite3.connect((snapshot/'database.db').as_uri()+'?mode=ro',uri=True) as old:
        with sqlite3.connect((restored/'database.db').as_uri()+'?mode=ro',uri=True) as new:
            with sqlite3.connect(Path(manifest['source_database']).as_uri()+'?mode=ro',uri=True) as source:
                old.row_factory=new.row_factory=source.row_factory=sqlite3.Row
                assert counts(old)==counts(new)==counts(source)==manifest['row_counts']
                for table in manifest['row_counts']:
                    # case_research_inputs uses case_id, not id, as its first primary key.
                    query='SELECT * FROM "'+table.replace('"','""')+'" ORDER BY 1'
                    before,after,original=list(old.execute(query)),list(new.execute(query)),list(source.execute(query))
                    assert [dict(r) for r in before]==[dict(r) for r in original], 'Original DB changed: '+table
                    for a,b in zip(before,after):
                        for key in a.keys():
                            if key in PATH_COLUMNS or (table=='mris' and key=='web_path'):continue
                            if key in JSON_COLUMNS and a[key]:
                                try: av,bv=json.loads(a[key]),json.loads(b[key])
                                except ValueError: assert a[key]==b[key];continue
                                assert canonical(av)==canonical(bv,True),(table,a['id'],key)
                            else:assert a[key]==b[key],(table,a['id'],key)
                    checked[table]=len(before)
    print(json.dumps({'status':'passed','original_and_backup_files_sha256_unchanged':len(manifest['files']),
                      'snapshot_database_sha256_unchanged':True,'original_database_rows_unchanged':True,
                      'restored_scientific_and_version_fields_unchanged':checked,
                      'scope':'Only operational paths/cache keys relocated; source/snapshot remain immutable; actual probability/cache/image/browser checks recorded separately.'},indent=2))


if __name__=='__main__':main()
