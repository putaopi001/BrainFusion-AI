"""Reopen a local conversion against an explicitly pinned receipt and current plan.

This is a read-only integrity check, never permission to activate model inputs.
The caller's report SHA is an audit anchor, not an authenticated signature.
"""
import gzip
import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import nibabel as nib
import numpy as np

from app.services.dicom_input_plan import PlanError, ROLES, validate_plan
from app.core.storage import is_supported_storage_path
from app.services.dicom_resampling import resample_array
from app.services.study_validation import validate_model_geometry

REPORT_CAP = 4 * 1024 * 1024
NIFTI_CAP = 128 * 1024 * 1024 + 1024 * 1024
SHA = re.compile(r'[0-9a-f]{64}')
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_INPUT_BYTES = 1024 * 1024 * 1024


def source_dataset(raw, source, instance):
    # Optional DICOM parser must not become a startup dependency of the API.
    try:
        from app.services.dicom_conversion import source_dataset as read_dataset
    except ImportError:
        fail('conversion_dependency_unavailable', 'DICOM核对依赖不可用；保持现有NIfTI入口。')
    return read_dataset(raw, source, instance)


def fail(reason, message):
    raise PlanError(reason, message)


def unique_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('Duplicate key')
        result[key] = value
    return result


def reject_constant(_value):
    raise ValueError('Nonfinite number')


def bounded_bytes(path, cap):
    if not path.is_file():
        fail('conversion_file_missing', '转换报告、原字节快照或NIfTI缺失。')
    if path.stat().st_size > cap:
        fail('conversion_file_budget_exceeded', '转换文件超过本地检查预算。')
    with path.open('rb') as handle:
        raw = handle.read(cap + 1)
    if len(raw) > cap:
        fail('conversion_file_budget_exceeded', '读取窗口内文件超过检查预算。')
    return raw


def scoped_path(root, expected, declared=None):
    # Only converter-owned canonical names; no arbitrary path from report JSON.
    if declared is not None and (not isinstance(declared, str) or Path(declared).absolute() != expected):
        fail('conversion_path_mismatch', '版本报告的路径与本版本固定文件名不一致。')
    resolved = expected.resolve()
    if resolved != expected or not resolved.is_relative_to(root):
        fail('conversion_path_escape', '转换版本含重定向路径，未读取目录外文件。')
    return expected


def verify_nifti(raw, source, row, target_grid=None):
    """Bound decompression before loading; float32 single-file converter output only."""
    output_geometry = target_grid if target_grid is not None else source['geometry']
    output_dimensions = output_geometry['dimensions']
    output_affine = (output_geometry['affine_ras_mm'] if target_grid is not None
                     else source['expected_source_ijk_to_ras_mm'])
    voxel_count = int(np.prod(output_dimensions))
    expected_length = 352 + voxel_count * 4
    if expected_length > NIFTI_CAP:
        fail('conversion_file_budget_exceeded', 'NIfTI展开大小超过现有模型预算。')
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as handle:
            expanded = handle.read(expected_length + 1)
        if len(expanded) != expected_length:
            fail('conversion_nifti_layout_invalid', 'NIfTI展开字节数与规划的float32矩阵不一致。')
        header = nib.Nifti1Header.from_fileobj(io.BytesIO(expanded), check=False)
        if (header['sizeof_hdr'] != 348 or header['magic'].tobytes() != b'n+1\x00'
                or float(header['vox_offset']) != 352 or expanded[348:352] != b'\x00' * 4
                or header.get_data_dtype() != np.dtype('<f4')
                or float(header['scl_slope']) != 1 or float(header['scl_inter']) != 0):
            fail('conversion_nifti_layout_invalid', 'NIfTI格式、数据偏移或缩放不同于已支持转换协议。')
        image = nib.Nifti1Image.from_bytes(expanded)
    except PlanError:
        raise
    except Exception:
        fail('conversion_nifti_unreadable', '转换NIfTI无法读取，未输出解析异常或私有值。')
    affine = np.asarray(output_affine)
    qform, qcode = image.header.get_qform(coded=True)
    sform, scode = image.header.get_sform(coded=True)
    if (image.shape != tuple(output_dimensions)
            or image.header.get_xyzt_units()[0] != 'mm'
            or not np.allclose(image.affine, affine, atol=1e-4, rtol=0)
            or not qcode or not scode
            or not np.allclose(qform, sform, atol=1e-4, rtol=0)):
        fail('conversion_nifti_geometry_invalid', '转换NIfTI矩阵、毫米单位或患者空间失效。')
    validate_model_geometry(image.shape, image.affine, image.header.get_zooms()[:3])
    if (row.get('shape') != list(image.shape) or row.get('qform_code') != int(qcode)
            or row.get('sform_code') != int(scode)
            or not np.array_equal(np.asarray(row.get('affine_ras_mm')), image.affine)
            or not np.array_equal(np.asarray(row.get('spacing_xyz_mm')), image.header.get_zooms()[:3])):
        fail('conversion_output_claim_mismatch', '报告中的NIfTI空间记录与实际文件不同。')
    return np.asarray(image.dataobj, dtype=np.float32)


def _inspect(directory, expected_report_sha256, proposal, snapshots):
    if not isinstance(expected_report_sha256, str) or not SHA.fullmatch(expected_report_sha256):
        fail('conversion_receipt_anchor_required', '需要外部保留的转换报告SHA；不从报告自身推定可信版本。')
    root = Path(directory).absolute()
    if not is_supported_storage_path(root) or not root.is_dir() or root.resolve() != root:
        fail('conversion_directory_unavailable', '转换版本必须是可读取的E盘独立目录。')
    report_path = scoped_path(root, root / 'conversion-report.json')
    raw_report = bounded_bytes(report_path, REPORT_CAP)
    if hashlib.sha256(raw_report).hexdigest() != expected_report_sha256:
        fail('conversion_report_sha_mismatch', '转换报告与外部保留的版本校验和不同。')
    report = json.loads(raw_report.decode('utf-8'), object_pairs_hook=unique_pairs, parse_constant=reject_constant)
    if (not isinstance(report, dict) or report.get('format') != 'dicom-local-conversion-v1'
            or report.get('status') != 'converted_and_verified'
            or any(report.get(key) is not False for key in ['model_input_eligible', 'inference_performed', 'archive_or_business_database_written'])
            or report.get('converter', {}).get('parameters', {}).get('registration_or_resampling') not in (False, True)):
        fail('conversion_report_invalid', '报告不符合只读转换协议，不能取得可用状态。')
    plan = validate_plan(proposal, snapshots)
    resampled=bool(plan.get('resampling'))
    if (report.get('converter', {}).get('parameters', {}).get('registration_or_resampling') is not resampled
            or report.get('resampling') != plan.get('resampling')
            or report.get('target_grid') != plan.get('target_grid')):
        fail('conversion_resampling_claim_mismatch','报告中的重采样声明与当前已确认方案不一致。')
    if any(report.get(key) != plan[key] for key in ['plan_revision', 'case_id', 'archive_id', 'archive_fingerprint', 'data_role', 'model_input_contract']):
        fail('conversion_source_stale', '当前病例、归档、角色声明或来源版本已改变；旧转换仅保留历史。')
    outputs = report.get('outputs')
    if not isinstance(outputs, dict) or set(outputs) != set(ROLES):
        fail('conversion_output_set_mismatch', '转换版本必须完整保留四个角色。')
    verified = {}; observed = {report_path: expected_report_sha256}; total_source_bytes = 0
    for role in ROLES:
        row, source = outputs[role], plan['sources'][role]
        if not isinstance(row, dict) or any(row.get('source_' + key) != source[key] for key in ['study_uid', 'series_uid', 'frame_of_reference_uid']):
            fail('conversion_source_identity_mismatch', '转换报告的Study/Series/Frame来源不同于当前规划。')
        instances = row.get('source_instances')
        if not isinstance(instances, list) or len(instances) != len(source['instances']):
            fail('conversion_instance_set_mismatch', '原字节快照实例集合或顺序缺失。')
        output = scoped_path(root, root / (role + '.nii.gz'), row.get('nifti_path'))
        raw = bounded_bytes(output, NIFTI_CAP)
        output_sha = hashlib.sha256(raw).hexdigest()
        if row.get('sha256') != output_sha:
            fail('conversion_nifti_sha_mismatch', '转换NIfTI字节与版本记录不同。')
        observed[output] = output_sha
        target_grid=plan.get('target_grid') if resampled else None
        pixels = verify_nifti(raw, source, row,target_grid)
        if resampled and row.get('source_geometry') != source['geometry']:
            fail('conversion_source_geometry_mismatch','报告源几何与当前DICOM元数据规划不同。')
        expected_hash, actual_hash = hashlib.sha256(), hashlib.sha256(); nonzero = False; error = 0.
        source_slices=[]
        for k, (record, planned) in enumerate(zip(instances, source['instances'])):
            if (not isinstance(record, dict) or record.get('instance_uid') != planned['instance_uid']
                    or record.get('metadata_sha256') != planned['metadata_sha256']
                    or not isinstance(record.get('dicom_sha256'), str) or not SHA.fullmatch(record['dicom_sha256'])):
                fail('conversion_instance_set_mismatch', '快照UID、顺序或元数据版本与当前规划不同。')
            path = scoped_path(root, root / 'original-byte-snapshots' / (record['dicom_sha256'] + '.dcm'), record.get('snapshot_path'))
            dicom = bounded_bytes(path, MAX_FILE_BYTES); total_source_bytes += len(dicom)
            if total_source_bytes > MAX_INPUT_BYTES:
                fail('conversion_file_budget_exceeded', '原字节快照总量超过1GiB。')
            if hashlib.sha256(dicom).hexdigest() != record['dicom_sha256']:
                fail('conversion_snapshot_sha_mismatch', '原DICOM快照字节与转换版本不同。')
            observed[path] = record['dicom_sha256']
            ds = source_dataset(dicom, source, planned)
            expected = np.asarray(ds.pixel_array, dtype=np.float32) * float(ds.get('RescaleSlope', 1)) + float(ds.get('RescaleIntercept', 0))
            if resampled:
                source_slices.append(expected)
            else:
                actual = pixels[:, :, k].T
                if expected.shape != actual.shape or not np.isfinite(actual).all() or not np.isfinite(expected).all():
                    fail('conversion_pixels_invalid', '重新打开的源像素或转换像素不符合矩阵/有限值要求。')
                error = max(error, float(np.max(np.abs(expected - actual))))
                if not np.allclose(expected, actual, atol=1e-4, rtol=0):
                    fail('conversion_pixels_mismatch', '重新打开后像素与原存储值和显式Rescale不同。')
                nonzero = nonzero or bool(np.any(actual != 0))
                expected_hash.update(np.asarray(expected, dtype='<f4').tobytes(order='C'))
                actual_hash.update(np.asarray(actual, dtype='<f4').tobytes(order='C'))
        if resampled:
            expected_volume=resample_array(np.stack(source_slices,axis=0),source['geometry'],target_grid,
                                           plan['resampling']['outside_value'])
            actual_volume=pixels.transpose(2,1,0)
            if expected_volume.shape!=actual_volume.shape or not np.isfinite(expected_volume).all() or not np.isfinite(actual_volume).all():
                fail('conversion_pixels_invalid','重采样后的体数据矩阵或有限值不符合目标空间。')
            error=float(np.max(np.abs(expected_volume-actual_volume)))
            if not np.allclose(expected_volume,actual_volume,atol=1e-4,rtol=0):
                fail('conversion_pixels_mismatch','重开版本与源DICOM独立插值结果不一致。')
            nonzero=bool(np.any(actual_volume!=0))
            expected_hash.update(np.asarray(expected_volume,dtype='<f4').tobytes(order='C'))
            actual_hash.update(np.asarray(actual_volume,dtype='<f4').tobytes(order='C'))
        if (not nonzero or row.get('all_voxels_compared') != pixels.size
                or row.get('expected_scaled_voxel_sha256') != expected_hash.hexdigest()
                or row.get('actual_voxel_sha256') != actual_hash.hexdigest()
                or row.get('maximum_absolute_intensity_error') != error):
            fail('conversion_output_claim_mismatch', '全体素校验或误差记录与重新核对结果不同。')
        verified[role] = {'nifti_sha256': output_sha, 'source_series_uid': source['series_uid'],
                          'all_voxels_compared': int(pixels.size), 'maximum_absolute_intensity_error': error}
        del pixels, raw
    # Re-read hashes at the end; a concurrent change never becomes accepted.
    for path, sha in observed.items():
        cap = REPORT_CAP if path == report_path else NIFTI_CAP if path.suffix == '.gz' else MAX_FILE_BYTES
        scoped_path(root, path)
        if hashlib.sha256(bounded_bytes(path, cap)).hexdigest() != sha:
            fail('conversion_changed_during_inspection', '检查窗口内转换版本发生变化，本次不能取得完整状态。')
    return {'status': 'verified_readonly', 'reason': None, 'data_role': plan['data_role'],
            'case_id': plan['case_id'], 'plan_revision': plan['plan_revision'],
            'report_sha256': expected_report_sha256, 'outputs': verified,
            'source_snapshots_byte_hashes_verified': True, 'all_converted_voxels_rechecked': True,
            'current_plan_matched': True}


def inspect_conversion_version(directory, expected_report_sha256, proposal, snapshots):
    base = {'format': 'dicom-conversion-inspection-v1', 'checked_utc': datetime.now(timezone.utc).isoformat(),
            'model_input_eligible': False, 'inference_performed': False, 'source_files_written': False,
            'archive_or_business_database_written': False, 'archive_case_binding_independently_verified': False,
            'reviewer_authenticated': False, 'live_archive_reconciled': False,
            'receipt_anchor_status': 'caller_supplied_SHA_not_authenticated_signature',
            'limitations': ['只核对本地版本和当前提供的规划，不证明真实归档、数据许可、像素审核或医生身份。',
                            '通过后仍不得自动替换病例当前MRI或触发模型。']}
    try:
        return {**base, **_inspect(directory, expected_report_sha256, proposal, snapshots)}
    except PlanError as e:
        status = 'stale' if e.reason == 'conversion_source_stale' else 'unavailable' if e.reason in ['conversion_file_missing', 'conversion_directory_unavailable', 'conversion_dependency_unavailable'] else 'invalid'
        return {**base, 'status': status, 'reason': e.reason, 'message': str(e)}
    except Exception:
        return {**base, 'status': 'invalid', 'reason': 'conversion_inspection_failed',
                'message': '本地转换版本无法核对，未输出路径、标签或异常原文。'}

