"""Time-bounded, read-only archive observation for a local conversion version."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
import httpx

from fastapi import HTTPException

from app.services.dicom_conversion_integrity import (
    REPORT_CAP, MAX_INPUT_BYTES, bounded_bytes, scoped_path, unique_pairs, reject_constant,
    inspect_conversion_version,
)
from app.services.dicom_input_plan import PlanError, ROLES, validate_plan
from app.services.dicom_series import series_manifest
from app.services.pacs_client import load_config, fail
from app.services.pacs_reconcile import ReconciliationClient

MAX_CHECK_SECONDS = 120


class DeadlineStream(httpx.SyncByteStream):
    def __init__(self, stream, check):
        self.stream, self.check = stream, check
    def __iter__(self):
        for block in self.stream:
            self.check()
            yield block
    def close(self):
        self.stream.close()


class DeadlineTransport(httpx.BaseTransport):
    def __init__(self, deadline):
        self.deadline = deadline
        self.inner = httpx.HTTPTransport(trust_env=False)
    def check(self):
        remaining = self.deadline - perf_counter()
        if remaining <= 0:
            fail('conversion_source_check_timeout','来源核对达到120秒预算，未取得完整状态；请稍后重试。')
        return remaining
    def handle_request(self, request):
        remaining = min(10., self.check())
        request.extensions['timeout'] = {'connect':min(2.,remaining),'read':remaining,'write':remaining,'pool':remaining}
        response = self.inner.handle_request(request)
        response.stream = DeadlineStream(response.stream,self.check)
        return response
    def close(self):
        self.inner.close()


class BudgetClient(ReconciliationClient):
    def __init__(self, config, deadline):
        super().__init__(config)
        self.http.close()
        self.budget_transport = DeadlineTransport(deadline)
        self.http = httpx.Client(base_url=config.base_url,auth=(config.username,config.password.get_secret_value()),
                                timeout=httpx.Timeout(10.,connect=2.),trust_env=False,follow_redirects=False,
                                transport=self.budget_transport)


def check_conversion_sources(directory, report_sha256, proposal, snapshots, config=None):
    started = perf_counter()
    base = {'format':'dicom-conversion-source-check-v1', 'started_utc':datetime.now(timezone.utc).isoformat(),
            'model_input_eligible':False, 'current_mri_replaced':False, 'archive_written':False,
            'source_files_written':False, 'reviewer_authenticated':False,
            'database_identity_cryptographically_verified':False, 'observation_only':True,
            'live_archive_reconciled':False,
            'limitations':['这是有起止时间的逐文件观察，不是归档事务快照或患者/审核者认证。',
                           '原字节一致不代替数据许可、像素审核或四角色实体证据，不能激活AI。']}
    try:
        plan = validate_plan(proposal, snapshots)
        target = config or load_config()
        if target.archive_id != plan['archive_id'] or target.endpoint_fingerprint != plan['archive_fingerprint']:
            fail('conversion_archive_target_mismatch', '归档目标与转换规划不同，未读取归档原文件。', 409)
        # Context and permissions precede any network or expensive local inspection.
        if not target.allow_pixel_read:
            fail('pixel_read_disabled', '服务端未开启原文件来源核对。')
        if target.expected_database_server_identifier is None:
            fail('archive_identity_unpinned', '未固定归档标识，不能核对转换来源。')
        local = inspect_conversion_version(directory, report_sha256, proposal, snapshots)
        if local['status'] != 'verified_readonly':
            return {**base, 'status':local['status'], 'reason':local['reason'],
                    'message':local.get('message','本地转换完整性未通过。'),
                    'completed_utc':datetime.now(timezone.utc).isoformat()}
        root = Path(directory).absolute()
        report_path = scoped_path(root, root/'conversion-report.json')
        raw = bounded_bytes(report_path, REPORT_CAP)
        if hashlib.sha256(raw).hexdigest() != report_sha256:
            fail('conversion_changed_before_archive_check', '本地转换在归档核对前改变。', 409)
        report = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_pairs, parse_constant=reject_constant)
        bindings = []; total = 0
        for role in ROLES:
            source = plan['sources'][role]
            for record in report['outputs'][role]['source_instances']:
                path = scoped_path(root, root/'original-byte-snapshots'/(record['dicom_sha256']+'.dcm'),record['snapshot_path'])
                size = path.stat().st_size; total += size
                bindings.append((role, {'study_uid':source['study_uid'], 'series_uid':source['series_uid'],
                    'sop_uid':record['instance_uid'], 'source_sha256':record['dicom_sha256'], 'source_bytes':size}))
        if total > MAX_INPUT_BYTES:
            fail('conversion_archive_byte_budget_exceeded', '归档来源单轮原文件总量超过1GiB。', 413)
        receipts = {}; pass_times = []
        with BudgetClient(target,started+MAX_CHECK_SECONDS) as archive:
            for pass_number in (1, 2):
                begin = perf_counter()
                for role in ROLES:
                    source = plan['sources'][role]
                    current = series_manifest(archive, source['study_uid'], source['series_uid'])
                    if (current['metadata_sha256'] != source['series_metadata_sha256']
                            or current['geometry'] != source['geometry']
                            or [row['instance_uid'] for row in current['instances']] != [row['instance_uid'] for row in source['instances']]
                            or any(row['metadata_sha256'] != old['metadata_sha256'] for row,old in zip(current['instances'],source['instances']))):
                        fail('conversion_archive_metadata_stale', '当前归档实例集合、空间或元数据与转换来源不同。', 409)
                for role, binding in bindings:
                    receipt = archive.reconcile(**binding)
                    if not receipt['verified_present_at_check']:
                        fail('conversion_archive_instance_missing', '当前归档缺少转换来源实例，不当作原文件已归档。', 409)
                    uid = binding['sop_uid']
                    if pass_number == 2 and receipt['orthanc_instance_id'] != receipts[uid]['orthanc_instance_id']:
                        fail('conversion_archive_mapping_changed', '两轮核对的归档实例映射不同。', 409)
                    receipts[uid] = receipt
                archive._check_system(archive._json('/system',dicom=False))
                pass_times.append((perf_counter()-begin)*1000)
            # A final whole-series reread catches metadata changes after the last
            # per-instance byte observation. Archive writers are not locked.
            for role in ROLES:
                source=plan['sources'][role]
                if series_manifest(archive,source['study_uid'],source['series_uid'])['metadata_sha256'] != source['series_metadata_sha256']:
                    fail('conversion_archive_metadata_stale', '归档核对结束时序列来源版本已经改变。',409)
        # Local files are checked again, not accepted from the earlier JSON alone.
        after = inspect_conversion_version(directory, report_sha256, proposal, snapshots)
        if after['status'] != 'verified_readonly':
            return {**base,'status':after['status'],'reason':after['reason'],
                    'message':'归档观察窗口内本地版本改变，完整来源状态未取得。',
                    'completed_utc':datetime.now(timezone.utc).isoformat()}
        if perf_counter()-started > MAX_CHECK_SECONDS:
            fail('conversion_source_check_timeout','来源核对达到120秒预算，未取得完整状态；请稍后重试。')
        return {**base, 'status':'matched_at_check', 'reason':None, 'data_role':plan['data_role'],
                'archive_observation_scope':'synthetic_protocol_only' if plan['data_role']=='synthetic-fixture' else 'configured_archive_observation',
                'case_id':plan['case_id'], 'archive_id':plan['archive_id'], 'archive_fingerprint':plan['archive_fingerprint'],
                'plan_revision':plan['plan_revision'], 'report_sha256':report_sha256,
                'live_archive_reconciled':True, 'instances_checked':len(bindings), 'roles_checked':list(ROLES),
                'raw_byte_passes':2, 'source_bytes_per_pass':total, 'total_raw_bytes_observed':total*2,
                'raw_pass_elapsed_ms':pass_times, 'total_elapsed_ms':(perf_counter()-started)*1000,
                'completed_utc':datetime.now(timezone.utc).isoformat(),
                'message':'本地转换与配置归档的实例原字节及元数据在本次核对中一致；仍待来源和角色审核，不可提交AI。'}
    except (HTTPException, PlanError) as error:
        detail=error.detail if isinstance(error,HTTPException) and isinstance(error.detail,dict) else {}
        reason=detail.get('reason',error.reason if isinstance(error,PlanError) else 'archive_check_failed')
        message=detail.get('message',str(error) if isinstance(error,PlanError) else '归档来源无法核对。')
        if perf_counter()-started >= MAX_CHECK_SECONDS:
            reason='conversion_source_check_timeout'
            message='来源核对达到120秒预算，未取得完整状态；请稍后重试。'
        stale={'conversion_archive_target_mismatch','conversion_archive_metadata_stale','conversion_archive_instance_missing',
               'conversion_archive_mapping_changed','conversion_changed_before_archive_check','archive_parent_uid_mismatch',
               'archive_content_conflict','archive_changed_during_check','archive_identity_mismatch','ambiguous_archive_uid',
               'series_instance_set_mismatch','series_changed_during_check','duplicate_series_uid','uid_mismatch'}
        return {**base,'status':'stale' if reason in stale else 'unavailable','reason':reason,'message':message,
                'completed_utc':datetime.now(timezone.utc).isoformat()}
    except Exception:
        return {**base,'status':'invalid','reason':'conversion_source_check_failed',
                'message':'来源核对失败，未输出路径、凭据、私有标签或异常原文。',
                'completed_utc':datetime.now(timezone.utc).isoformat()}
