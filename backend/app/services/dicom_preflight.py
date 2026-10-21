"""Read-only bounded import preflight, not a complete PS3.15 deidentifier."""
import hashlib
import io
import logging
import threading
import warnings
from pathlib import Path
from types import SimpleNamespace
from typing import Literal
from urllib.parse import urlsplit, parse_qs

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.services.pacs_client import validate_uid
from app.core.storage import is_supported_storage_path
from app.services.pacs_wado import checked_metadata

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_ELEMENTS = 10000
MAX_DEPTH = 24
MAX_FINDINGS = 1000
PARSER_LOCK = threading.Lock()
POLICY_VERSION = 'local-mr-import-preflight-v1'
BLOCKED_TAGS = {
    0x00100030,0x00100032,0x00101000,0x00101001,0x00101002,0x00101040,0x00102154,0x00104000,
    0x00080050,0x00080080,0x00080081,0x00081040,0x00081048,0x00081050,
    0x00020016,0x00020017,0x00020018,0x00020100,0x00020102,0x04000500,
}
ALLOW_TEXT_TAGS = {0x00100020,0x00120063,0x00080100,0x00080102,0x00080104}
UID_TAGS = {0x00080016,0x00080018,0x0020000D,0x0020000E,0x00200052,
            0x00020002,0x00020003,0x00020010,0x00020012,0x00081150}


class SourceManifest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    data_role: Literal['public-dicom-candidate','synthetic-fixture']
    sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    source_url: str
    dataset_url: str
    license_url: str
    patient_source_id: str = Field(pattern=r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$')
    study_uid: str
    series_uid: str
    sop_uid: str

    @field_validator('study_uid','series_uid','sop_uid')
    @classmethod
    def uid(cls,value):
        validate_uid(value)
        return value

    @field_validator('source_url','dataset_url','license_url')
    @classmethod
    def https_url(cls,value):
        url=urlsplit(value)
        if url.scheme!='https' or not url.hostname or url.username or url.password or url.fragment:
            raise ValueError('Invalid source URL')
        return value

    def public_endpoint_matches(self):
        url=urlsplit(self.source_url)
        query=parse_qs(url.query)
        return (url.hostname=='services.cancerimagingarchive.net' and url.port in (None,443)
                and url.path=='/nbia-api/services/v1/getSingleImage'
                and query.get('SeriesInstanceUID')==[self.series_uid]
                and query.get('SOPInstanceUID')==[self.sop_uid]
                and urlsplit(self.dataset_url).hostname=='www.cancerimagingarchive.net'
                and self.license_url=='https://creativecommons.org/licenses/by/4.0/')


class PixelReview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    reviewer_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    reviewed_utc: str
    decision: Literal['no_identifying_text_observed','identifying_text_observed']
    evidence_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')

    @field_validator('reviewed_utc')
    @classmethod
    def utc_time(cls,value):
        from datetime import datetime
        dt=datetime.fromisoformat(value.replace('Z','+00:00'))
        if dt.tzinfo is None or dt.utcoffset().total_seconds()!=0:
            raise ValueError('UTC review time required')
        return value


class ScanLimit(Exception):
    pass


def audit_dicom(path, source=None, pixel_review=None):
    report={'policy_version':POLICY_VERSION,'decision':'rejected','archive_eligible':False,
            'deidentification_complete':False,'archive_imported':False,
            'source_uid_binding_verified':False,'findings':[]}
    def finding(reason,path='Dataset',severity='blocking'):
        if len(report['findings'])>=MAX_FINDINGS:
            raise ScanLimit()
        report['findings'].append({'reason':reason,'tag_path':path,'severity':severity})
    try:
        file=Path(path).resolve(strict=True)
        if not is_supported_storage_path(file) or not file.is_file():
            finding('input_path_not_supported');return report
        size=file.stat().st_size
        if size>MAX_FILE_BYTES:
            finding('file_too_large');return report
        # One bounded snapshot binds all parsing/reviews; nothing is modified.
        with file.open('rb') as handle: raw=handle.read(MAX_FILE_BYTES+1)
        if len(raw)>MAX_FILE_BYTES:
            finding('file_changed_or_too_large');return report
        digest=hashlib.sha256(raw).hexdigest()
        report.update(source_sha256=digest,source_bytes=len(raw))
        manifest=SourceManifest.model_validate(source) if source is not None else None
        review=PixelReview.model_validate(pixel_review) if pixel_review is not None else None
    except Exception:
        finding('input_or_manifest_invalid');return report
    report['data_role']=manifest.data_role if manifest else 'unverified'
    source_ok=bool(manifest and manifest.sha256==digest and manifest.public_endpoint_matches())
    report['source_assertions_match_hash_and_endpoint']=source_ok
    report['provenance_independently_verified']=False
    report['pixel_review_attestation_present']=review is not None
    if not source_ok: finding('source_manifest_missing_or_mismatch')
    if review is None: finding('pixel_review_missing',severity='review')
    elif review.source_sha256!=digest: finding('pixel_review_hash_mismatch')
    elif review.decision!='no_identifying_text_observed': finding('pixel_identification_observed')
    if len(raw)<132 or raw[128:132]!=b'DICM':
        finding('part10_header_missing');return report
    if any(raw[:128]): finding('nonzero_preamble_requires_review',severity='review')
    try:
        import pydicom
        from pydicom.filereader import read_file_meta_info
    except ImportError:
        finding('dicom_parser_unavailable');return report
    report['parser_version']=pydicom.__version__
    # Parser warnings can contain original values; keep only a count, never text.
    with PARSER_LOCK, warnings.catch_warnings(record=True) as captured:
        logger=logging.getLogger('pydicom'); old_disabled=logger.disabled; logger.disabled=True
        try:
            meta=read_file_meta_info(file)
            syntax=str(meta.get('TransferSyntaxUID',''))
            report['transfer_syntax_uid']=syntax
            if syntax not in ('1.2.840.10008.1.2','1.2.840.10008.1.2.1'):
                finding('unsupported_file_transfer_syntax');return report
            ds=pydicom.dcmread(io.BytesIO(raw),force=False,stop_before_pixels=False)
            if manifest:
                for keyword,expected in [('StudyInstanceUID',manifest.study_uid),('SeriesInstanceUID',manifest.series_uid),('SOPInstanceUID',manifest.sop_uid)]:
                    if str(ds.get(keyword,''))!=expected: finding('source_uid_mismatch',keyword)
                if str(ds.get('PatientID','')).strip()!=manifest.patient_source_id:
                    finding('source_patient_pseudonym_mismatch','Dataset/00100020')
            if (str(ds.file_meta.get('MediaStorageSOPInstanceUID',''))!=str(ds.get('SOPInstanceUID',''))
                    or str(ds.file_meta.get('MediaStorageSOPClassUID',''))!=str(ds.get('SOPClassUID',''))):
                finding('file_meta_sop_mismatch','FileMeta')
            report['source_uid_binding_verified']=bool(manifest and not any(
                item['reason'] in ('source_uid_mismatch','file_meta_sop_mismatch')
                for item in report['findings']))
            count=0
            def walk(dataset,prefix,depth):
                nonlocal count
                if depth>MAX_DEPTH: raise ScanLimit()
                for element in dataset:
                    count+=1
                    if count>MAX_ELEMENTS: raise ScanLimit()
                    tag=int(element.tag); location=prefix+'/'+format(tag,'08X')
                    if tag in (0x7FE00010,0x7FE00008,0x7FE00009): continue
                    val=element.value
                    if tag==0x00020001 and prefix=='FileMeta' and val==b'\0\1':
                        continue  # Standard two-byte File Meta Information Version.
                    if element.tag.is_private: finding('private_attribute',location)
                    if element.VR=='SQ':
                        if tag in BLOCKED_TAGS and len(val): finding('identifier_or_embedded_identity',location)
                        for index,item in enumerate(val): walk(item,location+'['+str(index)+']',depth+1)
                        continue
                    nonempty=val is not None and str(val).strip(' \0')!=''
                    if not nonempty: continue
                    pseudo=(manifest and prefix=='Dataset' and tag==0x00100010 and str(val).strip()==manifest.patient_source_id)
                    if element.VR=='PN' and not pseudo: finding('person_name',location)
                    elif tag==0x00100020 and prefix!='Dataset': finding('nested_patient_identifier',location)
                    elif tag in BLOCKED_TAGS: finding('identifier_or_embedded_identity',location)
                    elif element.VR in ('OB','OW','UN','OF','OD','OL','OV') and tag not in (0xFFFCFFFC,):
                        finding('opaque_attribute_requires_review',location,'review')
                    elif tag==0xFFFCFFFC and isinstance(val,bytes) and any(val):
                        finding('nonzero_trailing_padding','Dataset/FFFCFFFC')
                    elif element.VR in ('DA','DT','TM'): finding('date_time_requires_review',location,'review')
                    elif element.VR in ('LT','ST','UT'): finding('free_text_requires_review',location,'review')
                    elif element.VR in ('LO','SH') and tag not in ALLOW_TEXT_TAGS and prefix!='FileMeta':
                        finding('text_requires_review',location,'review')
                    elif element.VR=='UI' and tag not in UID_TAGS: finding('uid_reference_requires_review',location,'review')
            walk(ds.file_meta,'FileMeta',0);walk(ds,'Dataset',0)
            report['scanned_elements']=count
            if str(ds.get('PatientIdentityRemoved','')).strip()!='YES':
                finding('identity_removal_unconfirmed','Dataset/00120062','review')
            burned=str(ds.get('BurnedInAnnotation','')).strip()
            if burned=='YES': finding('burned_in_annotation_present','Dataset/00280301')
            elif burned!='NO': finding('burned_in_annotation_unknown','Dataset/00280301','review')
            if 'DeidentificationMethod' not in ds and 'DeidentificationMethodCodeSequence' not in ds:
                finding('deidentification_method_missing','Dataset/00120063','review')
            selected=pydicom.Dataset()
            for tag in ['00080008','00080016','00080018','00080060','0020000D','0020000E','00200052','00200032','00200037',
                        '00280008','00280030','00280010','00280011','00280002','00280004','00280100','00280101','00280102','00280103',
                        '00180050','00180088','00281052','00281053','00281050','00281051']:
                if tag in ds: selected.add(ds[tag])
            try:
                archive=SimpleNamespace(config=SimpleNamespace(allow_pixel_read=False),_json=lambda _: [selected.to_json_dict()])
                _,expected=checked_metadata(archive,str(ds.get('StudyInstanceUID','')),str(ds.get('SeriesInstanceUID','')),str(ds.get('SOPInstanceUID','')))
                pixels=ds.get('PixelData',None)
                if not isinstance(pixels,bytes) or (len(pixels)!=expected and not (expected%2 and len(pixels)==expected+1 and pixels[-1]==0)):
                    finding('file_pixel_length_mismatch','Dataset/7FE00010')
                else: report['pixel_data_sha256']=hashlib.sha256(pixels).hexdigest()
            except HTTPException as exc:
                finding(exc.detail['reason'],'Dataset/Geometry')
            except Exception:
                finding('invalid_geometry_or_pixel_metadata','Dataset/Geometry')
        except ScanLimit:
            # Keep a bounded report and explicitly disclose an incomplete scan.
            report['findings']=report['findings'][:MAX_FINDINGS-1]
            finding('scan_limit_exceeded')
        except Exception:
            finding('dicom_parse_or_scan_failed')
        finally:
            logger.disabled=old_disabled
            report['parser_warning_count']=len(captured)
    # A changed source is never accepted, including same-size mutations.
    with file.open('rb') as handle:
        now=hashlib.sha256()
        for block in iter(lambda:handle.read(65536),b''):now.update(block)
    if now.hexdigest()!=digest: finding('source_changed_during_preflight')
    blocking=any(f['severity']=='blocking' for f in report['findings'])
    if report['findings']: report['decision']='rejected' if blocking else 'needs_review'
    elif manifest and manifest.data_role=='synthetic-fixture': report['decision']='engineering_fixture_pass'
    else:
        # Matching a caller-supplied manifest/review does not establish authority.
        # A future importer must validate provenance/reviewer identity independently.
        report['decision']='preflight_checks_passed'
    return report
