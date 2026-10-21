"""Read-only local DICOM preflight CLI; no archive upload or source rewrite."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.dicom_preflight import audit_dicom

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--source-manifest',type=Path)
    parser.add_argument('--pixel-review',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    target=args.output.resolve()
    if target.drive.upper()!='E:' or target.exists():
        parser.error('Fresh output on E: required; no output overwritten')
    def read(path):
        if path is None:return None
        if path.stat().st_size>65536:raise ValueError()
        return json.loads(path.read_text(encoding='utf-8-sig'))
    try:
        report=audit_dicom(args.input,read(args.source_manifest),read(args.pixel_review))
    except Exception:
        report={'policy_version':'local-mr-import-preflight-v1','decision':'rejected','archive_eligible':False,
                'deidentification_complete':False,'archive_imported':False,'findings':[{'reason':'invalid_input_or_manifest','tag_path':'Input','severity':'blocking'}]}
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8') as handle:json.dump(report,handle,ensure_ascii=False,indent=2)
    print(json.dumps({'decision':report['decision'],'archive_eligible':report['archive_eligible'],'findings_count':len(report['findings']),'source_unchanged_by_tool':True}))
    return 0 if report['decision'] in ('engineering_fixture_pass','preflight_checks_passed') else 3

if __name__=='__main__':raise SystemExit(main())
