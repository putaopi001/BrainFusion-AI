"""Frozen training-only NIfTI pilot preparation; no labels inferred or services changed."""
import argparse, hashlib, io, json, os, re, sys, urllib.request, zipfile, zlib
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
ROLES={'train','validation','test'}
SEQUENCES={'t1c','t1n','t2w','t2f'}

def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()
def save(path,data):
    path=Path(path); tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');tmp.replace(path)
def select_patients(inventory,mask_names,split,count=10):
    roles=split['patient_ids']
    if set(roles)!=ROLES or not 10<=count<=20: raise ValueError('Frozen 10-20 patient pilot and train/validation/test roles required')
    sets=[set(roles[k]) for k in sorted(ROLES)]
    if any(len(roles[k])!=len(set(roles[k])) for k in ROLES) or any(sets[i]&sets[j] for i in range(3) for j in range(i+1,3)):raise ValueError('Patient roles overlap or duplicate')
    groups={}
    for row in inventory:
        name=PurePosixPath(row['member']).name
        m=re.fullmatch(r'(\d+)_0_brain_(t1c|t1n|t2w|t2f)\.nii.gz',name)
        if m:
            pid,seq=m.groups();groups.setdefault(pid,{}).setdefault(seq,[]).append(row)
    masks={}
    for name in mask_names:
        m=re.fullmatch(r'(\d+)_0_tumor_mask_pre.nii.gz',PurePosixPath(name).name)
        if m:masks.setdefault(m[1],[]).append(name)
    eligible=sorted((pid for pid,g in groups.items() if pid in set(roles['train'])-{'4','13','16','17','19'} and set(g)==SEQUENCES and all(len(v)==1 for v in g.values()) and len(masks.get(pid,[]))==1),key=int)
    if len(eligible)<count:raise ValueError('Insufficient unique training-only four-sequence/exam0/reference-mask patients')
    return [{'patient_id':pid,'role':'train','examination':'0','images':{s:groups[pid][s][0] for s in sorted(SEQUENCES)},'reference_mask_member':masks[pid][0]} for pid in eligible[:count]]

class CachedRangeFile(io.RawIOBase):
    """Aligned persistent ranges; interrupted .part continues at its exact byte offset."""
    def __init__(self,url,size,root,opener=urllib.request.urlopen,block_size=1048576):
        self.url,self.size,self.root,self.opener,self.block_size=url,size,Path(root),opener,block_size
        self.root.mkdir(parents=True,exist_ok=True);self.pos=0;self.transferred=0;self.hits=0
    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.pos
    def seek(self,offset,whence=0):
        n=offset if whence==0 else self.pos+offset if whence==1 else self.size+offset if whence==2 else -1
        if n<0:raise ValueError('Negative or invalid seek')
        self.pos=n;return n
    def block(self,start):
        stop=min(start+self.block_size,self.size)-1;total=stop-start+1
        p=self.root/f'{start}-{stop}.bin';receipt=p.with_suffix('.sha256')
        if p.exists():
            if p.stat().st_size!=total or not receipt.is_file() or sha(p)!=receipt.read_text().strip():raise ValueError('Cached range integrity mismatch')
            self.hits+=1;return p.read_bytes()
        part=p.with_suffix('.part');offset=part.stat().st_size if part.exists() else 0
        if offset>total:raise ValueError('Partial range exceeds frozen block')
        if offset<total:
            req=urllib.request.Request(self.url,headers={'Range':f'bytes={start+offset}-{stop}','Accept-Encoding':'identity'})
            with self.opener(req,timeout=30) as response:
                if response.status!=206 or response.headers.get('Content-Range')!=f'bytes {start+offset}-{stop}/{self.size}':raise ValueError('Server did not honor exact range; no unbounded download')
                with part.open('ab') as output:
                    remaining=total-offset
                    while remaining:
                        chunk=response.read(min(65536,remaining))
                        if not chunk:raise ValueError('Truncated range; partial retained for resume')
                        output.write(chunk);self.transferred+=len(chunk);remaining-=len(chunk)
                    if response.read(1):raise ValueError('Oversized range response')
        digest=sha(part);part.replace(p);receipt.write_text(digest,encoding='ascii');return p.read_bytes()
    def read(self,n=-1):
        n=min(self.size-self.pos,n if n>=0 else self.size-self.pos)
        if n<=0:return b''
        chunks=[]
        while n:
            start=self.pos//self.block_size*self.block_size;block=self.block(start);offset=self.pos-start;take=min(n,len(block)-offset)
            chunks.append(block[offset:offset+take]);self.pos+=take;n-=take
        return b''.join(chunks)

def extract_member(archive,name,root,expected=None):
    member=archive.getinfo(name);relative=PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts or '\\' in name:raise ValueError('Unsafe archive member')
    if member.file_size>100_000_000 or member.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):raise ValueError('Unsupported archive member')
    if expected and (member.file_size!=expected['bytes'] or member.compress_size!=expected['compressed_bytes']):raise ValueError('Member inventory differs from frozen plan')
    p=(Path(root)/name).resolve();p.relative_to(Path(root).resolve());p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists():
        data=p.read_bytes()
        if len(data)!=member.file_size or zlib.crc32(data)!=member.CRC:raise ValueError('Existing member differs; never overwrite')
    else:
        data=archive.read(name) # zipfile verifies full-member CRC; no scripts executed.
        part=p.with_suffix(p.suffix+'.part');part.write_bytes(data);part.replace(p)
    return dict(member=name,path=str(p),bytes=len(data),zip_crc32=f'{member.CRC:08x}',sha256=sha(p))

def geometry(patient):
    import nibabel as nib
    import numpy as np
    from app.services.study_validation import validate_sequences
    from app.services.segmentation_metrics import validate_mask
    paths={k:v['path'] for k,v in patient['images'].items()};ref=validate_sequences(paths)
    mask_image=nib.load(patient['reference_mask']['path']);mask=validate_mask(mask_image,ref)
    for path in paths.values():
        data=nib.load(path).get_fdata(dtype=np.float32)
        if not np.isfinite(data).all() or data.max()<=data.min():raise ValueError('Invalid MRI values')
    return dict(shape=list(ref.shape),affine=ref.affine.tolist(),spacing_mm=list(map(float,ref.header.get_zooms())),axis_codes=list(nib.aff2axcodes(ref.affine)),reference_labels=np.unique(mask).tolist(),reference_region_voxels={str(k):int((mask==k).sum()) for k in (1,2,3,4)},no_registration_or_resampling=True)

def validated_config(config_path,config_sha,protocol_sha):
    if sha(config_path)!=config_sha.lower():raise ValueError('Frozen configuration/protocol SHA mismatch')
    config=read(config_path)
    if sha(config['protocol_path'])!=protocol_sha.lower():raise ValueError('Frozen configuration/protocol SHA mismatch')
    if config['protocol']!='brainfusion_training_pilot_v1' or config['selection']!='lowest_numeric_training_ids_exam0' or config['count']!=10:raise ValueError('Unexpected pilot protocol')
    for path,digest in config['input_sha256'].items():
        if sha(path)!=digest:raise ValueError('Frozen input SHA mismatch')
    record=read(config['record']); files={v['key']:v for v in record['files']};item=files['2_1_preop_scans_coreg.zip']
    if record['id']!=22205631 or record['metadata']['access_right']!='open' or record['metadata']['license']['id']!='cc-by-4.0':raise ValueError('Unexpected dataset/license')
    root=Path(config['output']).resolve();root.relative_to(Path('E:/BrainFusion-Data').resolve())
    if not root.is_dir():raise ValueError('Frozen output directory must exist')
    with zipfile.ZipFile(config['mask_archive']) as masks:
        chosen=select_patients(read(config['inventory']),masks.namelist(),read(config['split']),config['count'])
    if chosen!=config['patients']:raise ValueError('Frozen patient selection differs')
    return config,record,item,root,chosen

def verify_prepared(report,config,config_sha,root):
    if report.get('config_sha256')!=config_sha.lower():raise ValueError('Existing cohort configuration mismatch')
    planned=config['patients'];patients=report.get('patients',[])
    if report.get('status')!='prepared_not_inferred' or report.get('distinct_patients')!=len(planned) or [p.get('patient_id') for p in patients]!=[p['patient_id'] for p in planned]:raise ValueError('Prepared cohort patient denominator/order differs')
    for actual,expected in zip(patients,planned):
        if actual.get('role')!='train' or actual.get('examination')!='0' or set(actual.get('images',{}))!=SEQUENCES:raise ValueError('Prepared cohort role/exam/sequence identity differs')
        rows=[(actual['images'][k],root/'images'/expected['images'][k]['member']) for k in SEQUENCES]+[(actual['reference_mask'],root/'reference_masks'/expected['reference_mask_member'])]
        for row,path in rows:
            if Path(row['path']).resolve()!=path.resolve() or sha(path)!=row['sha256']:raise ValueError('Prepared cohort input identity or SHA changed')

def prepare(config_path,config_sha,protocol_sha):
    config,record,item,root,chosen=validated_config(config_path,config_sha,protocol_sha)
    complete=root/'prepared.json'
    if complete.exists():
        seal=complete.with_suffix('.sha256')
        if not seal.is_file() or sha(complete)!=seal.read_text().strip():raise ValueError('Prepared manifest integrity mismatch')
        report=read(complete);verify_prepared(report,config,config_sha,root)
        return report
    with zipfile.ZipFile(config['mask_archive']) as masks:
        # One current official metadata lookup binds new bytes to the known record.
        with urllib.request.urlopen('https://zenodo.org/api/records/22205631',timeout=30) as response:current=json.load(response)
        fresh={v['key']:v for v in current['files']}[item['key']]
        if current['id']!=record['id'] or current['metadata']['access_right']!='open' or current['metadata']['license']['id']!='cc-by-4.0' or any(fresh[k]!=item[k] for k in ['size','checksum']):raise ValueError('Official dataset version/size/checksum changed')
        save(root/'source-checked.json',dict(record_id=record['id'],url=item['links']['self'],published_bytes=item['size'],published_checksum=item['checksum'],license='CC-BY-4.0',checked_utc=datetime.now(timezone.utc).isoformat(),verification='selected ZIP member CRC32 + local SHA256; full archive MD5 not verified'))
        remote=CachedRangeFile(item['links']['self'],item['size'],root/'range-cache')
        patients=[]
        with zipfile.ZipFile(remote) as images:
            for p in chosen:
                entry=dict(patient_id=p['patient_id'],role='train',examination='0',images={})
                for seq,row in p['images'].items():entry['images'][seq]=extract_member(images,row['member'],root/'images',row)
                entry['reference_mask']=extract_member(masks,p['reference_mask_member'],root/'reference_masks')
                entry['geometry']=geometry(entry);patients.append(entry)
                save(root/'progress.json',dict(state='running',patients=patients,planned=10,range_bytes_this_attempt=remote.transferred,config_sha256=config_sha.lower()))
                print(f"Prepared training patient {p['patient_id']}: 4 MRI + reference mask; geometry/finite/CRC/SHA passed",flush=True)
        report=dict(status='prepared_not_inferred',patients=patients,config_sha256=config_sha.lower(),protocol_sha256=protocol_sha.lower(),source=read(root/'source-checked.json'),range_bytes_this_attempt=remote.transferred,cache_hits=remote.hits,distinct_patients=10,independent_evaluation=False)
        save(complete,report);complete.with_suffix('.sha256').write_text(sha(complete),encoding='ascii');return report

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',required=True);parser.add_argument('--config-sha256',required=True);parser.add_argument('--protocol-sha256',required=True)
    args=parser.parse_args();config,_,_,root,_=validated_config(args.config,args.config_sha256,args.protocol_sha256)
    job=root/'job.json';state=dict(pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),config=str(Path(args.config).resolve()),config_sha256=args.config_sha256,protocol_sha256=args.protocol_sha256,state='running',output=str(root),log=config['log'])
    save(job,state)
    try:
        result=prepare(args.config,args.config_sha256,args.protocol_sha256);state.update(state='succeeded',distinct_patients=result['distinct_patients'])
    except Exception as exc:
        state.update(state='failed',error=type(exc).__name__+': '+str(exc));raise
    finally:
        state['ended_utc']=datetime.now(timezone.utc).isoformat();save(job,state)
if __name__=='__main__':main()
