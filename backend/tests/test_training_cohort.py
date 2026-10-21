from pathlib import Path
import io,json,zipfile,hashlib
import pytest
from tools.prepare_training_cohort import CachedRangeFile,select_patients,extract_member

def fixtures():
    ids=[str(i) for i in range(20,33)];inv=[dict(member=f'x/{p}/{p}_0_brain_{s}.nii.gz',bytes=5,compressed_bytes=5) for p in ids for s in ['t1c','t1n','t2w','t2f']]
    return inv,[f'm/{p}/{p}_0_tumor_mask_pre.nii.gz' for p in ids],{'patient_ids':{'train':ids[:11],'validation':[ids[11]],'test':[ids[12]]}}
def test_selection_never_uses_validation_or_test_or_engineering():
    inv,masks,split=fixtures();rows=select_patients(inv,masks,split)
    assert [r['patient_id'] for r in rows]==[str(i) for i in range(20,30)]
    assert all(r['role']=='train' and r['examination']=='0' for r in rows)
def test_duplicate_sequence_is_not_guessed_or_silently_used():
    inv,masks,split=fixtures();inv.append(inv[0]);rows=select_patients(inv,masks,split)
    assert '20' not in [r['patient_id'] for r in rows]
    split['patient_ids']['test'].append('21')
    with pytest.raises(ValueError,match='overlap'):select_patients(inv,masks,split)
def test_missing_pair_or_small_cohort_explicitly_fails():
    inv,masks,split=fixtures()
    with pytest.raises(ValueError,match='Insufficient'):select_patients(inv,masks[:9],split)
    with pytest.raises(ValueError,match='10-20'):select_patients(inv,masks,split,9)
class Response(io.BytesIO):
    status=206
    def __init__(self,data,start,stop,size):super().__init__(data);self.headers={'Content-Range':f'bytes {start}-{stop}/{size}'}
def opener(data,calls):
    def open_(req,timeout):
        a,b=map(int,req.headers['Range'][6:].split('-'));calls.append((a,b));return Response(data[a:b+1],a,b,len(data))
    return open_
def test_ranges_seek_cache_and_resume_partial_at_exact_offset(tmp_path):
    data=b'abcdefghijkl';calls=[]
    (tmp_path/'0-3.part').write_bytes(b'ab')
    r=CachedRangeFile('https://example.test/data',len(data),tmp_path,opener(data,calls),4)
    assert r.read(7)==data[:7] and calls==[(2,3),(4,7)]
    r.seek(-4,2);assert r.read()==data[-4:]
    r.seek(0);assert r.read()==data and len(calls)==3
    r2=CachedRangeFile('https://example.test/data',12,tmp_path,opener(data,calls),4)
    assert r2.read()==data and len(calls)==3
    (tmp_path/'0-3.bin').write_bytes(b'xxxx')
    with pytest.raises(ValueError,match='integrity'):r2.seek(0);r2.read(1)
def test_server_ignoring_range_never_saves_large_response(tmp_path):
    def bad(req,timeout):
        r=Response(b'x'*100,0,99,100);r.status=200;return r
    r=CachedRangeFile('https://example.test/data',100,tmp_path,bad,4)
    with pytest.raises(ValueError,match='exact range'):r.read(1)
    assert not list(tmp_path.glob('*.bin')) and not list(tmp_path.glob('*.part'))
def test_truncated_response_keeps_partial_and_resumes(tmp_path):
    calls=[]
    def short(req,timeout):return Response(b'ab',0,3,4)
    r=CachedRangeFile('https://example.test/data',4,tmp_path,short,4)
    with pytest.raises(ValueError,match='Truncated'):r.read(4)
    assert (tmp_path/'0-3.part').read_bytes()==b'ab'
    r=CachedRangeFile('https://example.test/data',4,tmp_path,opener(b'abcd',calls),4)
    assert r.read()==b'abcd' and calls==[(2,3)]
def test_member_traversal_and_existing_drift_fail_without_overwrite(tmp_path):
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z:z.writestr('../bad.nii.gz',b'bad');z.writestr('p/20.nii.gz',b'good')
    with zipfile.ZipFile(buf) as z:
        with pytest.raises(ValueError,match='Unsafe'):extract_member(z,'../bad.nii.gz',tmp_path)
        row=extract_member(z,'p/20.nii.gz',tmp_path);p=Path(row['path']);p.write_bytes(b'drift')
        with pytest.raises(ValueError,match='never overwrite'):extract_member(z,'p/20.nii.gz',tmp_path)
        assert p.read_bytes()==b'drift'


def test_real_nifti_geometry_counts_and_nonfinite_rejection(tmp_path):
    import nibabel as nib
    import numpy as np
    from tools.prepare_training_cohort import geometry
    patient={'images':{},'reference_mask':{'path':str(tmp_path/'mask.nii.gz')}}
    for key in ['t1c','t1n','t2w','t2f']:
        p=tmp_path/(key+'.nii.gz');nib.save(nib.Nifti1Image(np.arange(64,dtype=np.float32).reshape(4,4,4),np.eye(4)),p);patient['images'][key]={'path':str(p)}
    nib.save(nib.Nifti1Image(np.ones((4,4,4),dtype=np.uint8),np.eye(4)),patient['reference_mask']['path'])
    result=geometry(patient)
    assert result['reference_region_voxels']=={'1':64,'2':0,'3':0,'4':0} and result['no_registration_or_resampling']
    data=np.arange(64,dtype=np.float32).reshape(4,4,4);data[0,0,0]=np.nan
    nib.save(nib.Nifti1Image(data,np.eye(4)),patient['images']['t2f']['path'])
    with pytest.raises(ValueError,match='Invalid MRI'):geometry(patient)
def test_real_nifti_mismatched_affine_and_illegal_mask_fail(tmp_path):
    import nibabel as nib
    import numpy as np
    from tools.prepare_training_cohort import geometry
    patient={'images':{},'reference_mask':{'path':str(tmp_path/'mask.nii.gz')}}
    for key in ['t1c','t1n','t2w','t2f']:
        p=tmp_path/(key+'.nii.gz');nib.save(nib.Nifti1Image(np.arange(64,dtype=np.float32).reshape(4,4,4),np.eye(4)),p);patient['images'][key]={'path':str(p)}
    affine=np.eye(4);affine[0,3]=2
    nib.save(nib.Nifti1Image(np.ones((4,4,4),dtype=np.uint8),affine),patient['reference_mask']['path'])
    with pytest.raises(ValueError,match='affine'):geometry(patient)
    nib.save(nib.Nifti1Image(np.full((4,4,4),5,dtype=np.uint8),np.eye(4)),patient['reference_mask']['path'])
    with pytest.raises(ValueError,match='invalid labels'):geometry(patient)
def test_resume_cannot_claim_ten_patients_with_missing_or_repeated_rows(tmp_path):
    from tools.prepare_training_cohort import verify_prepared
    config={'patients':[{'patient_id':str(i)} for i in range(10)]}
    report={'config_sha256':'a'*64,'status':'prepared_not_inferred','distinct_patients':10,'patients':[{'patient_id':'0'}]*10}
    with pytest.raises(ValueError,match='denominator'):verify_prepared(report,config,'a'*64,tmp_path)
    report['patients']=[{'patient_id':str(i)} for i in range(9)]
    with pytest.raises(ValueError,match='denominator'):verify_prepared(report,config,'a'*64,tmp_path)
