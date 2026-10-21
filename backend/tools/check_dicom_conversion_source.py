"""Read-only source observation; private local PACS config, never archive upload."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.config import settings
from app.services.dicom_conversion_source import check_conversion_sources
from plan_dicom_model_input import read


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['version-dir','report-sha256','proposal','snapshots','output']:
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--pacs-config')
    args=parser.parse_args()
    output=Path(args.output).resolve()
    if (output.drive.upper()!='E:' or not output.parent.is_dir() or output.suffix.lower()!='.json'
            or output.exists() or output.is_relative_to(Path(args.version_dir).resolve())):
        parser.error('Use a new E-drive JSON outside the inspected version; never overwrite.')
    if args.pacs_config:settings.PACS_CONFIG_FILE=args.pacs_config
    try:
        proposal,psha=read(args.proposal,4*1024*1024)
        snapshots,ssha=read(args.snapshots,16*1024*1024)
        report=check_conversion_sources(args.version_dir,args.report_sha256,proposal,snapshots)
        report['input_file_sha256']={'proposal':psha,'snapshots':ssha}
    except (OSError,ValueError,UnicodeError,RecursionError):
        report={'status':'invalid','reason':'invalid_input_files','model_input_eligible':False,'archive_written':False}
    with output.open('x',encoding='utf-8') as handle:json.dump(report,handle,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({'status':report['status'],'reason':report.get('reason'),'model_input_eligible':False,'archive_written':False}))
    return 0 if report['status']=='matched_at_check' else 3


if __name__=='__main__':raise SystemExit(main())
