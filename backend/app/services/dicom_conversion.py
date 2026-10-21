"""Bounded original-byte DICOM -> NIfTI derivative verification; no activation."""
import hashlib
import io
import json
import os
import re
import shutil
import logging
import warnings
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace

import nibabel as nib
import numpy as np
import pydicom
import SimpleITK as sitk
from fastapi import HTTPException

from app.services.dicom_input_plan import PlanError, ROLES, validate_plan, metadata_semantic_digest
from app.core.storage import is_supported_storage_path
from app.services.dicom_preflight import PARSER_LOCK
from app.services.pacs_wado import checked_metadata_item
from app.services.dicom_resampling import resample_array, resample_image
from app.services.study_validation import validate_sequences

MAX_FILE_BYTES = 64*1024*1024
MAX_INPUT_BYTES = 1024*1024*1024
SUPPORTED_TS = {'1.2.840.10008.1.2.1', '1.2.840.10008.1.2'}


def fail(reason, message):
    raise PlanError(reason, message)


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def source_dataset(raw, source, instance):
    # Serialize parser warning suppression with the existing preflight parser.
    with PARSER_LOCK, warnings.catch_warnings(record=True):
        logger=logging.getLogger('pydicom');previous=logger.disabled;logger.disabled=True
        try:
            return _source_dataset(raw,source,instance)
        finally:
            logger.disabled=previous


def _source_dataset(raw, source, instance):
    if raw[128:132] != b'DICM':
        fail('unsupported_dicom_file', '转换要求完整Part10原文件。')
    try:
        # Pinned pydicom3.0.2 header reader checks TS before any deflate decode.
        stream=io.BytesIO(raw);stream.seek(132)
        meta=pydicom.filereader._read_file_meta_info(stream)
        if str(meta.get('TransferSyntaxUID','')) not in SUPPORTED_TS:
            fail('conversion_transfer_syntax_unsupported', '初版转换仅支持未压缩Little Endian原文件，不自动转码。')
        ds = pydicom.dcmread(io.BytesIO(raw), force=False)
        # Only numeric geometry/presentation and mandatory identity fields.
        tags = ['00080008','00080016','00080018','00080060','0020000D','0020000E','00200052',
                '00200032','00200037','00280030','00280010','00280011','00280002','00280004',
                '00280100','00280101','00280102','00280103','00280008','00180050','00180088',
                '00281052','00281053','00281050','00281051']
        metadata = {tag: ds[int(tag,16)].to_json_dict(None,1024) for tag in tags if int(tag,16) in ds}
        item, expected = checked_metadata_item(SimpleNamespace(allow_pixel_read=False),metadata,
                                                source['study_uid'],source['series_uid'],instance['instance_uid'])
        if (str(ds.file_meta.MediaStorageSOPInstanceUID) != instance['instance_uid']
                or str(ds.file_meta.MediaStorageSOPClassUID) != str(ds.SOPClassUID)):
            fail('file_meta_uid_mismatch', 'FileMeta与数据集实例身份不一致。')
        if metadata_semantic_digest(item) != instance['metadata_semantic_sha256']:
            fail('original_metadata_revision_mismatch', '原DICOM文件与规划中的元数据版本不一致。')
        stored_length = expected + expected % 2  # Standard even-length OB padding.
        if ('PixelData' not in ds or len(ds.PixelData) != stored_length
                or (expected % 2 and ds.PixelData[-1] != 0)):
            fail('original_pixel_length_mismatch', '原DICOM像素字节长度与单帧布局不一致。')
        if ds.get('BurnedInAnnotation') not in ('NO',):
            fail('pixel_review_unresolved', '原文件未明确声明无像素烧录；实际像素审核仍需独立完成。')
        return ds
    except HTTPException as e:
        fail(e.detail['reason'], e.detail['message'])
    except PlanError:
        raise
    except Exception:
        fail('unreadable_dicom_file', '原DICOM结构不可读取；未输出标签或异常原文。')


def convert_and_verify(proposal, snapshots, source_files, output_dir):
    """Own fresh output directory and snapshot all inputs before the reader runs."""
    plan = validate_plan(proposal, snapshots)
    directory = Path(output_dir).resolve()
    if not is_supported_storage_path(directory) or directory.exists() or not directory.parent.is_dir():
        fail('fresh_conversion_directory_required', '转换只能使用现有E盘父目录中的全新目录，不覆盖既有产物。')
    instances = {row['instance_uid']: (source,row) for source in plan['sources'].values() for row in source['instances']}
    if not isinstance(source_files,dict) or set(source_files) != set(instances):
        fail('original_file_set_mismatch', '必须提供规划中每个SOP的原文件和SHA；不接受缺项或多项。')
    paths, total = {}, 0
    for uid, record in source_files.items():
        if (not isinstance(record,dict) or set(record) != {'path','sha256'}
                or not isinstance(record['path'],str) or not isinstance(record['sha256'],str)
                or not re.fullmatch(r'[0-9a-f]{64}',record['sha256'])):
            fail('invalid_original_file_record', '原文件记录格式无效。')
        try:
            path=Path(record['path']).resolve(strict=True)
            size=path.stat().st_size
            if not is_supported_storage_path(path) or not path.is_file() or not 132 < size <= MAX_FILE_BYTES:
                raise ValueError()
        except (OSError,ValueError):
            fail('invalid_original_file', '原文件必须存在于E盘且每个不超过64MiB。')
        if path in paths.values():
            fail('original_path_reused', '同一个文件不能代替多个SOP。')
        paths[uid]=path;total+=size
    if total > MAX_INPUT_BYTES:
        fail('conversion_input_budget_exceeded', '原文件总量超过1GiB轻量转换预算。')
    # Reserve raw input copies + worst-case float32 derivatives + 512MiB.
    required=total+sum(np.prod(s['geometry']['dimensions'],dtype=np.int64)*4 for s in plan['sources'].values())+512*1024*1024
    if shutil.disk_usage(directory.parent).free < required:
        fail('conversion_disk_budget_exceeded', 'E盘空间不足以保留原字节快照和转换版本。')
    directory.mkdir(exist_ok=False)
    stage=directory/'original-byte-snapshots';stage.mkdir()
    started=perf_counter();derived={};stored={};copied_bytes=0
    try:
        for uid,path in paths.items():
            with path.open('rb') as handle:raw=handle.read(MAX_FILE_BYTES+1)
            copied_bytes+=len(raw)
            if copied_bytes>MAX_INPUT_BYTES:
                fail('conversion_input_budget_exceeded', '复制窗口内原文件总量超过1GiB，停止转换。')
            if not 132 < len(raw) <= MAX_FILE_BYTES or hashlib.sha256(raw).hexdigest()!=source_files[uid]['sha256']:
                fail('original_file_sha_mismatch', '原DICOM校验和与文件记录不一致，拒绝转换。')
            source,instance=instances[uid]
            source_dataset(raw,source,instance)
            target=stage/(source_files[uid]['sha256']+'.dcm')
            with target.open('xb') as handle:
                handle.write(raw);handle.flush();os.fsync(handle.fileno())
            stored[uid]=target
        conversion_ms={}
        resampling=plan.get('resampling')
        target_grid=plan.get('target_grid')
        for role in ROLES:
            source=plan['sources'][role]
            ordered=[stored[row['instance_uid']] for row in source['instances']]
            begin=perf_counter()
            reader=sitk.ImageSeriesReader()
            reader.SetImageIO('GDCMImageIO')
            reader.SetFileNames([str(path) for path in ordered])
            reader.SetOutputPixelType(sitk.sitkFloat32)
            reader.SetForceOrthogonalDirection(False)
            reader.LoadPrivateTagsOff()
            reader.MetaDataDictionaryArrayUpdateOff()
            image=reader.Execute()
            if list(image.GetSize())!=source['geometry']['dimensions']:
                fail('converted_matrix_mismatch', '转换器矩阵与原DICOM规划不一致。')
            source_direction=np.asarray(image.GetDirection(),dtype=float).reshape(3,3)
            source_affine_lps=np.eye(4)
            source_affine_lps[:3,:3]=source_direction@np.diag(image.GetSpacing())
            source_affine_lps[:3,3]=image.GetOrigin()
            source_affine_ras=np.diag([-1.,-1.,1.,1.])@source_affine_lps
            if not np.allclose(source_affine_ras,source['expected_source_ijk_to_ras_mm'],atol=1e-4,rtol=0):
                fail('converted_source_geometry_mismatch','GDCM读取所得原始患者空间与DICOM规划不同。')
            output_image=resample_image(image,target_grid,sitk,resampling['outside_value']) if resampling else image
            for key in output_image.GetMetaDataKeys():output_image.EraseMetaData(key)
            output=directory/(role+'.nii.gz')
            sitk.WriteImage(output_image,str(output),True)
            converted=nib.load(output)
            if converted.header.get_xyzt_units()[0]!='mm':
                fail('converted_units_mismatch', '转换后NIfTI未明确采用毫米。')
            output_dimensions=target_grid['dimensions'] if resampling else source['geometry']['dimensions']
            expected_affine=np.asarray(target_grid['affine_ras_mm'] if resampling else source['expected_source_ijk_to_ras_mm'])
            if converted.shape!=tuple(output_dimensions) or not np.allclose(converted.affine,expected_affine,atol=1e-4,rtol=0):
                fail('converted_affine_mismatch', '转换后affine与声明的原始或重采样患者空间不同。')
            qform,qcode=converted.header.get_qform(coded=True)
            sform,scode=converted.header.get_sform(coded=True)
            if not qcode or not scode or not np.allclose(qform,sform,atol=1e-4,rtol=0):
                fail('converted_form_mismatch', '转换后qform/sform缺失或冲突。')
            pixel_count=0;expected_hash=hashlib.sha256();actual_hash=hashlib.sha256();max_error=0.;nonzero_found=False
            if resampling:
                source_slices=[]
                for row in source['instances']:
                    ds=source_dataset(stored[row['instance_uid']].read_bytes(),source,row)
                    voxels=np.asarray(ds.pixel_array,dtype=np.float32)*float(ds.get('RescaleSlope',1))+float(ds.get('RescaleIntercept',0))
                    if voxels.shape!=(source['geometry']['dimensions'][1],source['geometry']['dimensions'][0]):
                        fail('converted_pixels_invalid','原DICOM层矩阵与来源几何不一致。')
                    source_slices.append(voxels)
                expected_volume=resample_array(np.stack(source_slices,axis=0),source['geometry'],target_grid,resampling['outside_value'])
                actual_volume=np.asarray(converted.dataobj,dtype=np.float32).transpose(2,1,0)
                if expected_volume.shape!=actual_volume.shape or not np.isfinite(expected_volume).all() or not np.isfinite(actual_volume).all():
                    fail('converted_pixels_invalid','重采样像素矩阵或有限值不符合输入几何。')
                max_error=float(np.max(np.abs(expected_volume-actual_volume)))
                if not np.allclose(expected_volume,actual_volume,atol=1e-4,rtol=0):
                    fail('converted_pixels_mismatch','NIfTI重采样像素与原DICOM独立解码/插值结果不一致。')
                nonzero_found=bool(np.any(actual_volume!=0))
                expected_hash.update(np.asarray(expected_volume,dtype='<f4').tobytes(order='C'))
                actual_hash.update(np.asarray(actual_volume,dtype='<f4').tobytes(order='C'))
                pixel_count=int(actual_volume.size)
            else:
                for k,row in enumerate(source['instances']):
                    raw=stored[row['instance_uid']].read_bytes()
                    ds=source_dataset(raw,source,row)
                    expected=np.asarray(ds.pixel_array,dtype=np.float32)*float(ds.get('RescaleSlope',1))+float(ds.get('RescaleIntercept',0))
                    actual=np.asarray(converted.dataobj[:,:,k],dtype=np.float32).T
                    if expected.shape!=actual.shape or not np.isfinite(expected).all() or not np.isfinite(actual).all():
                        fail('converted_pixels_invalid', '转换像素矩阵或有限值不符合原文件。')
                    error=float(np.max(np.abs(expected-actual)));max_error=max(max_error,error)
                    nonzero_found = nonzero_found or bool(np.any(actual != 0))
                    if not np.allclose(expected,actual,atol=1e-4,rtol=0):
                        fail('converted_pixels_mismatch', '转换后像素与原存储值/显式Rescale参数不一致。')
                    expected_hash.update(np.asarray(expected,dtype='<f4').tobytes(order='C'))
                    actual_hash.update(np.asarray(actual,dtype='<f4').tobytes(order='C'))
                    pixel_count+=actual.size
            if not nonzero_found:
                fail('empty_sequence_for_model', '转换后序列全部为零，不满足现有模型输入；不生成成功状态。')
            conversion_ms[role]=(perf_counter()-begin)*1000
            derived[role]={'nifti_path':str(output),'sha256':sha_file(output),'shape':list(converted.shape),
                'spacing_xyz_mm':list(map(float,converted.header.get_zooms()[:3])),
                'affine_ras_mm':converted.affine.tolist(),'qform_code':int(qcode),'sform_code':int(scode),
                'all_voxels_compared':int(pixel_count),'maximum_absolute_intensity_error':max_error,
                'expected_scaled_voxel_sha256':expected_hash.hexdigest(),'actual_voxel_sha256':actual_hash.hexdigest(),
                'source_series_uid':source['series_uid'],'source_study_uid':source['study_uid'],
                'source_frame_of_reference_uid':source['frame_of_reference_uid'],
                'source_geometry':source['geometry'],
                'source_instances':[{'instance_uid':row['instance_uid'],'dicom_sha256':source_files[row['instance_uid']]['sha256'],
                    'snapshot_path':str(stored[row['instance_uid']]),'metadata_sha256':row['metadata_sha256']} for row in source['instances']]}
            del image,output_image,converted
        validate_sequences({role:derived[role]['nifti_path'] for role in ROLES})
        if any(sha_file(path)!=source_files[uid]['sha256'] for uid,path in paths.items()):
            fail('original_changed_during_conversion', '原文件在转换窗口内改变；产物未取得完成状态。')
        report={'format':'dicom-local-conversion-v1','status':'converted_and_verified','data_role':plan['data_role'],
            'plan_revision':plan['plan_revision'],'case_id':plan['case_id'],'archive_id':plan['archive_id'],
            'archive_fingerprint':plan['archive_fingerprint'],'model_input_contract':plan['model_input_contract'],
            'resampling':resampling,'target_grid':target_grid,
            'converter':{'tool':'SimpleITK.ImageSeriesReader/GDCMImageIO','simpleitk_version':sitk.Version_VersionString(),
                'itk_version':sitk.Version_ITKVersionString(),'bundled_gdcm_version':'not_exposed_by_this_python_API',
                'pydicom_version':pydicom.__version__,
                'parameters':{'input_order':'validated_UIDs_ascending_IPP_projection','output_pixel_type':'float32',
                    'force_orthogonal_direction':False,'private_tags_loaded':False,'metadata_dictionary_loaded':False,
                    'original_OB_padding':'standard_even_value_length_only_no_source_rewrite',
                    'output':'compressed_NIfTI','intensity_mapping':'stored_pixel*RescaleSlope+RescaleIntercept',
                    'registration_or_resampling':bool(resampling),
                    'resampling_interpolation':resampling['interpolation'] if resampling else None,
                    'resampling_reference_role':resampling['reference_role'] if resampling else None,
                    'coordinate_mapping':resampling['coordinate_mapping'] if resampling else None,
                    'outside_value':resampling['outside_value'] if resampling else None},
                'documentation':'https://simpleitk.readthedocs.io/en/master/link_DicomSeriesReader_docs.html',
                'installation':'existing_local_environment_no_new_install'},
            'outputs':derived,'timing_ms':conversion_ms,'total_elapsed_ms':(perf_counter()-started)*1000,
            'original_dicom_byte_hashes_verified':True,'existing_model_geometry_contract_passed':True,
            'model_input_eligible':False,'inference_performed':False,'archive_or_business_database_written':False,
            'source_review_status':plan['role_confirmation_status'],
            'limitations':['元数据/像素映射验证不等于真实归档身份、来源许可或医生角色审核。',
                           '转换产物未激活为病例当前MRI，不会触发模型；真实四序列端到端另验。']}
        with (directory/'conversion-report.json').open('x',encoding='utf-8') as handle:
            json.dump(report,handle,ensure_ascii=False,indent=2,allow_nan=False)
        return report
    except Exception as e:
        reason=e.reason if isinstance(e,PlanError) else 'conversion_failed'
        message=str(e) if isinstance(e,PlanError) else '转换或独立核对失败；保留本版本目录，不输出标签/解码异常原文。'
        with (directory/'conversion-failure.json').open('x',encoding='utf-8') as handle:
            json.dump({'status':'rejected','reason':reason,'message':message,'model_input_eligible':False,
                       'conversion_complete':False,'original_files_rewritten':False},handle,ensure_ascii=False,indent=2)
        if isinstance(e,PlanError):raise
        fail(reason,message)

