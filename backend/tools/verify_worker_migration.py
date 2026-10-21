"""Capture old CPU results; verify new worker/values/cache/report isolation/restart.

HTTP against the single registered service. One existing engineering case gets
a new CPU job; unknown-clinical old demo cases must remain unavailable.
No MRI upload, segmentation, training or clinical edits.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import urllib.error
import urllib.request

CASES = (17,)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['capture','extract','restart'],required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--baseline',type=Path)
    parser.add_argument('--completed',type=Path)
    parser.add_argument('--api-base',default='http://127.0.0.1:8012')
    parser.add_argument('--source-db',type=Path,required=True)
    parser.add_argument('--copied-db',type=Path)
    args=parser.parse_args()
    output=args.output.resolve();output.relative_to(Path('E:/BrainFusion-Runtime/results/nightly').resolve());output.mkdir(exist_ok=False)
    checks=[]
    def request(path,method='GET'):
        # No body means reuse the versioned case input; {} would instead be
        # validated as an explicitly supplied, incomplete ClinicalInput.
        data=None
        req=urllib.request.Request(args.api_base+path,data=data,method=method,headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=30) as response:return response.status,json.load(response)['data']
        except urllib.error.HTTPError as error:
            return error.code,json.load(error)
    def get(path):
        status,value=request(path);assert status==200,(path,status,value);return value
    def signature():
        data={}
        for row in get('/cases/'):
            identifier=row['id']
            data[str(identifier)]={'detail':get(f'/cases/{identifier}/detail'),'opinion':get(f'/cases/{identifier}/doctor-opinion')}
            if (data[str(identifier)]['detail'].get('mri') or {}).get('id'):
                data[str(identifier)]['annotations']=get(f'/mri/{identifier}/annotations')
        return data
    def db_rows(path):
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as connection:
            connection.row_factory=sqlite3.Row
            assert connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            names=[r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            return {name:[dict(row) for row in connection.execute('SELECT * FROM "'+name.replace('"','""')+'" ORDER BY 1')] for name in names}
    current=signature()
    if args.mode=='capture':
        protected=[Path('E:/BrainFusion-Runtime/envs/radiomics39/source.json'),Path('E:/BrainFusion-Runtime/envs/radiomics39/python.exe'),
                   Path('E:/BrainFusion-AI/.conda/brainfusion/python.exe'),Path('E:/BrainFusion-AI/backend/tools/extract_selected_radiomics.py'),
                   Path('E:/BrainFusion-AI/backend/app/research/feature_contract.py')]
        jobs={str(i):get(f'/research/cases/{i}/features') for i in CASES}
        origins={str(i):'current API' for i in CASES}
        inputs={str(i):get(f'/research/cases/{i}/clinical-input') for i in CASES}
        if any(job is None for job in jobs.values()):
            raise ValueError('Migration baseline needs an existing successful current job and unchanged valid clinical input')
        value={'signature':current,'features':jobs,'old_feature_origins':origins,'clinical_inputs':inputs,
               'source_database_rows':db_rows(args.source_db),'protected_sha256':{str(p):digest(p) for p in protected}}
        assert all(j['state']=='succeeded' and not j.get('stale',False) for j in value['features'].values())
        (output/'baseline.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
        checks.append('All18 case/report/confirmation/clinical/opinion/annotation and case17 old feature result captured; source database/protected environments fingerprinted')
    else:
        before=json.loads(args.baseline.read_text(encoding='utf-8'))
        assert current==before['signature'],'Case/report/clinical/opinion/annotation/analysis changed'
        assert db_rows(args.source_db)==before['source_database_rows'],'Original source database modified'
        assert args.copied_db and db_rows(args.copied_db)==before['source_database_rows'],'Copied database science/rows changed'
        assert all(digest(Path(path))==sha for path,sha in before['protected_sha256'].items())
        checks.append('All18 case signatures, original/copy database rows, main/legacy Python and extraction protocol unchanged')
        if args.mode=='extract':
            records=[]
            for identifier in CASES:
                status,job=request(f'/research/cases/{identifier}/features','POST')
                assert status==202,(status,job)
                assert job['id']!=before['features'][str(identifier)]['id'],'New worker must not reuse old worker cache'
                duplicate_status,duplicate=request(f'/research/cases/{identifier}/features','POST')
                assert duplicate_status in (202,409),(duplicate_status,duplicate)
                if duplicate_status==202:assert duplicate['id']==job['id'] and duplicate['cache_hit']
                else:assert get(f'/research/cases/{identifier}/features')['id']==job['id']
                deadline=time.monotonic()+120
                while job['state'] in ('queued','running') and time.monotonic()<deadline:
                    time.sleep(.25);job=get(f'/research/cases/{identifier}/features')
                assert job['state']=='succeeded' and not job.get('stale'),job
                old=before['features'][str(identifier)]
                new_values,old_values=job['result'],old['result']
                assert new_values['versions']['python']=='3.11.17' and new_values['versions']['pyradiomics']=='v3.1.0'
                for key in ('input_sha256','mask_sha256','region_voxel_counts','contract_sha256','device','feature_source','target'):
                    assert new_values[key]==old_values[key],(identifier,key)
                assert new_values['device']=='cpu'
                assert job['analysis_run_id']==old['analysis_run_id']
                assert job['clinical_input_version']==before['clinical_inputs'][str(identifier)]['version']
                assert job['clinical_input']==old['clinical_input']
                differences={}
                assert set(new_values['selected_features'])==set(old_values['selected_features'])
                for name,value in old_values['selected_features'].items():
                    new=new_values['selected_features'][name]
                    if value is None:assert new is None
                    else:assert new is not None and abs(new-value)<=1e-8+1e-5*abs(value),(identifier,name,new,value)
                for name,value in old_values['probabilities'].items():
                    differences[name]=abs(value-new_values['probabilities'][name]);assert differences[name]<1e-6
                status,cached=request(f'/research/cases/{identifier}/features','POST')
                assert status==202 and cached['id']==job['id'] and cached['cache_hit']
                records.append({'case_id':identifier,'job':get(f'/research/cases/{identifier}/features'),'old_job_id':old['id'],
                                'probability_absolute_differences':differences,'duplicate_status':duplicate_status,'cache_hit_same_id':True})
                (output/'completed.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
                print(f'Case {identifier}: supported CPU worker, same20 features/probabilities, new provenance, same clinical/analysis version, duplicate/cache PASS',flush=True)
            assert signature()==before['signature'] and db_rows(args.copied_db)==before['source_database_rows']
            for unavailable in (11,12,13,14,15):
                clinical=get(f'/research/cases/{unavailable}/clinical-input')
                assert not clinical['available'] and clinical['female'] is None
                status,detail=request(f'/research/cases/{unavailable}/features','POST')
                assert status==409 and detail.get('detail'),(unavailable,status,detail)
                assert get(f'/research/cases/{unavailable}/features') is None
            checks.append('Case17 actual CPU extraction matches old20 features/probabilities, worker cache separation and same-ID repeat; five unknown-clinical legacy demos explicitly rejected, no fabricated input')
        else:
            completed=json.loads(args.completed.read_text(encoding='utf-8'))
            for record in completed:
                identifier=record['case_id'];job=get(f'/research/cases/{identifier}/features')
                assert job==record['job'],(identifier,'Saved job/result changed after restart')
                status,cached=request(f'/research/cases/{identifier}/features','POST')
                assert status==202 and cached['id']==job['id'] and cached['cache_hit']
            checks.append('Supported-worker job/result persists exactly after actual service restart; repeat cache-hit without extraction')
    (output/'validation.json').write_text(json.dumps({'status':'passed','mode':args.mode,'checks':checks,'new_segmentation_or_training':False},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'passed','mode':args.mode,'checks':checks}),flush=True)


if __name__=='__main__':main()
