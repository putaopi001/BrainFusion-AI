"""Auditable, read-only four-role metadata planning. Never authorizes AI/import."""
import hashlib
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Literal

import numpy as np
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError, field_validator

from app.services.dicom_series import validate_series
from app.services.dicom_resampling import ResamplingError, build_target_grid, ensure_grid_covered
from app.services.pacs_client import validate_uid
from app.services.study_validation import MODEL_INPUT_CONTRACT_ID, validate_model_geometry

ROLES = ('t1c', 't1n', 't2w', 't2f')
SHA = r'^[0-9a-f]{64}$'
ROLE_SIGNALS = {'t1c': ('T1', 'post', False), 't1n': ('T1', 'pre', False),
                't2w': ('T2', 'not_applicable', False), 't2f': ('T2', 'not_applicable', True)}


class PlanError(ValueError):
    def __init__(self, reason, message):
        super().__init__(message)
        self.reason = reason


def fail(reason, message):
    raise PlanError(reason, message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def metadata_semantic_digest(metadata):
    # DICOM JSON may spell the same DS/IS value as a number or string.
    # Keep the exact API revision separately; file readers compare numeric
    # meaning without silently rewriting the source snapshot.
    clean = {}
    for tag, item in metadata.items():
        if tag == '7FE00010':
            continue
        values = item['Value']
        if item['vr'] == 'DS':
            values = [float(value) for value in values]
        elif item['vr'] in ('IS', 'US'):
            values = [int(value) for value in values]
        clean[tag] = {'vr': item['vr'], 'Value': values}
    return digest(clean)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class RoleEvidence(StrictModel):
    # These are operator declarations, not an automatic reading of MRI physics.
    weighting: Literal['T1', 'T2']
    contrast_phase: Literal['pre', 'post', 'not_applicable']
    fluid_attenuated: StrictBool
    basis: Literal['acquisition_record', 'published_protocol', 'local_manual_review']
    evidence_sha256: str = Field(pattern=SHA)
    evidence_reference: str = Field(pattern=r'^[a-zA-Z0-9_.:-]{1,128}$')
    reviewer_reference: str = Field(pattern=r'^[a-zA-Z0-9_.:-]{1,128}$')
    confirmed_at: datetime

    @field_validator('confirmed_at')
    @classmethod
    def aware_time(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('Confirmation timestamp requires timezone')
        return value.astimezone(timezone.utc)


class ResamplingPolicy(StrictModel):
    format: Literal['dicom-model-resampling-policy-v1']
    reference_role: Literal['t1c']
    target_spacing_xyz_mm: list[float] = Field(min_length=3, max_length=3)
    interpolation: Literal['linear']
    coordinate_mapping: Literal['same_frame_of_reference_identity']
    outside_value: float

    @field_validator('target_spacing_xyz_mm', 'outside_value')
    @classmethod
    def finite_values(cls, value):
        values = value if isinstance(value, list) else [value]
        if any(not np.isfinite(float(item)) for item in values):
            raise ValueError('Resampling values must be finite')
        return value

    @field_validator('target_spacing_xyz_mm')
    @classmethod
    def supported_spacing(cls, value):
        if not np.allclose(np.asarray(value, dtype=float), [1.0, 1.0, 1.0], atol=1e-6, rtol=0):
            raise ValueError('The current model only supports explicit 1 mm isotropic output')
        return [float(item) for item in value]


class Assignment(StrictModel):
    role: Literal['t1c', 't1n', 't2w', 't2f']
    study_uid: str
    series_uid: str
    series_metadata_sha256: str = Field(pattern=SHA)
    evidence: RoleEvidence

    @field_validator('study_uid', 'series_uid')
    @classmethod
    def uid(cls, value):
        try:
            return validate_uid(value)
        except HTTPException:
            raise ValueError('Invalid DICOM UID') from None


class Proposal(StrictModel):
    format: Literal['dicom-model-input-proposal-v1']
    case_id: int = Field(strict=True, gt=0)
    archive_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    archive_fingerprint: str = Field(pattern=SHA)
    data_role: Literal['synthetic-fixture', 'dicom-metadata-snapshot']
    assignments: list[Assignment] = Field(min_length=4, max_length=4)
    resampling: ResamplingPolicy | None = None


def source_affine_ras(geometry):
    """Expected column,row,plane grid only; does not write a NIfTI conversion."""
    affine = np.eye(4)
    a, b = geometry['image_orientation_patient'][:3], geometry['image_orientation_patient'][3:]
    direction = np.array([a, b, geometry['unit_normal_for_sorting']], dtype=float).T
    affine[:3, :3] = direction @ np.diag(geometry['spacing_xyz_mm'])
    affine[:3, 3] = geometry['origin_lps_mm']
    return np.diag([-1., -1., 1., 1.]) @ affine


def validate_plan(proposal, bundle):
    try:
        selection = Proposal.model_validate(proposal)
    except ValidationError:
        fail('invalid_proposal', '四序列确认规划格式无效；必须逐项明确角色、版本和带时区的确认依据。')
    assignments = {item.role: item for item in selection.assignments}
    if set(assignments) != set(ROLES):
        fail('four_distinct_roles_required', '必须各提供一次T1c、T1n、T2w、FLAIR，不能重复角色。')
    if len({item.series_uid for item in selection.assignments}) != 4:
        fail('distinct_series_required', '同一Series不能同时冒充多个模型序列。')
    if len({item.study_uid for item in selection.assignments}) != 1:
        fail('cross_study_not_supported', '初版不接受跨Study组装模型输入；先核实同检查来源。')
    if (not isinstance(bundle, dict) or bundle.get('format') != 'dicom-series-snapshot-bundle-v1'
            or bundle.get('data_role') != selection.data_role
            or not isinstance(bundle.get('series'), list) or len(bundle['series']) != 4):
        fail('four_source_snapshots_required', '必须提供与规划用途相符的四个完整序列快照；元数据快照不是归档认证。')
    indexed = {}
    for snapshot in bundle['series']:
        if not isinstance(snapshot, dict):
            fail('invalid_snapshot', '序列快照格式无效。')
        series_uid = snapshot.get('series_uid')
        if not isinstance(series_uid, str) or series_uid in indexed:
            fail('duplicate_source_snapshot', '序列快照UID缺失或重复。')
        indexed[series_uid] = snapshot
    expected_series = {item.series_uid for item in selection.assignments}
    if set(indexed) != expected_series:
        fail('source_set_mismatch', '确认记录与序列快照的UID集合不一致。')
    all_instances, sources, reference = set(), {}, None
    for role in ROLES:
        item = assignments[role]
        evidence = item.evidence
        if (evidence.weighting, evidence.contrast_phase, evidence.fluid_attenuated) != ROLE_SIGNALS[role]:
            fail('role_evidence_conflict', '角色声明与加权/对比剂阶段/液体抑制声明冲突；未按名称猜测。')
        snapshot = indexed[item.series_uid]
        if (snapshot.get('format') != 'dicom-series-view-manifest-v1'
                or type(snapshot.get('source_case_id')) is not int or snapshot['source_case_id'] != selection.case_id
                or snapshot.get('study_uid') != item.study_uid
                or snapshot.get('archive_id') != selection.archive_id
                or snapshot.get('archive_fingerprint') != selection.archive_fingerprint):
            fail('source_context_mismatch', '病例/检查/归档来源与确认记录不一致；拒绝旧来源。')
        rows = snapshot.get('instances')
        if not isinstance(rows, list) or len(rows) > 512 or len(rows) != snapshot.get('instance_count'):
            fail('invalid_snapshot', '实例清单缺失或数量与快照不一致。')
        try:
            raw = [row['metadata'] for row in rows]
            uids = [row['instance_uid'] for row in rows]
            checked = validate_series(SimpleNamespace(allow_pixel_read=False), raw,
                                      item.study_uid, item.series_uid, uids)
        except HTTPException as e:
            fail(e.detail['reason'], e.detail['message'])
        except (TypeError, KeyError, ValueError, AttributeError):
            fail('invalid_snapshot', '实例快照结构无效。')
        if any(uid in all_instances for uid in uids):
            fail('source_instance_reused', '同一SOP Instance被多个序列重复使用。')
        all_instances.update(uids)
        revisions = {row['instance_uid']: row['metadata_sha256'] for row in checked['instances']}
        if any(row.get('metadata_sha256') != revisions[row['instance_uid']] for row in rows):
            fail('instance_snapshot_revision_mismatch', '实例元数据与记录的版本不一致。')
        if (checked['metadata_sha256'] != item.series_metadata_sha256
                or snapshot.get('metadata_sha256') != checked['metadata_sha256']):
            fail('series_snapshot_revision_mismatch', '序列元数据已改变，原确认不可沿用。')
        geometry = checked['geometry']
        if snapshot.get('geometry') != geometry:
            fail('snapshot_geometry_mismatch', '快照空间与实例元数据重算结果不一致。')
        affine = source_affine_ras(geometry)
        if selection.resampling is None:
            try:
                validate_model_geometry(geometry['dimensions'], affine, geometry['spacing_xyz_mm'])
            except ValueError as e:
                reason = ('model_spacing_unsupported' if '1 mm' in str(e) else
                          'model_oblique_unsupported' if 'Oblique' in str(e) else 'model_grid_unsupported')
                fail(reason, 'DICOM原网格不满足现有模型契约：' + str(e) + '。未自动配准或重采样。')
        if reference is not None:
            if geometry['frame_of_reference_uid'] != reference['frame_of_reference_uid']:
                fail('model_frames_differ', '四序列FrameOfReference不同，未自动配准。')
            if (selection.resampling is None
                    and (geometry['dimensions'] != reference['dimensions']
                         or not np.allclose(affine, source_affine_ras(reference), atol=1e-4, rtol=0))):
                fail('model_grids_differ', '四序列原矩阵/affine不同，未自动重采样或对齐。')
        else:
            reference = geometry
        sources[role] = {'study_uid': item.study_uid, 'series_uid': item.series_uid,
                         'frame_of_reference_uid': geometry['frame_of_reference_uid'],
                         'series_metadata_sha256': checked['metadata_sha256'],
                         'instances': [{'instance_uid': row['instance_uid'], 'metadata_sha256': row['metadata_sha256'],
                                        'metadata_semantic_sha256': metadata_semantic_digest(row['metadata']),
                                        'position_lps_mm': row['position_lps_mm']} for row in checked['instances']],
                         'geometry': geometry, 'expected_source_ijk_to_ras_mm': affine.tolist(),
                         'role_declaration': evidence.model_dump(mode='json')}
    target_grid = None
    if selection.resampling is not None:
        try:
            target_grid = build_target_grid(sources['t1c']['geometry'],
                                            selection.resampling.target_spacing_xyz_mm)
            for source in sources.values():
                ensure_grid_covered(source['geometry'], target_grid)
        except ResamplingError as e:
            fail('model_resampling_geometry_invalid', str(e))
    content = {'format': 'dicom-model-input-plan-v1', 'data_role': selection.data_role,
               'case_id': selection.case_id, 'archive_id': selection.archive_id,
               'archive_fingerprint': selection.archive_fingerprint,
               'model_input_contract': MODEL_INPUT_CONTRACT_ID, 'sources': sources,
               'resampling': selection.resampling.model_dump(mode='json') if selection.resampling else None,
               'target_grid': target_grid}
    return {**content, 'plan_revision': digest(content), 'status': 'metadata_plan_ready',
            'created_utc': datetime.now(timezone.utc).isoformat(),
            'metadata_geometry_contract_passed': True,
            'role_confirmation_status': 'supplied_declarations_not_authenticated_or_independently_verified',
            'archive_case_binding_independently_verified': False,
            'source_dicom_bytes_verified': False, 'conversion_performed': False,
            'model_input_eligible': False, 'registration_or_resampling': selection.resampling is not None,
            'next_required': ['verified_archive_case_binding_and_original_DICOM_SHA',
                              'source_and_role_review', 'supported_converter_version_and_parameters',
                              'converted_NIfTI_SHA_geometry_voxel_mapping_and_existing_model_validation'],
            'limitations': ['元数据SHA不是原DICOM文件或像素校验和。',
                           '本地JSON声明不能证明审核者身份、医生复核或数据许可。',
                           '预期affine只是源索引坐标映射，不能冒充转换所得NIfTI。']}


def plan_report(proposal, bundle):
    """Stable redacted negative outcome, suitable for an immutable CLI receipt."""
    try:
        return validate_plan(proposal, bundle)
    except PlanError as e:
        return {'format': 'dicom-model-input-plan-v1', 'status': 'rejected',
                'reason': e.reason, 'message': str(e), 'metadata_geometry_contract_passed': False,
                'model_input_eligible': False, 'conversion_performed': False,
                'registration_or_resampling': False}
