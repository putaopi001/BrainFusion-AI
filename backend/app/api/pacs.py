"""Local archive queries, case mapping and guarded DICOM viewing; no AI activation."""
import hashlib
import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, Path as ApiPath
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import require_dicom_parser

require_dicom_parser()

from app.database import get_db
from app.models.case import Case
from app.models.pacs import PACSStudyLink
from app.services.pacs_client import PacsClient, fail, load_config, validate_uid
from app.core.storage import is_supported_storage_path
from app.services.pacs_wado import checked_metadata, frame_bytes, multipart_response, metadata_revision
from app.services.dicom_series import series_manifest
from app.services.pacs_reconcile import ReconciliationClient
from app.services.dicom_conversion_registry import load_index, inspect_entry, check_archive_entry, entry_inputs
from app.services.dicom_input_plan import PlanError
from app.services import dicom_conversion_role_review as dicom_role_review
from app.services import dicom_conversion_jobs
from app.services import dicom_web_plan
from app.services import pacs_import
from app.services import dicom_measurements
from app.services import dicom_view_state
from app.services import dicom_report
from app.services import dicom_review
from app.services.local_auth import require_doctor

router = APIRouter(prefix='/pacs', tags=['pacs'])


def no_store(response: Response):
    response.headers['Cache-Control'] = 'no-store'


@router.get('/status', dependencies=[Depends(no_store)])
def status():
    try:
        with PacsClient() as archive:
            archive.query('studies', limit=1)
            viewing = bool(archive.config.allow_pixel_read
                           and archive.config.expected_database_server_identifier)
            try:
                importing = bool(archive.config.expected_database_server_identifier and pacs_import.registry())
            except HTTPException:
                importing = False
            message = ('归档查询可用；已启用受支持序列的 DICOM 阅片，仍需核对空间并关联病例。'
                       if viewing else '归档查询可用；阅片需要后台启用像素读取并固定归档标识。')
            return {'code': 200, 'data': {'state': 'ready', 'read_available': True,
                    'archive_id': archive.config.archive_id, 'orthanc_version': archive.version,
                    'pixel_read_enabled': archive.config.allow_pixel_read,
                    'message': message + ('可从下方已核对资料导入，AI 桥接尚未开放。' if importing else '尚无可用的已登记导入资料，AI 桥接尚未开放。'),
                    'import_available': importing, 'dicom_view_available': viewing, 'ai_bridge_available': False}}
    except HTTPException as exc:
        return {'code': 200, 'data': {'state': exc.detail['reason'], 'message': exc.detail['message'],
                'read_available': False, 'import_available': False, 'dicom_view_available': False,
                'ai_bridge_available': False, 'pixel_read_enabled': False}}


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    acknowledge_reviewed_local_viewing_only: Literal[True]


@router.get('/import-candidates', dependencies=[Depends(no_store)])
def import_candidates():
    config = load_config()
    return {'code':200,'data':{'items':[{**pacs_import.public_candidate(row),
             'latest_import':pacs_import.current(row['candidate_id'],config)} for row in pacs_import.registry()]}}


@router.get('/imports/{candidate_id}', dependencies=[Depends(no_store)])
def import_status(candidate_id:str):
    pacs_import.candidate(candidate_id)
    return {'code':200,'data':pacs_import.current(candidate_id)}


@router.post('/imports/{candidate_id}', dependencies=[Depends(no_store)])
def import_candidate(candidate_id:str,payload:ImportRequest):
    return {'code':200,'data':pacs_import.execute(candidate_id,payload.acknowledge_reviewed_local_viewing_only)}


def read(level, study_uid=None, series_uid=None, limit=100, offset=0):
    # Validate identifiers before making any upstream request.
    if study_uid is not None:
        validate_uid(study_uid)
    if series_uid is not None:
        validate_uid(series_uid)
    with PacsClient() as archive:
        items = archive.query(level, study_uid, series_uid, limit, offset)
        return {'code': 200, 'data': {'archive_id': archive.config.archive_id, 'items': items,
                'limit': limit, 'offset': offset, 'next_offset': offset + limit if len(items) == limit else None}}


@router.get('/studies', dependencies=[Depends(no_store)])
def studies(study_uid: str | None = None, limit: int = Query(50, ge=1, le=100),
            offset: int = Query(0, ge=0, le=100000)):
    return read('studies', study_uid, limit=limit, offset=offset)


@router.get('/studies/{study_uid}/series', dependencies=[Depends(no_store)])
def series(study_uid: str, limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0, le=100000)):
    return read('series', study_uid, limit=limit, offset=offset)


@router.get('/studies/{study_uid}/series/{series_uid}/instances', dependencies=[Depends(no_store)])
def instances(study_uid: str, series_uid: str, limit: int = Query(100, ge=1, le=100),
              offset: int = Query(0, ge=0, le=100000)):
    return read('instances', study_uid, series_uid, limit, offset)


@router.get('/studies/{study_uid}/series/{series_uid}/view-manifest', dependencies=[Depends(no_store)])
def view_manifest(study_uid: str, series_uid: str):
    validate_uid(study_uid); validate_uid(series_uid)
    config = load_config()
    if not config.allow_pixel_read or not config.expected_database_server_identifier:
        fail('pixel_read_disabled', '隔离归档只读阅片需要本地启用像素读取并固定归档标识。')
    with ReconciliationClient(config) as archive:
        manifest = series_manifest(archive, study_uid, series_uid)
    for row in manifest['instances']:
        row['metadata']['7FE00010']['BulkDataURI'] = (
            f'/pacs/archive/studies/{study_uid}/series/{series_uid}/instances/{row["instance_uid"]}/frames/1'
            f'?metadata_sha256={row["metadata_sha256"]}&archive_fingerprint={config.endpoint_fingerprint}')
    manifest.update(source_case_id=None, archive_only=True, transport_enabled=True,
                    saved_dicom_annotations_available=False, dicom_view_state_available=False,
                    segmentation_overlay_available=False)
    return {'code': 200, 'data': manifest}


@router.get('/archive/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/frames/{frame_number}')
def archive_frame(study_uid: str, series_uid: str, instance_uid: str,
                  frame_number: int = ApiPath(ge=1, le=1),
                  metadata_sha256: str = Query(pattern=r'^[0-9a-f]{64}$'),
                  archive_fingerprint: str = Query(pattern=r'^[0-9a-f]{64}$')):
    for uid in (study_uid, series_uid, instance_uid):
        validate_uid(uid)
    config = load_config()
    if not config.allow_pixel_read or not config.expected_database_server_identifier:
        fail('pixel_read_disabled', '隔离归档的帧读取仅在已固定身份的研究阅片配置中启用。')
    if config.endpoint_fingerprint != archive_fingerprint:
        fail('archive_revision_mismatch', '隔离归档配置版本已变化，请重新打开序列。', 409)
    with ReconciliationClient(config) as archive:
        item, expected = checked_metadata(archive, study_uid, series_uid, instance_uid)
        if metadata_revision(item) != metadata_sha256:
            fail('instance_revision_mismatch', 'DICOM 元数据版本已变化，拒绝使用旧帧地址。', 409)
        pixels = frame_bytes(archive, study_uid, series_uid, instance_uid, expected)
    body, content_type = multipart_response(pixels)
    return Response(body, media_type=content_type, headers={'Cache-Control': 'no-store'})


@router.get('/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/metadata')
def instance_metadata(study_uid: str, series_uid: str, instance_uid: str):
    for uid in (study_uid, series_uid, instance_uid): validate_uid(uid)
    with PacsClient() as archive:
        item, _ = checked_metadata(archive, study_uid, series_uid, instance_uid)
    return JSONResponse([item], media_type='application/dicom+json', headers={'Cache-Control':'no-store'})


@router.get('/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/frames/{frame_number}')
def instance_frame(study_uid: str, series_uid: str, instance_uid: str, frame_number: int = ApiPath(ge=1, le=1)):
    for uid in (study_uid, series_uid, instance_uid): validate_uid(uid)
    config = load_config()
    if not config.allow_pixel_read:
        fail('pixel_read_disabled', '像素读取默认关闭；完成数据来源和像素脱敏核查后才能由本地服务端启用。')
    with PacsClient(config) as archive:
        _, expected = checked_metadata(archive, study_uid, series_uid, instance_uid)
        pixels = frame_bytes(archive, study_uid, series_uid, instance_uid, expected)
    body, content_type = multipart_response(pixels)
    return Response(body, media_type=content_type, headers={'Cache-Control':'no-store'})


def link_result(row, config=None):
    return {'id': row.id, 'case_id': row.case_id, 'archive_id': row.archive_id, 'study_uid': row.study_uid,
            'metadata_sha256': row.metadata_sha256, 'confirmation_method': row.confirmation_method,
            'created_time': row.created_time.isoformat() + 'Z',
            'archive_matches_config': bool(config and row.archive_id == config.archive_id
                                           and row.endpoint_fingerprint == config.endpoint_fingerprint)}


@router.get('/cases/{case_id}/links', dependencies=[Depends(no_store)])
def links(case_id: int, db: Session = Depends(get_db)):
    if not db.get(Case, case_id):
        fail('case_not_found', '病例不存在。', 404)
    try:
        config = load_config()
    except HTTPException:
        config = None
    rows = db.query(PACSStudyLink).filter_by(case_id=case_id).order_by(PACSStudyLink.id).all()
    return {'code': 200, 'data': {'items': [link_result(row, config) for row in rows]}}


def conversion_context(entry, rows, config):
    return bool(config and config.archive_id == entry.archive_id
                and config.endpoint_fingerprint == entry.archive_fingerprint
                and any(row.study_uid == entry.study_uid and row.archive_id == entry.archive_id
                        and row.endpoint_fingerprint == entry.archive_fingerprint for row in rows))


def conversion_entries(case_id, db):
    if not db.get(Case, case_id):
        fail('case_not_found', '病例不存在。', 404)
    return [entry for entry in load_index() if entry.case_id == case_id]


@router.get('/cases/{case_id}/conversions', dependencies=[Depends(no_store)])
def conversions(case_id: int, db: Session = Depends(get_db)):
    entries = conversion_entries(case_id, db)
    try:
        config = load_config()
    except HTTPException:
        config = None
    rows = db.query(PACSStudyLink).filter_by(case_id=case_id).all()
    return {'code': 200, 'data': {'state': 'registered' if entries else 'not_registered',
            'message': '转换版本独立于当前NIfTI；本地核对通过也需真实归档、来源和角色审核。' if entries
                       else '当前病例尚无登记的DICOM转换版本，现有NIfTI不受影响。',
            'model_input_eligible': False, 'current_mri_replaced': False,
            'items': [{'version_id': entry.version_id, 'study_uid': entry.study_uid,
                       'archive_id': entry.archive_id, 'report_sha256': entry.report_sha256,
                       'archive_binding_matches_config': conversion_context(entry, rows, config),
                       'original_byte_check_enabled': bool(config and config.allow_pixel_read
                           and config.expected_database_server_identifier and conversion_context(entry, rows, config)),
                       'integrity_status': 'not_rechecked', 'model_input_eligible': False} for entry in entries]}}


def web_plan_context(db, case_id, study_uid):
    db.expire_all()
    config = case_archive_config(db, case_id, study_uid)
    if not config.allow_pixel_read or not config.expected_database_server_identifier:
        fail('conversion_plan_source_disabled', '当前归档未启用受支持原文件读取，不能创建转换方案。', 409)
    return config


@router.post('/cases/{case_id}/conversion-plans/preview', dependencies=[Depends(no_store)])
def preview_web_conversion_plan(case_id: int, payload: dicom_web_plan.Preview,
                                identity: dict = Depends(require_doctor), db: Session = Depends(get_db)):
    verify = lambda: web_plan_context(db, case_id, payload.study_uid)
    try:
        return {'code': 200, 'data': dicom_web_plan.preview(case_id, payload, identity, verify(), verify)}
    except PlanError as error:
        fail(error.reason, str(error), 409)


@router.post('/cases/{case_id}/conversion-plans/jobs', dependencies=[Depends(no_store)])
def create_web_conversion_job(case_id: int, payload: dicom_web_plan.Create,
                               identity: dict = Depends(require_doctor), db: Session = Depends(get_db)):
    if not db.get(Case, case_id):
        fail('case_not_found', '病例不存在。', 404)
    try:
        record, _, _ = dicom_web_plan.read_draft(payload.draft_id, case_id, identity)
        verify = lambda: web_plan_context(db, case_id, record['study_uid'])
        return {'code': 200, 'data': dicom_web_plan.create(case_id, payload, identity, verify(), verify)}
    except PlanError as error:
        fail(error.reason, str(error), 404 if error.reason == 'conversion_plan_not_found' else 409)


class ConversionJobRetryRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_attempt: int = Field(ge=1, le=8)


@router.get('/cases/{case_id}/conversion-jobs', dependencies=[Depends(no_store)])
def conversion_jobs(case_id: int, db: Session = Depends(get_db)):
    conversion_entries(case_id, db)  # Also validates that the case exists.
    return {'code': 200, 'data': {'items': dicom_conversion_jobs.list_jobs(case_id)}}


@router.post('/cases/{case_id}/conversion-jobs/{job_id}/start', dependencies=[Depends(no_store)])
def start_conversion_job(case_id: int, job_id: str, payload: ConversionJobRetryRequest,
                         identity: dict = Depends(require_doctor), db: Session = Depends(get_db)):
    conversion_entries(case_id, db)
    try:
        row, plan = dicom_conversion_jobs.prepared_job(job_id, case_id, payload.expected_attempt)
        config = load_config()
        study_uids = {source['study_uid'] for source in plan['sources'].values()}
        links = db.query(PACSStudyLink).filter_by(case_id=case_id, archive_id=config.archive_id).all()
        if (plan['data_role'] != 'dicom-metadata-snapshot'
                or plan['archive_id'] != config.archive_id
                or plan['archive_fingerprint'] != config.endpoint_fingerprint
                or not config.allow_pixel_read or not config.expected_database_server_identifier
                or not any(link.study_uid in study_uids and link.endpoint_fingerprint == config.endpoint_fingerprint for link in links)):
            fail('conversion_archive_binding_unresolved', '准备作业与当前病例归档关联或读取配置不符，请重新核对来源。', 409)
        dicom_conversion_jobs.submit_job(job_id)
    except PlanError as error:
        fail(error.reason, str(error), 404 if error.reason == 'conversion_job_not_found' else 409)
    return {'code': 200, 'data': {**row, 'reviewer_authenticated': True,
            'professional_credential_verified': False, 'model_input_eligible': False,
            'current_mri_replaced': False, 'inference_performed': False}}


@router.post('/cases/{case_id}/conversion-jobs/{job_id}/retry', dependencies=[Depends(no_store)])
def retry_conversion_job(case_id: int, job_id: str,
                         payload: ConversionJobRetryRequest,
                         identity: dict = Depends(require_doctor), db: Session = Depends(get_db)):
    conversion_entries(case_id, db)
    try:
        row = dicom_conversion_jobs.retry_job(job_id, case_id, payload.expected_attempt)
    except PlanError as error:
        status_code = 404 if error.reason == 'conversion_job_not_found' else 409
        fail(error.reason, str(error), status_code)
    dicom_conversion_jobs.submit_job(job_id)
    return {'code': 200, 'data': {**row, 'reviewer_authenticated': True,
            'professional_credential_verified': False, 'model_input_eligible': False,
            'current_mri_replaced': False, 'inference_performed': False}}


@router.get('/cases/{case_id}/conversions/{version_id}/inspection', dependencies=[Depends(no_store)])
def conversion_inspection(case_id: int, version_id: str = ApiPath(pattern=r'^[a-zA-Z0-9_-]{1,64}$'),
                          db: Session = Depends(get_db)):
    entries = conversion_entries(case_id, db)
    entry = next((row for row in entries if row.version_id == version_id), None)
    if entry is None:
        fail('conversion_version_not_found', '当前病例没有该转换版本。', 404)
    try:
        config = load_config()
    except HTTPException:
        config = None
    links = db.query(PACSStudyLink).filter_by(case_id=case_id).all()
    if not conversion_context(entry, links, config):
        data = {'status': 'unavailable' if config is None else 'stale', 'reason': 'conversion_archive_binding_unresolved',
                'message': '当前归档配置或病例检查关联与转换来源不符，保留历史版本且不作为当前输入。'}
    else:
        data = inspect_entry(entry)
        try:
            after_config = load_config()
        except HTTPException:
            after_config = None
        db.expire_all()
        after_links = db.query(PACSStudyLink).filter_by(case_id=case_id).all()
        after_entry = next((row for row in conversion_entries(case_id, db) if row.version_id == version_id), None)
        if after_entry != entry or not conversion_context(entry, after_links, after_config):
            data = {'status': 'stale', 'reason': 'conversion_binding_changed_during_inspection',
                    'message': '核对窗口内版本登记、归档配置或病例检查关联改变；本次核对失效。'}
    return {'code': 200, 'data': {**data, 'version_id': version_id, 'model_input_eligible': False,
            'current_mri_replaced': False, 'live_archive_reconciled': False,
            'message': data.get('message', '本地文件核对通过；尚未核对当前真实归档和审核，不可提交AI。')}}


@router.get('/cases/{case_id}/conversions/{version_id}/source-check', dependencies=[Depends(no_store)])
def conversion_source_check(case_id: int, version_id: str = ApiPath(pattern=r'^[a-zA-Z0-9_-]{1,64}$'),
                            db: Session = Depends(get_db)):
    entry = next((row for row in conversion_entries(case_id,db) if row.version_id==version_id),None)
    if entry is None:
        fail('conversion_version_not_found','当前病例没有该转换版本。',404)
    try:
        config=load_config()
    except HTTPException:
        config=None
    links=db.query(PACSStudyLink).filter_by(case_id=case_id).all()
    if not conversion_context(entry,links,config):
        data={'status':'unavailable' if config is None else 'stale','reason':'conversion_archive_binding_unresolved',
              'message':'当前归档配置或病例检查关联与转换来源不符。','live_archive_reconciled':False}
    else:
        data=check_archive_entry(entry,config)
        try:
            after_config=load_config()
        except HTTPException:
            after_config=None
        db.expire_all()
        after_links=db.query(PACSStudyLink).filter_by(case_id=case_id).all()
        after_entry=next((row for row in conversion_entries(case_id,db) if row.version_id==version_id),None)
        if after_entry!=entry or not conversion_context(entry,after_links,after_config):
            data={'status':'stale','reason':'conversion_binding_changed_during_inspection',
                  'message':'核对窗口内版本登记、归档配置或病例关联改变。','live_archive_reconciled':False}
    return {'code':200,'data':{**data,'version_id':version_id,'model_input_eligible':False,
            'current_mri_replaced':False,'reviewer_authenticated':False}}


class ConversionRoleReview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['approve', 'reject']
    plan_revision: str = Field(pattern=r'^[0-9a-f]{64}$')
    assignment_set_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    confirm_roles: Literal[True]


@router.get('/cases/{case_id}/conversions/{version_id}/role-review', dependencies=[Depends(no_store)])
def conversion_role_review(case_id: int, version_id: str = ApiPath(pattern=r'^[a-zA-Z0-9_-]{1,64}$'), db: Session = Depends(get_db)):
    entry = next((row for row in conversion_entries(case_id, db) if row.version_id == version_id), None)
    if entry is None: fail('conversion_version_not_found', '当前病例没有该转换版本。', 404)
    view = dicom_role_review.describe(entry)
    return {'code': 200, 'data': {**view, 'history': dicom_role_review.history(entry)}}


@router.post('/cases/{case_id}/conversions/{version_id}/role-review', dependencies=[Depends(no_store)])
def submit_conversion_role_review(case_id: int, version_id: str, payload: ConversionRoleReview,
                                  identity: dict = Depends(require_doctor), db: Session = Depends(get_db)):
    entry = next((row for row in conversion_entries(case_id, db) if row.version_id == version_id), None)
    if entry is None: fail('conversion_version_not_found', '当前病例没有该转换版本。', 404)
    try: config = load_config()
    except HTTPException: config = None
    before = db.query(PACSStudyLink).filter_by(case_id=case_id).all()
    if not conversion_context(entry, before, config): fail('conversion_archive_binding_unresolved', '转换来源与当前病例关联或归档配置不符。', 409)
    view = dicom_role_review.describe(entry)
    if payload.plan_revision != view['plan_revision'] or payload.assignment_set_sha256 != view['assignment_set_sha256']:
        fail('conversion_role_review_stale', '角色声明或转换版本已变化，请重新打开并核对。', 409)
    local = inspect_entry(entry)
    if local.get('status') != 'verified_readonly': fail('conversion_local_integrity_required', '转换版本本地完整性未通过，不能登记角色决定。', 409)
    source = None
    if payload.decision == 'approve':
        if not view['review_allowed']: fail('synthetic_conversion_not_reviewable', '合成工程夹具不能取得真实DICOM角色审批。', 409)
        source = check_archive_entry(entry, config)
        if source.get('status') != 'matched_at_check' or source.get('data_role') != 'dicom-metadata-snapshot' or source.get('plan_revision') != payload.plan_revision or source.get('report_sha256') != entry.report_sha256 or source.get('archive_id') != entry.archive_id or source.get('archive_fingerprint') != entry.archive_fingerprint:
            fail('conversion_archive_review_required', '当前归档原字节或序列元数据未完整匹配，角色审批未保存。', 409)
    db.expire_all()
    try: config_after = load_config()
    except HTTPException: config_after = None
    after = db.query(PACSStudyLink).filter_by(case_id=case_id).all()
    current = next((row for row in conversion_entries(case_id, db) if row.version_id == version_id), None)
    if current != entry or not conversion_context(entry, after, config_after): fail('conversion_role_review_stale', '审核期间转换登记、病例关联或归档配置发生变化；未保存决定。', 409)
    saved = dicom_role_review.record(entry, payload.decision, payload.plan_revision, payload.assignment_set_sha256, identity, source)
    return {'code': 200, 'data': {**saved, 'reviewer_authenticated': True,
        'review_status': 'approved' if payload.decision == 'approve' else 'rejected',
        'professional_credential_verified': False, 'model_input_eligible': False, 'current_mri_replaced': False}}




class ConversionActivation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    plan_revision: str = Field(pattern=r'^[0-9a-f]{64}$')
    assignment_set_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    confirm_activation: Literal[True]


def _latest_conversion_approval(entry, view):
    rows = dicom_role_review.history(entry)
    binding = {'version_id': entry.version_id, 'report_sha256': entry.report_sha256,
               'proposal_sha256': entry.proposal_sha256, 'snapshots_sha256': entry.snapshots_sha256}
    if not rows or rows[-1].get('decision') != 'approve' or rows[-1].get('binding') != binding:
        fail('conversion_role_approval_required', '此转换版本没有最新且有效的本地医生角色确认。', 409)
    row = rows[-1]
    if (row.get('plan_revision') != view['plan_revision']
            or row.get('assignment_set_sha256') != view['assignment_set_sha256']
            or row.get('reviewer', {}).get('role') != 'doctor'
            or row.get('reviewer', {}).get('professional_credential_verified') is not False
            or row.get('source_check', {}).get('status') != 'matched_at_check'):
        fail('conversion_role_approval_stale', '审核未绑定当前来源/角色版本或归档原字节回执。', 409)
    return row


def _activation_paths(entry, local):
    from pathlib import Path
    from app.services.dicom_input_plan import ROLES
    root = Path(entry.version_dir).resolve(strict=True)
    if not is_supported_storage_path(root) or not root.is_dir():
        fail('conversion_directory_unavailable', '转换版本不在受支持的E盘目录。', 409)
    outputs = local.get('outputs')
    if local.get('status') != 'verified_readonly' or not isinstance(outputs, dict) or set(outputs) != set(ROLES):
        fail('conversion_local_integrity_required', '转换版本或四序列输出完整性未通过，不能激活。', 409)
    paths = {}
    for role in ROLES:
        path = (root / (role + '.nii.gz')).resolve(strict=True)
        if path.parent != root or not is_supported_storage_path(path) or not path.is_file():
            fail('conversion_output_scope_invalid', '四序列转换文件不在版本目录内，不能激活。', 409)
        paths[role] = str(path)
    return paths


def _reject_engineering_resampling_activation(plan):
    """Resampling is approved for geometry/conversion acceptance only, not model input."""
    if plan.get('resampling') is not None:
        fail('resampled_model_input_not_released',
             '此重采样配置目前仅用于影像工程验收；完成模型预处理验证前不能激活或推理。', 409)


@router.post('/cases/{case_id}/conversions/{version_id}/activate-model-input', dependencies=[Depends(no_store)])
def activate_conversion_model_input(case_id: int, version_id: str = ApiPath(pattern=r'^[a-zA-Z0-9_-]{1,64}$'),
                                    payload: ConversionActivation = ..., identity: dict = Depends(require_doctor),
                                    db: Session = Depends(get_db)):
    """Make only a fully rechecked, approved conversion the current MRI; never runs inference."""
    from datetime import datetime, timezone
    from uuid import uuid4
    from pathlib import Path
    from app.models.analysis_run import AnalysisRun
    from app.models.mri import MRI
    from app.services.analysis_jobs import submission_lock
    from app.services.mri_preview_service import generate_mri_previews
    from app.services.study_validation import MODEL_INPUT_CONTRACT_ID, validate_sequences
    from app.core.storage import upload_root

    entry = next((row for row in conversion_entries(case_id, db) if row.version_id == version_id), None)
    if entry is None: fail('conversion_version_not_found', '当前病例没有该转换版本。', 404)
    if entry.case_id != case_id: fail('conversion_case_mismatch', '转换版本不属于当前病例。', 409)
    try: config = load_config()
    except HTTPException: config = None
    links = db.query(PACSStudyLink).filter_by(case_id=case_id).all()
    if not conversion_context(entry, links, config):
        fail('conversion_archive_binding_unresolved', '转换版本与当前病例关联或本机归档配置不符。', 409)
    view = dicom_role_review.describe(entry)
    if payload.plan_revision != view['plan_revision'] or payload.assignment_set_sha256 != view['assignment_set_sha256']:
        fail('conversion_role_review_stale', '角色声明或转换版本已变化，请重新核对。', 409)
    if not view.get('review_allowed') or view.get('data_role') != 'dicom-metadata-snapshot':
        fail('synthetic_conversion_not_activatable', '合成工程夹具或非归档来源版本不可激活。', 409)
    _latest_conversion_approval(entry, view)
    local = inspect_entry(entry)
    paths = _activation_paths(entry, local)
    try:
        validate_sequences(paths)
    except Exception as error:
        fail('conversion_model_geometry_invalid', '四序列NIfTI不满足现有模型空间契约；未自动重采样。', 409)
    try:
        proposal, snapshots = entry_inputs(entry)
        from app.services.dicom_input_plan import validate_plan
        plan = validate_plan(proposal, snapshots)
    except Exception:
        fail('conversion_source_plan_invalid', '转换版本当前角色规划/来源无法重新核对。', 409)
    _reject_engineering_resampling_activation(plan)
    if (plan['model_input_contract'] != MODEL_INPUT_CONTRACT_ID
            or set(plan['sources']) != {'t1c', 't1n', 't2w', 't2f'}):
        fail('conversion_model_contract_mismatch', '转换版本与当前模型输入契约不一致。', 409)

    activation_id = uuid4().hex
    preview_root = (upload_root() / f'case_{case_id}' / ('dicom_activation_' + activation_id)).resolve()
    upload_base = upload_root().resolve()
    if not is_supported_storage_path(preview_root) or preview_root == upload_base or upload_base not in preview_root.parents:
        fail('activation_storage_scope_invalid', '预览文件路径超出E盘病例目录。', 503)
    preview_root.mkdir(parents=True, exist_ok=False)
    committed = False
    try:
        preview_paths = generate_mri_previews(Path(paths['t2f']), preview_root / 'previews', 0)
        # Keep the same process-local lock as analysis submissions and NIfTI replacement.
        with submission_lock:
            db.expire_all()
            case = db.get(Case, case_id)
            if case is None: fail('case_not_found', '病例不存在。', 404)
            current_entry = next((row for row in conversion_entries(case_id, db) if row.version_id == version_id), None)
            try: config_now = load_config()
            except HTTPException: config_now = None
            current_links = db.query(PACSStudyLink).filter_by(case_id=case_id).all()
            if current_entry != entry or not conversion_context(entry, current_links, config_now):
                fail('conversion_binding_changed', '激活期间版本、病例关联或归档配置发生变化。', 409)
            # The archive observation is deliberately repeated while submissions are excluded.
            source = check_archive_entry(entry, config_now)
            if (source.get('status') != 'matched_at_check' or source.get('data_role') != 'dicom-metadata-snapshot'
                    or source.get('plan_revision') != view['plan_revision']
                    or source.get('report_sha256') != entry.report_sha256
                    or source.get('archive_id') != entry.archive_id
                    or source.get('archive_fingerprint') != entry.archive_fingerprint
                    or source.get('raw_byte_passes') != 2
                    or source.get('live_archive_reconciled') is not True):
                fail('conversion_archive_recheck_required', '当前归档实例原字节未在激活窗口再次完整匹配。', 409)
            # Revalidate local outputs before taking SQLite's write lock.
            db.expire_all()
            final_entry = next((row for row in conversion_entries(case_id, db) if row.version_id == version_id), None)
            if final_entry != entry or inspect_entry(entry).get('status') != 'verified_readonly':
                fail('conversion_changed_during_activation', '来源或转换产物在激活核对窗口发生变化。', 409)
            db.rollback()
            db.connection().exec_driver_sql('BEGIN IMMEDIATE')
            db.expire_all()
            case = db.get(Case, case_id)
            if case is None: fail('case_not_found', '病例不存在。', 404)
            if db.query(AnalysisRun).filter(AnalysisRun.case_id == case_id,
                    AnalysisRun.state.in_(['queued', 'running'])).first():
                fail('analysis_active', '病例存在排队或运行中的AI分析；完成后再切换模型输入。', 409)
            final_entry = next((row for row in conversion_entries(case_id, db) if row.version_id == version_id), None)
            if final_entry != entry:
                fail('conversion_binding_changed', '最终提交前转换版本登记发生变化。', 409)
            with dicom_role_review.journal_lock():
                latest_review = _latest_conversion_approval(entry, view)
                if latest_review.get('decision') != 'approve':
                    fail('conversion_role_approval_required', '未找到当前有效审核决定。', 409)
                # Ensure the plan digest is still bound to exactly the files presented for conversion.
                final_view = dicom_role_review.describe(entry)
                if final_view['plan_revision'] != view['plan_revision'] or final_view['assignment_set_sha256'] != view['assignment_set_sha256']:
                    fail('conversion_role_review_stale', '最终提交前角色规划发生变化。', 409)
                mri = MRI(case_id=case_id, filename=f'DICOM conversion {version_id}', filepath=paths['t2f'],
                          web_path=None, slice_path=str(preview_paths[0]), processed_path=None, preview_error=None,
                          modality='MRI', status='preview_ready', doctor_verified=False, segmentation_source='unavailable',
                          sequences_json=json.dumps(paths, ensure_ascii=False, sort_keys=True), segmentation_path=None,
                          analysis_run_id=None, verified_run_id=None, input_source='dicom-conversion')
                source_rows = {role: {'study_uid': plan['sources'][role]['study_uid'],
                                      'series_uid': plan['sources'][role]['series_uid'],
                                      'frame_of_reference_uid': plan['sources'][role]['frame_of_reference_uid'],
                                      'series_metadata_sha256': plan['sources'][role]['series_metadata_sha256'],
                                      'nifti_sha256': local['outputs'][role]['nifti_sha256']}
                               for role in ('t1c', 't1n', 't2w', 't2f')}
                provenance = {'format':'dicom-mri-input-lineage-v1','activation_id':activation_id,
                    'conversion_version_id':entry.version_id,'report_sha256':entry.report_sha256,
                    'proposal_sha256':entry.proposal_sha256,'snapshots_sha256':entry.snapshots_sha256,
                    'plan_revision':view['plan_revision'],'assignment_set_sha256':view['assignment_set_sha256'],
                    'model_input_contract':MODEL_INPUT_CONTRACT_ID,'archive_id':entry.archive_id,
                    'archive_fingerprint':entry.archive_fingerprint,'study_uid':entry.study_uid,
                    'roles':source_rows,'role_review_id':latest_review['review_id'],
                    'reviewer':latest_review['reviewer'],'activated_by':identity,
                    'activation_source_check':{key:source.get(key) for key in
                        ('status','completed_utc','instances_checked','roles_checked','raw_byte_passes','total_raw_bytes_observed')},
                    'converter':json.loads(Path(entry.version_dir, 'conversion-report.json').read_text(encoding='utf-8')).get('converter'),
                    'activated_utc':datetime.now(timezone.utc).isoformat(),
                    'inference_performed':False,'original_dicom_modified':False}
                mri.source_provenance_json = json.dumps(provenance, ensure_ascii=False, sort_keys=True, allow_nan=False)
                db.add(mri); db.flush()
                file_stat = Path(paths['t2f']).stat()
                mri.web_path = f'/mri/{case_id}/nifti?mri_id={mri.id}&revision={file_stat.st_size}-{file_stat.st_mtime_ns}'
                previous = db.query(MRI).filter(MRI.case_id == case_id, MRI.id != mri.id).order_by(MRI.id.desc()).first()
                if previous is not None:
                    from app.models.annotation import MRIAnnotation
                    db.query(MRIAnnotation).filter_by(mri_id=previous.id).update({'coordinate_contract':'obsolete-input'})
                case.status, case.mri_path = 'uploaded', mri.filepath
                db.commit()
                committed = True
                return {'code':200,'data':{'mri_id':mri.id,'status':mri.status,'input_source':mri.input_source,
                    'conversion_version_id':entry.version_id,'plan_revision':view['plan_revision'],
                    'model_input_eligible':True,'current_mri_replaced':True,'inference_performed':False,
                    'original_dicom_modified':False,'previous_mri_and_analysis_history_preserved':True,
                    'annotations_marked_obsolete':previous is not None}}
    except Exception as error:
        db.rollback()
        if isinstance(error, HTTPException): raise
        raise HTTPException(422, 'DICOM模型输入激活失败；现有当前MRI保持不变。') from error
    finally:
        if not committed and preview_root.exists():
            preview_root.resolve().relative_to(upload_base)
            import shutil
            shutil.rmtree(preview_root)


class LinkCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    study_uid: str
    acknowledge_case_match: Literal[True]


def case_archive_config(db,case_id,study_uid):
    validate_uid(study_uid)
    if not db.get(Case,case_id):
        fail('case_not_found','病例不存在。',404)
    config=load_config()
    link=db.query(PACSStudyLink).filter_by(case_id=case_id,archive_id=config.archive_id,study_uid=study_uid).first()
    if not link or link.endpoint_fingerprint!=config.endpoint_fingerprint:
        fail('case_archive_link_required','检查尚未与当前病例和归档配置核对关联。',409)
    return config


def measurement_source(db, case_id, study_uid, series_uid):
    validate_uid(series_uid)
    config = case_archive_config(db, case_id, study_uid)
    if not config.allow_pixel_read or not config.expected_database_server_identifier:
        fail('dicom_measurement_unavailable', 'DICOM测量需要已核对的本机归档与像素读取授权。', 409)
    link = db.query(PACSStudyLink).filter_by(case_id=case_id, archive_id=config.archive_id, study_uid=study_uid).one()
    before = (link.id, link.endpoint_fingerprint)
    with ReconciliationClient(config) as archive:
        manifest = series_manifest(archive, study_uid, series_uid)
    db.expire_all()
    current_config = case_archive_config(db, case_id, study_uid)
    link = db.query(PACSStudyLink).filter_by(case_id=case_id, archive_id=current_config.archive_id, study_uid=study_uid).one()
    if (before != (link.id, link.endpoint_fingerprint) or current_config.endpoint_fingerprint != config.endpoint_fingerprint
            or not current_config.allow_pixel_read):
        fail('dicom_measurement_source_changed', '核对期间归档配置或病例关联改变，请重新打开序列。', 409)
    return dicom_measurements.context_for(manifest, link), manifest['geometry']


@router.get('/cases/{case_id}/studies/{study_uid}/series/{series_uid}/measurements', dependencies=[Depends(no_store)])
def list_dicom_measurements(case_id: int, study_uid: str, series_uid: str, db: Session=Depends(get_db)):
    context, _ = measurement_source(db, case_id, study_uid, series_uid)
    return {'code': 200, 'data': dicom_measurements.list_items(db, case_id, context)}


def checked_reading_report(db, case_id, study_uid, series_uid):
    context, geometry = measurement_source(db, case_id, study_uid, series_uid)
    data = dicom_report.snapshot(db, case_id, context, geometry)
    # A changed link/archive or an edit committed while reading cannot become a
    # mixed report. Exporters compare this content revision before and after render.
    after_context, _ = measurement_source(db, case_id, study_uid, series_uid)
    db.expire_all()
    after = dicom_report.snapshot(db, case_id, after_context, geometry)
    if context != after_context or data['content_sha256'] != after['content_sha256']:
        fail('dicom_report_changed', '核对期间来源、测量或病例意见改变，请刷新阅片记录。', 409)
    return data


@router.get('/cases/{case_id}/studies/{study_uid}/series/{series_uid}/reading-report', dependencies=[Depends(no_store)])
def dicom_reading_report(case_id: int, study_uid: str, series_uid: str, db: Session=Depends(get_db)):
    data = checked_reading_report(db, case_id, study_uid, series_uid)
    return {'code': 200, 'data': dicom_review.attach(db, case_id, data)}


@router.get('/cases/{case_id}/studies/{study_uid}/series/{series_uid}/reviews', dependencies=[Depends(no_store)])
def dicom_review_history(case_id: int, study_uid: str, series_uid: str,
                         limit: int = Query(20, ge=1, le=50), offset: int = Query(0, ge=0),
                         db: Session=Depends(get_db)):
    data = checked_reading_report(db, case_id, study_uid, series_uid)
    return {'code': 200, 'data': dicom_review.history(db, case_id, data, limit, offset)}


@router.post('/cases/{case_id}/studies/{study_uid}/series/{series_uid}/reviews', dependencies=[Depends(no_store)])
def save_dicom_review(case_id: int, study_uid: str, series_uid: str,
                       payload: dicom_review.Create, identity: dict=Depends(require_doctor), db: Session=Depends(get_db)):
    # SQLite write ownership prevents a measurement/opinion edit from committing
    # between the final local snapshot check and recording its review.
    db.rollback()
    db.connection().exec_driver_sql('BEGIN IMMEDIATE')
    data = checked_reading_report(db, case_id, study_uid, series_uid)
    return {'code': 200, 'data': dicom_review.save(db, case_id, data, payload, identity)}


@router.get('/cases/{case_id}/studies/{study_uid}/series/{series_uid}/view-state', dependencies=[Depends(no_store)])
def latest_dicom_view_state(case_id: int, study_uid: str, series_uid: str, db: Session=Depends(get_db)):
    context, _ = measurement_source(db, case_id, study_uid, series_uid)
    return {'code': 200, 'data': dicom_view_state.latest(db, case_id, context)}


@router.post('/cases/{case_id}/studies/{study_uid}/series/{series_uid}/view-state', dependencies=[Depends(no_store)])
def save_dicom_view_state(case_id: int, study_uid: str, series_uid: str, payload: dicom_view_state.Create, db: Session=Depends(get_db)):
    context, _ = measurement_source(db, case_id, study_uid, series_uid)
    return {'code': 200, 'data': dicom_view_state.save(db, case_id, context, payload)}


@router.post('/cases/{case_id}/studies/{study_uid}/series/{series_uid}/measurements', dependencies=[Depends(no_store)])
def save_dicom_measurement(case_id: int, study_uid: str, series_uid: str, payload: dicom_measurements.Create, db: Session=Depends(get_db)):
    context, geometry = measurement_source(db, case_id, study_uid, series_uid)
    return {'code': 200, 'data': dicom_measurements.save(db, case_id, context, geometry, payload)}


@router.delete('/cases/{case_id}/studies/{study_uid}/series/{series_uid}/measurements/{item_id}', dependencies=[Depends(no_store)])
def delete_dicom_measurement(case_id: int, study_uid: str, series_uid: str, item_id: int, payload: dicom_measurements.Delete, db: Session=Depends(get_db)):
    context, _ = measurement_source(db, case_id, study_uid, series_uid)
    return {'code': 200, 'data': dicom_measurements.remove(db, case_id, item_id, context, payload)}


@router.get('/cases/{case_id}/studies/{study_uid}/series/{series_uid}/view-manifest',dependencies=[Depends(no_store)])
def case_view_manifest(case_id:int,study_uid:str,series_uid:str,db:Session=Depends(get_db)):
    validate_uid(series_uid)
    config=case_archive_config(db,case_id,study_uid)
    with ReconciliationClient(config) as archive:
        manifest=series_manifest(archive,study_uid,series_uid)
    for row in manifest['instances']:
        row['metadata']['7FE00010']['BulkDataURI']=(
            f'/pacs/cases/{case_id}/studies/{study_uid}/series/{series_uid}/instances/{row["instance_uid"]}/frames/1'
            f'?metadata_sha256={row["metadata_sha256"]}&archive_fingerprint={config.endpoint_fingerprint}')
    manifest.update(source_case_id=case_id,transport_enabled=True,
                    saved_dicom_annotations_available=bool(config.allow_pixel_read and config.expected_database_server_identifier),
                    dicom_view_state_available=bool(config.allow_pixel_read and config.expected_database_server_identifier),segmentation_overlay_available=False)
    return {'code':200,'data':manifest}


@router.get('/cases/{case_id}/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}/frames/{frame_number}')
def case_frame(case_id:int,study_uid:str,series_uid:str,instance_uid:str,
               frame_number:int=ApiPath(ge=1,le=1),
               metadata_sha256:str=Query(pattern=r'^[0-9a-f]{64}$'),
               archive_fingerprint:str=Query(pattern=r'^[0-9a-f]{64}$'),
               db:Session=Depends(get_db)):
    validate_uid(series_uid);validate_uid(instance_uid)
    config=case_archive_config(db,case_id,study_uid)
    if config.endpoint_fingerprint!=archive_fingerprint:
        fail('archive_revision_mismatch','归档配置版本已变化，请重新打开DICOM序列。',409)
    with ReconciliationClient(config) as archive:
        item,expected=checked_metadata(archive,study_uid,series_uid,instance_uid)
        if metadata_revision(item)!=metadata_sha256:
            fail('instance_revision_mismatch','实例元数据版本已变化，拒绝沿用旧空间读取像素。',409)
        pixels=frame_bytes(archive,study_uid,series_uid,instance_uid,expected)
    body,content_type=multipart_response(pixels)
    return Response(body,media_type=content_type,headers={'Cache-Control':'no-store'})


@router.post('/cases/{case_id}/links', dependencies=[Depends(no_store)])
def create_link(case_id: int, payload: LinkCreate, db: Session = Depends(get_db)):
    validate_uid(payload.study_uid)
    if not db.get(Case, case_id):
        fail('case_not_found', '病例不存在。', 404)
    with PacsClient() as archive:
        items = archive.query('studies', study_uid=payload.study_uid, limit=2)
        if len(items) != 1:
            fail('study_not_found', '归档中未找到唯一的指定检查，未建立关联。', 404)
        config = archive.config
    def existing_result(row):
        if row.case_id != case_id or row.endpoint_fingerprint != config.endpoint_fingerprint:
            fail('mapping_conflict', '该检查已关联其他病例或归档地址已改变，拒绝覆盖原关联。', 409)
        return {'code': 200, 'data': link_result(row, config)}
    existing = db.query(PACSStudyLink).filter_by(archive_id=config.archive_id, study_uid=payload.study_uid).first()
    if existing:
        return existing_result(existing)
    row = PACSStudyLink(case_id=case_id, archive_id=config.archive_id,
                       endpoint_fingerprint=config.endpoint_fingerprint, study_uid=payload.study_uid,
                       metadata_json=json.dumps(items[0], sort_keys=True),
                       metadata_sha256=hashlib.sha256(json.dumps(items[0], sort_keys=True).encode()).hexdigest())
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(PACSStudyLink).filter_by(archive_id=config.archive_id, study_uid=payload.study_uid).first()
        if existing:
            return existing_result(existing)
        raise
    db.refresh(row)
    return {'code': 200, 'data': link_result(row, config)}


