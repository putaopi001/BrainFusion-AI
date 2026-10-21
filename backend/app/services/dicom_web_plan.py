"""Case-bound four-series drafts and original capture, never approval or AI activation."""
import hashlib
import json
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from fastapi import HTTPException
from pydantic import Field, StrictBool, field_validator

from app.services import dicom_conversion_jobs as jobs
from app.services.dicom_conversion import source_dataset, MAX_FILE_BYTES
from app.services.dicom_conversion_source import BudgetClient
from app.services.dicom_input_plan import StrictModel, ROLE_SIGNALS, ROLES, digest, validate_plan, fail
from app.services.dicom_series import series_manifest
from app.services.pacs_client import validate_uid

MAX_CAPTURE_BYTES = 256 * 1024 * 1024
MAX_SECONDS = 120
DRAFT_SECONDS = 3600


class Choice(StrictModel):
    role: Literal['t1c', 't1n', 't2w', 't2f']
    series_uid: str

    @field_validator('series_uid')
    @classmethod
    def uid(cls, value):
        try:
            return validate_uid(value)
        except HTTPException:
            raise ValueError('Invalid DICOM UID') from None


class Preview(StrictModel):
    study_uid: str
    assignments: list[Choice] = Field(min_length=4, max_length=4)
    evidence_basis: Literal['acquisition_record', 'published_protocol', 'local_manual_review']
    evidence_text: str = Field(min_length=8, max_length=128, pattern=r'^[a-zA-Z0-9_.:-]+$')
    resample_to_t1c_1mm: StrictBool = False

    @field_validator('study_uid')
    @classmethod
    def uid(cls, value):
        return Choice.uid(value)

    @field_validator('evidence_text')
    @classmethod
    def useful_text(cls, value):
        value = value.strip()
        if len(value) < 8 or len(value) > 128 or not all(ch.isalnum() or ch in '_.:-' for ch in value):
            raise ValueError('Describe the acquisition/protocol evidence')
        return value


class Create(StrictModel):
    draft_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    plan_revision: str = Field(pattern=r'^[a-f0-9]{64}$')
    acknowledge_roles: Literal[True]


def _root(create=False):
    root = jobs._root().parent / 'dicom-conversion-plans'
    if root.resolve() != root:
        fail('conversion_plan_path_invalid', '转换方案目录不符合运行配置。')
    if create:
        root.mkdir(exist_ok=True)
    return root


def _write(path, value):
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, allow_nan=False, indent=2)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_snapshot(archive, case_id, study_uid, series_uid):
    item = series_manifest(archive, study_uid, series_uid)
    item.update(source_case_id=case_id, archive_id=archive.config.archive_id,
                archive_fingerprint=archive.config.endpoint_fingerprint)
    return item


def _same_context(config, verify_context):
    current = verify_context()
    if (current.archive_id != config.archive_id or current.endpoint_fingerprint != config.endpoint_fingerprint
            or not current.allow_pixel_read or not current.expected_database_server_identifier):
        fail('conversion_plan_context_changed', '方案准备期间归档配置或病例关联改变，请重新核对。')


def preview(case_id, selection, identity, config, verify_context):
    choices = {item.role: item.series_uid for item in selection.assignments}
    if set(choices) != set(ROLES) or len(set(choices.values())) != 4:
        fail('four_distinct_roles_required', '必须明确选择四个不同序列，各对应一个模型角色。')
    _same_context(config, verify_context)
    stamp = datetime.now(timezone.utc).isoformat()
    draft_id = uuid.uuid4().hex
    evidence = {'basis': selection.evidence_basis, 'reference': selection.evidence_text,
                'creator_id': identity['id'], 'confirmed_at': stamp,
                'study_uid': selection.study_uid, 'choices': choices}
    snapshots, assignments = [], []
    try:
        with BudgetClient(config, time.monotonic() + MAX_SECONDS) as archive:
            for role in ROLES:
                item = _source_snapshot(archive, case_id, selection.study_uid, choices[role])
                snapshots.append(item)
                weighting, phase, attenuated = ROLE_SIGNALS[role]
                assignments.append({'role': role, 'study_uid': selection.study_uid,
                    'series_uid': choices[role], 'series_metadata_sha256': item['metadata_sha256'],
                    'evidence': {'weighting': weighting, 'contrast_phase': phase,
                        'fluid_attenuated': attenuated, 'basis': selection.evidence_basis,
                        'evidence_sha256': digest(evidence), 'evidence_reference': 'web-plan.' + draft_id,
                        'reviewer_reference': identity['id'], 'confirmed_at': stamp}})
            archive._check_system(archive._json('/system', dicom=False))
        proposal = {'format': 'dicom-model-input-proposal-v1', 'case_id': case_id,
            'archive_id': config.archive_id, 'archive_fingerprint': config.endpoint_fingerprint,
            'data_role': 'dicom-metadata-snapshot', 'assignments': assignments}
        if selection.resample_to_t1c_1mm:
            proposal['resampling'] = {'format':'dicom-model-resampling-policy-v1',
                'reference_role':'t1c','target_spacing_xyz_mm':[1.0,1.0,1.0],
                'interpolation':'linear','coordinate_mapping':'same_frame_of_reference_identity',
                'outside_value':0.0}
        bundle = {'format': 'dicom-series-snapshot-bundle-v1',
                  'data_role': proposal['data_role'], 'series': snapshots}
        plan = validate_plan(proposal, bundle)
        _same_context(config, verify_context)
    except httpx.HTTPError:
        fail('conversion_plan_archive_unavailable', '归档读取中断，未生成转换方案，请稍后重试。')
    root = _root(create=True)
    if len([p for p in root.glob('*/draft.json') if p.parent.name not in {'.prepare-' + draft_id}]) >= 128:
        fail('conversion_plan_limit', '已保存的转换方案数量达到本机上限，请先整理历史方案。')
    staging = root / ('.prepare-' + draft_id)
    staging.mkdir()
    try:
        for name, value in (('proposal.json', proposal), ('snapshots.json', bundle), ('evidence.json', evidence)):
            _write(staging / name, value)
        record = {'format': 'dicom-web-plan-v1', 'draft_id': draft_id, 'case_id': case_id,
            'study_uid': selection.study_uid, 'creator_id': identity['id'], 'created_utc': stamp,
            'expires_at': time.time() + DRAFT_SECONDS, 'plan_revision': plan['plan_revision'],
            'hashes': {name: _sha(staging / name) for name in ('proposal.json', 'snapshots.json', 'evidence.json')}}
        _write(staging / 'draft.json', record)
        staging.rename(root / draft_id)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    geometry = plan['target_grid'] or plan['sources'][ROLES[0]]['geometry']
    return {'draft_id': draft_id, 'plan_revision': plan['plan_revision'],
        'study_uid': selection.study_uid, 'expires_at': record['expires_at'],
        'dimensions': geometry['dimensions'], 'spacing_xyz_mm': geometry['spacing_xyz_mm'],
        'resampling_applied': bool(plan['resampling']), 'resampling': plan['resampling'],
        'source_geometries': {role:{'dimensions':plan['sources'][role]['geometry']['dimensions'],
            'spacing_xyz_mm':plan['sources'][role]['geometry']['spacing_xyz_mm'],
            'origin_lps_mm':plan['sources'][role]['geometry']['origin_lps_mm'],
            'frame_of_reference_uid':plan['sources'][role]['frame_of_reference_uid']} for role in ROLES},
        'assignments': [{'role': role, 'series_uid': choices[role],
            'instance_count': len(plan['sources'][role]['instances'])} for role in ROLES],
        'metadata_geometry_contract_passed': True, 'source_bytes_captured': False,
        'role_review_completed': False, 'model_input_eligible': False, 'current_mri_replaced': False,
        'inference_performed': False}


def read_draft(draft_id, case_id, identity):
    if not jobs.JOB_ID.fullmatch(draft_id):
        fail('conversion_plan_not_found', '转换方案不存在。')
    root = _root()
    folder = root / draft_id
    try:
        if folder.resolve(strict=True).parent != root.resolve(strict=True):
            fail('conversion_plan_invalid', '转换方案范围无效。')
        record, _ = jobs.read(folder / 'draft.json', 128*1024)
        if (record.get('format') != 'dicom-web-plan-v1' or record.get('draft_id') != draft_id
                or record.get('case_id') != case_id or record.get('creator_id') != identity['id']):
            fail('conversion_plan_not_found', '当前病例或账户没有该转换方案。')
        if type(record.get('expires_at')) not in (int, float) or time.time() >= record['expires_at']:
            fail('conversion_plan_expired', '转换方案已过期，请重新检查四序列。')
        values = {}
        for name, cap in (('proposal.json', 4*1024*1024), ('snapshots.json', 16*1024*1024), ('evidence.json', 128*1024)):
            value, sha = jobs.read(folder / name, cap)
            if sha != record['hashes'][name]:
                fail('conversion_plan_changed', '保存的方案已改变，请重新检查四序列。')
            values[name] = value
        plan = validate_plan(values['proposal.json'], values['snapshots.json'])
        if plan['plan_revision'] != record['plan_revision'] or plan['case_id'] != case_id:
            fail('conversion_plan_changed', '方案版本已改变，请重新检查四序列。')
        return record, folder, plan
    except FileNotFoundError:
        fail('conversion_plan_not_found', '转换方案不存在或来源文件缺失。')
    except (OSError, KeyError, TypeError):
        fail('conversion_plan_invalid', '转换方案不可读取，请重新检查四序列。')


def _check_manifests(archive, case_id, plan):
    for source in plan['sources'].values():
        current = _source_snapshot(archive, case_id, source['study_uid'], source['series_uid'])
        if current['metadata_sha256'] != source['series_metadata_sha256']:
            fail('conversion_plan_source_changed', '归档序列在预览后发生变化，未创建转换任务。')


def create(case_id, payload, identity, config, verify_context):
    record, folder, plan = read_draft(payload.draft_id, case_id, identity)
    if payload.plan_revision != record['plan_revision']:
        fail('conversion_plan_stale', '提交的方案版本已过时，请重新预览。')
    if config.archive_id != plan['archive_id'] or config.endpoint_fingerprint != plan['archive_fingerprint']:
        fail('conversion_plan_context_changed', '方案与当前归档配置不符，请重新预览。')
    _same_context(config, verify_context)
    with jobs._file_lock(folder / 'create.lock', blocking=False) as acquired:
        if not acquired:
            fail('conversion_plan_busy', '该方案正在创建任务，请稍后刷新作业列表。')
        job_id = payload.draft_id
        if (jobs._root() / job_id / 'job.json').exists():
            row = jobs._read_job(job_id)
            if (row['case_id'] != case_id or row['inputs']['proposal']['sha256'] != record['hashes']['proposal.json']
                    or row['inputs']['snapshots']['sha256'] != record['hashes']['snapshots.json']):
                fail('conversion_plan_changed', '已有任务与该方案不一致，未创建重复任务。')
            return {**jobs._public(row), 'already_created': True}
        if shutil.disk_usage(folder).free < MAX_CAPTURE_BYTES * 2:
            fail('conversion_plan_disk_budget', '转换方案存储空间不足，未读取原文件。')
        capture = folder / ('capture-' + uuid.uuid4().hex[:12])
        capture.mkdir()
        files, total = {}, 0
        job_created = False
        try:
            try:
                with BudgetClient(config, time.monotonic() + MAX_SECONDS) as archive:
                    _check_manifests(archive, case_id, plan)
                    for source in plan['sources'].values():
                        for instance in source['instances']:
                            uid = instance['instance_uid']
                            resource_id = archive.lookup_instance(uid)
                            if resource_id is None:
                                fail('conversion_plan_source_missing', '归档中找不到方案实例，未创建转换任务。')
                            raw = bytearray()
                            with archive.http.stream('GET', '/instances/' + resource_id + '/file',
                                    headers={'Accept': 'application/dicom', 'Accept-Encoding': 'identity'}) as response:
                                if (response.status_code != 200
                                        or response.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/dicom'
                                        or response.headers.get('content-encoding', 'identity').strip().lower() != 'identity'):
                                    fail('conversion_plan_file_unavailable', '归档原文件不可读取，未创建转换任务。')
                                for chunk in response.iter_raw(chunk_size=65536):
                                    raw.extend(chunk)
                                    total += len(chunk)
                                    if len(raw) > MAX_FILE_BYTES or total > MAX_CAPTURE_BYTES:
                                        fail('conversion_plan_capture_budget', '原文件超过本次转换预算，未创建转换任务。')
                            source_dataset(bytes(raw), source, instance)
                            output = capture / ('p' + str(len(files)).zfill(5) + '.dcm')
                            with output.open('xb') as handle:
                                handle.write(raw)
                            files[uid] = {'path': str(output), 'sha256': hashlib.sha256(raw).hexdigest()}
                    _check_manifests(archive, case_id, plan)
                    archive._check_system(archive._json('/system', dicom=False))
                _same_context(config, verify_context)
                read_draft(payload.draft_id, case_id, identity)
            except httpx.HTTPError:
                fail('conversion_plan_archive_unavailable', '归档读取中断，未创建转换任务；请重新尝试。')
            manifest = capture / 'source-files.json'
            _write(manifest, files)
            output_parent = jobs._root().parent / 'dicom-conversion-outputs'
            if output_parent.resolve() != output_parent:
                fail('conversion_plan_path_invalid', '转换输出目录不符合运行配置。')
            output_parent.mkdir(exist_ok=True)
            row = jobs.create_job(folder/'proposal.json', folder/'snapshots.json', manifest,
                output_parent/('web-' + job_id[:16]), register_version_id='web-' + job_id, job_id=job_id)
            job_created = True
        except Exception:
            if not job_created:
                shutil.rmtree(capture, ignore_errors=True)
            raise
        return {**row, 'already_created': False}

