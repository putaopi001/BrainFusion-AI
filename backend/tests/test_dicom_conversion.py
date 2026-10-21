"""True local GDCM conversion of explicitly synthetic Part10 files, no cohort."""
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import nibabel as nib
import numpy as np
import pydicom
import pytest
from pydicom.dataset import Dataset, FileDataset, FileMetaDataset

from app.services.dicom_conversion import convert_and_verify, source_dataset
from app.services.dicom_input_plan import PlanError, validate_plan, ROLES
from app.services.dicom_series import validate_series
from test_dicom_input_plan import inputs
from test_dicom_series import tag


def files_fixture(tmp_path, negative=False, scaled=False, pixel_layout='signed16', resampling=False):
    proposal,bundle=inputs()
    folder=tmp_path/'SYNTHETIC-original';folder.mkdir()
    files={};voxel_references={}
    for i,role in enumerate(ROLES):
        source=bundle['series'][i]
        raw=[]
        for k,row in enumerate(source['instances']):
            metadata=copy.deepcopy(row['metadata'])
            if resampling and role=='t2w':
                # A denser input matrix with the same physical field of view.
                metadata['00280010']=tag(3,'US');metadata['00280011']=tag(5,'US')
                metadata['00280030']=tag([.5,.5],'DS')
            if pixel_layout != 'signed16':
                metadata['00280010']=tag(3,'US');metadata['00280011']=tag(3,'US')
                allocated,stored,representation=(8,8,0) if pixel_layout=='unsigned8' else (16,12,1)
                for code,value in [('00280100',allocated),('00280101',stored),('00280102',stored-1),('00280103',representation)]:
                    metadata[code]=tag(value,'US')
            if negative:
                metadata['00200037']=tag([-1,0,0,0,1,0],'DS')
                metadata['00200032']=tag([10,20,30-k],'DS')
            if scaled:
                metadata['00281053']=tag([-.5,1.5,2][k],'DS')
                metadata['00281052']=tag(-20+k,'DS')
            # Parsing standard JSON numeric DS values preserves semantic meaning.
            ds=Dataset.from_json(metadata)
            uid=str(ds.SOPInstanceUID)
            meta=FileMetaDataset();meta.MediaStorageSOPClassUID=ds.SOPClassUID
            meta.MediaStorageSOPInstanceUID=uid;meta.TransferSyntaxUID=pydicom.uid.ExplicitVRLittleEndian
            meta.ImplementationClassUID='2.25.999123'
            file=folder/('misleading-name-'+str(100-k)+'-'+role+'.dcm')
            obj=FileDataset(str(file),{},file_meta=meta,preamble=b'\0'*128)
            obj.update(ds)
            obj.PatientID='SYNTHETIC_ONLY';obj.PatientName='SYNTHETIC^NO_REAL_PERSON'
            obj.BurnedInAnnotation='NO';obj.SeriesNumber=i+1
            rows=int(ds.Rows);columns=int(ds.Columns)
            if pixel_layout=='unsigned8':
                pixels=(np.arange(rows*columns).reshape(rows,columns)+k*20+i*50).astype('u1')
            elif pixel_layout=='signed12':
                pixels=(np.arange(rows*columns).reshape(rows,columns)+k*20+i*100-80).astype('<i2')
            else:pixels=(np.arange(rows*columns).reshape(rows,columns)+k*20+i*100-80).astype('<i2')
            obj.PixelData=pixels.tobytes()
            obj.save_as(file,enforce_file_format=True)
            files[uid]={'path':str(file),'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
            voxel_references[uid]=pixels.astype(np.float32)*float(obj.get('RescaleSlope',1))+float(obj.get('RescaleIntercept',0))
            raw.append(metadata)
        updated=validate_series(SimpleNamespace(allow_pixel_read=False),raw,source['study_uid'],source['series_uid'],[r['00080018']['Value'][0] for r in raw])
        updated.update(source_case_id=17,archive_id='SYNTHETIC-plan',archive_fingerprint='1'*64)
        bundle['series'][i]=updated
        proposal['assignments'][i]['series_metadata_sha256']=updated['metadata_sha256']
    if resampling:
        proposal['resampling']={
            'format':'dicom-model-resampling-policy-v1','reference_role':'t1c',
            'target_spacing_xyz_mm':[1,1,1],'interpolation':'linear',
            'coordinate_mapping':'same_frame_of_reference_identity','outside_value':0}
    return proposal,bundle,files,voxel_references


def test_explicit_resampling_converts_and_reopens_against_recomputed_source(tmp_path):
    from app.services.dicom_conversion_integrity import inspect_conversion_version
    proposal,bundle,files,_=files_fixture(tmp_path,resampling=True)
    original={path:Path(path).read_bytes() for path in (record['path'] for record in files.values())}
    output=tmp_path/'resampled-version'
    report=convert_and_verify(proposal,bundle,files,output)
    assert report['status']=='converted_and_verified'
    assert report['converter']['parameters']['registration_or_resampling'] is True
    assert report['target_grid']['dimensions']==[3,2,3]
    assert report['target_grid']['spacing_xyz_mm']==[1,1,1]
    assert report['existing_model_geometry_contract_passed']
    assert not report['model_input_eligible'] and not report['inference_performed']
    for role,row in report['outputs'].items():
        image=nib.load(row['nifti_path'])
        assert image.shape==(3,2,3)
        assert image.header.get_zooms()[:3]==(1,1,1)
        assert row['source_geometry']==next(x for x in bundle['series'] if x['series_uid']==row['source_series_uid'])['geometry']
    inspected=inspect_conversion_version(output,hashlib.sha256((output/'conversion-report.json').read_bytes()).hexdigest(),proposal,bundle)
    assert inspected['status']=='verified_readonly',inspected
    assert {path:Path(path).read_bytes() for path in original}==original


def test_resampling_receipt_cannot_be_changed_to_claim_no_interpolation(tmp_path):
    proposal,bundle,files,_=files_fixture(tmp_path,resampling=True)
    output=tmp_path/'resampled-tamper-version'
    report=convert_and_verify(proposal,bundle,files,output)
    receipt=output/'conversion-report.json'
    document=json.loads(receipt.read_text(encoding='utf-8'))
    document['converter']['parameters']['registration_or_resampling']=False
    receipt.write_text(json.dumps(document),encoding='utf-8')
    from app.services.dicom_conversion_integrity import inspect_conversion_version
    inspected=inspect_conversion_version(output,hashlib.sha256(receipt.read_bytes()).hexdigest(),proposal,bundle)
    assert inspected['status']=='invalid'
    assert inspected['reason']=='conversion_resampling_claim_mismatch'


@pytest.mark.parametrize('pixel_layout',['unsigned8','signed12'])
def test_odd_unsigned_ob_padding_and_signed_low_bits(tmp_path,pixel_layout):
    proposal,bundle,files,references=files_fixture(tmp_path,pixel_layout=pixel_layout)
    report=convert_and_verify(proposal,bundle,files,tmp_path/'converted')
    assert sum(r['all_voxels_compared'] for r in report['outputs'].values())==108
    for row in report['outputs'].values():
        image=nib.load(row['nifti_path'])
        for k,source in enumerate(row['source_instances']):
            np.testing.assert_array_equal(np.asarray(image.dataobj[:,:,k]).T,references[source['instance_uid']])
    if pixel_layout=='unsigned8':
        ds=pydicom.dcmread(next(iter(files.values()))['path'])
        assert len(ds.PixelData)==10 and ds.PixelData[-1]==0


@pytest.mark.parametrize('negative,scaled',[(False,False),(True,True)])
def test_actual_gdcm_signed_rectangular_voxels_negative_direction_rescale_and_model_guard(tmp_path,negative,scaled):
    proposal,bundle,files,references=files_fixture(tmp_path,negative,scaled)
    before={record['path']:Path(record['path']).read_bytes() for record in files.values()}
    report=convert_and_verify(proposal,bundle,files,tmp_path/'converted')
    assert report['status']=='converted_and_verified' and report['data_role']=='synthetic-fixture'
    assert report['original_dicom_byte_hashes_verified'] and report['existing_model_geometry_contract_passed']
    assert not report['model_input_eligible'] and not report['inference_performed'] and not report['archive_or_business_database_written']
    assert report['converter']['parameters']['force_orthogonal_direction'] is False
    assert report['converter']['parameters']['registration_or_resampling'] is False
    for role,result in report['outputs'].items():
        assert result['all_voxels_compared']==18 and result['maximum_absolute_intensity_error']==0
        assert result['expected_scaled_voxel_sha256']==result['actual_voxel_sha256']
        image=nib.load(result['nifti_path'])
        for k,row in enumerate(result['source_instances']):
            np.testing.assert_array_equal(np.asarray(image.dataobj[:,:,k]).T,references[row['instance_uid']])
            assert Path(row['snapshot_path']).read_bytes()==before[files[row['instance_uid']]['path']]
        assert b'SYNTHETIC^NO_REAL_PERSON' not in image.header.binaryblock
        assert not result['source_frame_of_reference_uid'] is None
    assert {path:Path(path).read_bytes() for path in before}==before
    with pytest.raises(PlanError,match='全新目录'):
        convert_and_verify(proposal,bundle,files,tmp_path/'converted')
    assert (tmp_path/'converted/conversion-report.json').exists()


@pytest.mark.parametrize('change,reason',[
    ('sha','original_file_sha_mismatch'),('geometry','original_metadata_revision_mismatch'),
    ('pixel_length','original_pixel_length_mismatch'),('burned','pixel_review_unresolved'),
    ('file_meta','file_meta_uid_mismatch'),('missing','original_file_set_mismatch'),
    ('extra','original_file_set_mismatch'),('same_path','original_path_reused')])
def test_original_byte_or_identity_conflicts_never_produce_complete_conversion(tmp_path,change,reason):
    proposal,bundle,files,_=files_fixture(tmp_path)
    uid=next(iter(files));record=files[uid];path=Path(record['path'])
    if change=='sha':record['sha256']='0'*64
    elif change=='missing':files.pop(uid)
    elif change=='extra':files['2.25.999']=copy.deepcopy(record)
    elif change=='same_path':files[list(files)[1]]=copy.deepcopy(record)
    else:
        ds=pydicom.dcmread(path)
        if change=='geometry':ds.ImagePositionPatient=[11,20,30]
        elif change=='pixel_length':ds.PixelData=ds.PixelData[:-2]
        elif change=='burned':del ds.BurnedInAnnotation
        else:ds.file_meta.MediaStorageSOPInstanceUID='2.25.999'
        if change=='file_meta':
            # dcmwrite repairs file-meta on enforce_file_format=True; keep a
            # deliberately wrong FileMeta with the ordinary writer mode.
            ds.save_as(path,enforce_file_format=False)
        else:ds.save_as(path,enforce_file_format=True)
        record['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(PlanError) as caught:convert_and_verify(proposal,bundle,files,tmp_path/'rejected')
    assert caught.value.reason==reason
    assert not (tmp_path/'rejected/conversion-report.json').exists()
    if (tmp_path/'rejected').exists():
        failure=json.loads((tmp_path/'rejected/conversion-failure.json').read_text(encoding='utf-8'))
        assert not failure['conversion_complete'] and not failure['model_input_eligible']


def test_compressed_transfer_syntax_refused_before_full_parser(tmp_path,monkeypatch):
    proposal,bundle,files,_=files_fixture(tmp_path)
    plan=validate_plan(proposal,bundle)
    source=plan['sources']['t1c'];row=source['instances'][0]
    raw=bytearray(Path(files[row['instance_uid']]['path']).read_bytes())
    # Replace equal-length explicit LE UID by JPEG lossless UID through header
    # reader injection; proves full dcmread cannot be reached on that metadata.
    import app.services.dicom_conversion as service
    monkeypatch.setattr(service.pydicom.filereader,'_read_file_meta_info',lambda _stream:SimpleNamespace(get=lambda *_args:'1.2.840.10008.1.2.1.99'))
    monkeypatch.setattr(service.pydicom,'dcmread',lambda *_args,**_kwargs:pytest.fail('Must reject before inflate/parser'))
    with pytest.raises(PlanError) as caught:source_dataset(bytes(raw),source,row)
    assert caught.value.reason=='conversion_transfer_syntax_unsupported'


def test_independent_conversion_cli_records_all_outputs_no_repeat_overwrite(tmp_path):
    proposal,bundle,files,_=files_fixture(tmp_path)
    paths=[]
    for name,value in [('proposal',proposal),('snapshots',bundle),('source-files',files)]:
        path=tmp_path/(name+'.json');path.write_text(json.dumps(value),encoding='utf-8');paths.append(path)
    tool=Path(__file__).resolve().parents[1]/'tools/convert_dicom_model_input.py'
    args=[sys.executable,str(tool),'--proposal',str(paths[0]),'--snapshots',str(paths[1]),'--source-files',str(paths[2]),'--output-dir',str(tmp_path/'cli-version')]
    done=subprocess.run(args,capture_output=True,text=True)
    assert done.returncode==0,done.stdout+done.stderr
    assert json.loads(done.stdout)['all_voxels_compared']==72
    import os
    index = Path(os.environ['DICOM_CONVERSION_INDEX_FILE'])
    assert index.parent.name.startswith('conversion_suite_')
    job_file = index.parent/'dicom-conversion-jobs'/json.loads(done.stdout)['job']['job_id']/'job.json'
    assert job_file.is_file(), 'CLI children must inherit the owned test job root'

    original=(tmp_path/'cli-version/conversion-report.json').read_bytes()
    retry=subprocess.run(args,capture_output=True,text=True)
    assert retry.returncode==3 and 'fresh_conversion_directory_required' in retry.stdout
    assert (tmp_path/'cli-version/conversion-report.json').read_bytes()==original


@pytest.mark.parametrize('mode,reason',[
    ('bytes','conversion_input_budget_exceeded'),('disk','conversion_disk_budget_exceeded')])
def test_resource_refusal_precedes_any_output_directory(tmp_path,monkeypatch,mode,reason):
    proposal,bundle,files,_=files_fixture(tmp_path)
    import app.services.dicom_conversion as service
    before={record['path']:hashlib.sha256(Path(record['path']).read_bytes()).hexdigest() for record in files.values()}
    if mode=='bytes':monkeypatch.setattr(service,'MAX_INPUT_BYTES',1)
    else:monkeypatch.setattr(service.shutil,'disk_usage',lambda _path:SimpleNamespace(free=0))
    with pytest.raises(PlanError) as caught:convert_and_verify(proposal,bundle,files,tmp_path/'rejected')
    assert caught.value.reason==reason and not (tmp_path/'rejected').exists()
    assert {path:hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in before}==before


@pytest.mark.parametrize('change,reason',[
    ('affine','converted_affine_mismatch'),('voxel','converted_pixels_mismatch'),
    ('units','converted_units_mismatch'),('forms','converted_form_mismatch'),
    ('empty','empty_sequence_for_model')])
def test_independent_reloaded_output_checks_and_empty_input(tmp_path,monkeypatch,change,reason):
    proposal,bundle,files,_=files_fixture(tmp_path)
    import app.services.dicom_conversion as service
    if change=='empty':
        for row in files.values():
            ds=pydicom.dcmread(row['path']);ds.PixelData=b'\0'*12;ds.save_as(row['path'],enforce_file_format=True)
            row['sha256']=hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()
    else:
        original=service.sitk.WriteImage
        def corrupted(image,path,*args):
            original(image,path,*args)
            value=nib.load(path);data=value.get_fdata(dtype=np.float32);affine=value.affine.copy()
            if change=='affine':affine[0,3]+=1
            elif change=='voxel':data[1,1,1]+=1
            altered=nib.Nifti1Image(data,affine,header=value.header.copy())
            if change=='units':altered.header.set_xyzt_units('unknown')
            elif change=='forms':
                wrong=affine.copy();wrong[0,3]+=.1;altered.set_qform(wrong,code=1)
            nib.save(altered,path)
        monkeypatch.setattr(service.sitk,'WriteImage',corrupted)
    with pytest.raises(PlanError) as caught:convert_and_verify(proposal,bundle,files,tmp_path/'rejected')
    assert caught.value.reason==reason
    assert not (tmp_path/'rejected/conversion-report.json').exists()
    assert (tmp_path/'rejected/conversion-failure.json').exists()
