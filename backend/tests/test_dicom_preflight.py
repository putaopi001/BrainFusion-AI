"""Explicit synthetic Part10 files and recursive privacy/error behaviors."""
import hashlib,json,struct,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
import pytest
from pydicom.dataset import Dataset,FileDataset,FileMetaDataset
from pydicom.sequence import Sequence
from pydicom.uid import ExplicitVRLittleEndian
from app.services import dicom_preflight as service

SECRET='PRIVATE_PERSON_NEVER_LOG_THIS'

def save(path,ds):
    ds.save_as(path,enforce_file_format=True)
    return hashlib.sha256(path.read_bytes()).hexdigest()

@pytest.fixture
def candidate(tmp_path):
    path=tmp_path/'SYNTHETIC.dcm'
    meta=FileMetaDataset()
    meta.MediaStorageSOPClassUID='1.2.840.10008.5.1.4.1.1.4'
    meta.MediaStorageSOPInstanceUID='2.25.10003'
    meta.TransferSyntaxUID=ExplicitVRLittleEndian
    ds=FileDataset(str(path),{},file_meta=meta,preamble=b'\0'*128)
    ds.SOPClassUID=meta.MediaStorageSOPClassUID;ds.SOPInstanceUID=meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID='2.25.10001';ds.SeriesInstanceUID='2.25.10002';ds.FrameOfReferenceUID='2.25.10004'
    ds.PatientID='SYNTHETIC-AUDIT';ds.PatientName='SYNTHETIC-AUDIT'
    ds.PatientIdentityRemoved='YES';ds.DeidentificationMethod='Synthetic fixture only'
    ds.BurnedInAnnotation='NO';ds.Modality='MR';ds.ImageType=['ORIGINAL','PRIMARY']
    ds.ImagePositionPatient=[10,20,-30];ds.ImageOrientationPatient=[0,-1,0,1,0,0];ds.PixelSpacing=[3.25,2]
    ds.Rows=2;ds.Columns=3;ds.SamplesPerPixel=1;ds.PhotometricInterpretation='MONOCHROME2'
    ds.BitsAllocated=16;ds.BitsStored=16;ds.HighBit=15;ds.PixelRepresentation=1
    ds.PixelData=struct.pack('<6h',-1000,0,1024,30000,-2,2573)
    digest=save(path,ds)
    source={'data_role':'synthetic-fixture','sha256':digest,'patient_source_id':'SYNTHETIC-AUDIT',
            'study_uid':str(ds.StudyInstanceUID),'series_uid':str(ds.SeriesInstanceUID),'sop_uid':str(ds.SOPInstanceUID),
            'source_url':'https://services.cancerimagingarchive.net/nbia-api/services/v1/getSingleImage?SeriesInstanceUID=2.25.10002&SOPInstanceUID=2.25.10003',
            'dataset_url':'https://www.cancerimagingarchive.net/collection/SYNTHETIC-FIXTURE-NOT-REAL/',
            'license_url':'https://creativecommons.org/licenses/by/4.0/'}
    review={'source_sha256':digest,'reviewer_id':'SYNTHETIC-REVIEWER','reviewed_utc':datetime.now(timezone.utc).isoformat(),
            'decision':'no_identifying_text_observed','evidence_sha256':'1'*64}
    return path,ds,source,review

def audit(candidate):
    path,ds,source,review=candidate
    digest=save(path,ds);source['sha256']=digest;review['source_sha256']=digest
    return service.audit_dicom(path,source,review)

def reasons(report):return {item['reason'] for item in report['findings']}

def test_synthetic_success_original_preserved_without_clinical_claim(candidate):
    path,_,source,review=candidate
    result=service.audit_dicom(path,source,review)
    assert result['decision']=='engineering_fixture_pass',result
    assert not result['archive_eligible'] and not result['archive_imported'] and not result['deidentification_complete']
    assert hashlib.sha256(path.read_bytes()).hexdigest()==source['sha256']
    assert result['pixel_data_sha256']==hashlib.sha256(struct.pack('<6h',-1000,0,1024,30000,-2,2573)).hexdigest()

def test_recursive_nested_name_private_and_reference_not_only_root(candidate):
    path,ds,source,review=candidate
    level1=Dataset();level2=Dataset();level2.PatientName=SECRET
    level2.add_new((0x0011,0x1010),'LO',SECRET);level2.ReferencedSOPInstanceUID='2.25.99999'
    level1.ContentSequence=Sequence([level2]);ds.ContentSequence=Sequence([level1])
    result=audit(candidate)
    assert result['decision']=='rejected' and {'person_name','private_attribute','uid_reference_requires_review'}<=reasons(result)
    assert any('0040A730[0]/0040A730[0]/00100010' in f['tag_path'] for f in result['findings'])
    assert SECRET not in json.dumps(result)

def test_nested_other_patient_id_and_encrypted_sequence_are_blocked(candidate):
    _,ds,_,_=candidate
    nested=Dataset();nested.PatientID=SECRET
    ds.OtherPatientIDsSequence=Sequence([nested])
    encrypted=Dataset();encrypted.add_new((0x0400,0x0520),'OB',SECRET.encode())
    ds.EncryptedAttributesSequence=Sequence([encrypted])
    result=audit(candidate)
    assert {'nested_patient_identifier','identifier_or_embedded_identity'}<=reasons(result)
    assert SECRET not in json.dumps(result) and result['decision']=='rejected'

def test_declared_public_source_cannot_self_authorize_archive_import(candidate):
    path,_,source,review=candidate
    source['data_role']='public-dicom-candidate'
    result=service.audit_dicom(path,source,review)
    assert result['decision']=='preflight_checks_passed',result
    assert result['archive_eligible'] is False and result['provenance_independently_verified'] is False

def test_after_pixel_attributes_are_not_skipped(candidate):
    path,ds,source,review=candidate
    ds.add_new((0xFFFC,0xFFFC),'OB',SECRET.encode())
    result=audit(candidate)
    assert 'nonzero_trailing_padding' in reasons(result) and not result['archive_eligible']
    assert SECRET not in json.dumps(result)

def test_nonstandard_file_meta_binary_not_silently_exempted(candidate):
    path,ds,_,_=candidate
    ds.file_meta.FileMetaInformationVersion=b'\0\1'+SECRET.encode()
    result=audit(candidate)
    assert 'opaque_attribute_requires_review' in reasons(result) and not result['archive_eligible']
    assert SECRET not in json.dumps(result)

@pytest.mark.parametrize('mode,reason',[
    ('source_hash','source_manifest_missing_or_mismatch'),('uid','source_uid_mismatch'),
    ('patient','source_patient_pseudonym_mismatch'),('review_hash','pixel_review_hash_mismatch'),
    ('review_missing','pixel_review_missing'),('review_identifies','pixel_identification_observed'),
    ('source_missing','source_manifest_missing_or_mismatch'),('http','input_or_manifest_invalid'),
])
def test_bound_manifest_and_review_failure(candidate,mode,reason):
    path,ds,source,review=candidate
    if mode=='source_hash':source['sha256']='0'*64
    if mode=='uid':source['sop_uid']='2.25.999'
    if mode=='patient':source['patient_source_id']='SYNTHETIC-OTHER'
    if mode=='review_hash':review['source_sha256']='0'*64
    if mode=='review_missing':review=None
    if mode=='review_identifies':review['decision']='identifying_text_observed'
    if mode=='source_missing':source=None
    if mode=='http':source['source_url']=source['source_url'].replace('https:','http:')
    result=service.audit_dicom(path,source,review)
    assert reason in reasons(result) and not result['archive_eligible']

@pytest.mark.parametrize('mode,reason',[
    ('private','private_attribute'),('name','person_name'),('birth','identifier_or_embedded_identity'),
    ('date','date_time_requires_review'),('description','text_requires_review'),('text','free_text_requires_review'),
    ('identity','identity_removal_unconfirmed'),('burned','burned_in_annotation_present'),
    ('unknown_burned','burned_in_annotation_unknown'),('mosaic','unsupported_mosaic'),
    ('meta','file_meta_sop_mismatch'),('preamble','nonzero_preamble_requires_review'),
    ('length','file_pixel_length_mismatch'),('deflated','unsupported_file_transfer_syntax'),
])
def test_known_privacy_and_layout_cases(candidate,mode,reason):
    path,ds,source,review=candidate
    if mode=='private':ds.add_new((0x0011,0x1010),'LO',SECRET)
    if mode=='name':ds.PatientName=SECRET
    if mode=='birth':ds.PatientBirthDate='19800101'
    if mode=='date':ds.StudyDate='20200101'
    if mode=='description':ds.SeriesDescription=SECRET
    if mode=='text':ds.add_new((0x0040,0xA160),'UT',SECRET)
    if mode=='identity':del ds.PatientIdentityRemoved
    if mode=='burned':ds.BurnedInAnnotation='YES'
    if mode=='unknown_burned':del ds.BurnedInAnnotation
    if mode=='mosaic':ds.ImageType=['ORIGINAL','PRIMARY','MOSAIC']
    if mode=='meta':
        # dcmwrite normally aligns SOP UID. Persist then alter source binary same-length.
        raw=path.read_bytes().replace(b'2.25.10003',b'2.25.10009',1)
        path.write_bytes(raw);source['sha256']=hashlib.sha256(raw).hexdigest();review['source_sha256']=source['sha256']
        result=service.audit_dicom(path,source,review)
    else:
        if mode=='preamble':ds.preamble=SECRET.encode().ljust(128,b'\0')
        if mode=='length':ds.PixelData=b'\0\0'
        if mode=='deflated':ds.file_meta.TransferSyntaxUID='1.2.840.10008.1.2.1.99'
        result=audit(candidate)
    assert reason in reasons(result),result
    assert not result['archive_eligible'] and SECRET not in json.dumps(result)

@pytest.mark.parametrize('limit', ['depth','elements','findings','size'])
def test_bounded_scan_limits_no_raw_values(candidate,monkeypatch,limit):
    path,ds,_,_=candidate
    if limit=='size':monkeypatch.setattr(service,'MAX_FILE_BYTES',1)
    elif limit=='elements':monkeypatch.setattr(service,'MAX_ELEMENTS',2)
    elif limit=='findings':
        monkeypatch.setattr(service,'MAX_FINDINGS',2)
        for offset in range(4):ds.add_new((0x0011,0x1010+offset),'LO',SECRET)
    else:
        monkeypatch.setattr(service,'MAX_DEPTH',1)
        a=Dataset();b=Dataset();b.PatientName=SECRET;a.ContentSequence=Sequence([b]);ds.ContentSequence=Sequence([a])
    result=audit(candidate)
    assert not result['archive_eligible'] and ('scan_limit_exceeded' in reasons(result) or 'file_too_large' in reasons(result))
    assert SECRET not in json.dumps(result)

def test_non_dicom_and_invalid_review_do_not_expose_values(candidate,tmp_path):
    path,_,source,review=candidate
    bad=tmp_path/'invalid.dcm';bad.write_bytes(SECRET.encode())
    result=service.audit_dicom(bad)
    assert 'part10_header_missing' in reasons(result) and SECRET not in json.dumps(result)
    review['reviewer_id']=SECRET+' '+SECRET
    assert 'input_or_manifest_invalid' in reasons(service.audit_dicom(path,source,review))

def test_real_cli_fresh_output_redaction_exit_and_no_overwrite(candidate,tmp_path):
    path,ds,source,review=candidate
    ds.PatientName=SECRET;digest=save(path,ds);source['sha256']=digest
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps(source),encoding='utf-8')
    output=tmp_path/'report.json'
    command=[sys.executable,str(Path(__file__).resolve().parents[1]/'tools/audit_dicom_preflight.py'),
             '--input',str(path),'--source-manifest',str(manifest),'--output',str(output)]
    result=subprocess.run(command,capture_output=True,text=True)
    assert result.returncode==3 and output.exists()
    assert SECRET not in result.stdout+result.stderr+output.read_text(encoding='utf-8')
    previous=output.read_bytes()
    retry=subprocess.run(command,capture_output=True,text=True)
    assert retry.returncode!=0 and output.read_bytes()==previous
