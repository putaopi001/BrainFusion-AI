"""Read-only Orthanc import reconciliation. No upload, overwrite or approval."""
import hashlib
import json
import re
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from app.services.pacs_client import PacsClient, MAX_JSON_BYTES, fail, validate_uid
from app.services.dicom_preflight import MAX_FILE_BYTES

ORTHANC_ID = r'[0-9a-f]{8}(?:-[0-9a-f]{8}){4}'


def orthanc_id(value):
    if not isinstance(value, str) or not re.fullmatch(ORTHANC_ID, value):
        fail('invalid_archive_resource', '归档资源标识无效，未核实导入结果。', 502)
    return value


class ReconciliationClient(PacsClient):
    def _check_system(self, system):
        expected = self.config.expected_database_server_identifier
        if expected is None:
            fail('archive_identity_unpinned', '未固定归档服务标识，不能核实导入结果。')
        if not isinstance(system, dict) or system.get('DatabaseServerIdentifier') != expected:
            fail('archive_identity_mismatch', '归档服务标识与本地配置不一致。', 409)
        # These are preparation requirements, not authorization to write.
        if (system.get('OverwriteInstances') is not False
                or system.get('OverwriteInstancesMode', 'Never') != 'Never'):
            fail('archive_overwrite_enabled', '归档允许覆盖实例，不符合原文件保留契约。', 409)
        if system.get('IngestTranscoding') != '':
            fail('archive_transcoding_enabled', '归档摄入转换未禁用，不能保证原文件字节一致。', 409)
        if type(system.get('ReadOnly')) is not bool:
            fail('archive_capabilities_unknown', '归档未明确提供所需配置状态。', 502)

    def __enter__(self):
        if not self.config.allow_pixel_read:
            self.http.close()
            fail('pixel_read_disabled', '服务端未开启原文件核对，归档内容未读取。')
        if self.config.expected_database_server_identifier is None:
            self.http.close()
            fail('archive_identity_unpinned', '未固定归档服务标识，不能核实导入结果。')
        super().__enter__()
        try:
            self._check_system(self.system)
            return self
        except Exception:
            self.http.close()
            raise

    def lookup_instance(self, sop_uid):
        uid = validate_uid(sop_uid)
        try:
            # POST is a read-only UID lookup according to Orthanc's REST API.
            with self.http.stream('POST', '/tools/lookup', content=uid.encode('ascii'),
                                  headers={'Accept': 'application/json', 'Content-Type': 'text/plain'}) as response:
                if response.status_code in (401, 403):
                    fail('authentication_failed', '归档身份查询未通过鉴权。')
                if response.status_code != 200:
                    fail('archive_lookup_unresolved', '归档身份查询未成功，不能当作实例不存在。', 502)
                if response.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
                    fail('invalid_archive_lookup', '归档身份查询返回格式错误。', 502)
                body = bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    body.extend(chunk)
                    if len(body) > MAX_JSON_BYTES:
                        fail('metadata_too_large', '归档身份查询超出上限。', 502)
                data = json.loads(body)
        except httpx.HTTPError:
            fail('unavailable', '归档身份查询连接失败，尚未核实结果。')
        except (ValueError, UnicodeError):
            fail('invalid_archive_lookup', '归档身份查询返回格式错误。', 502)
        if not isinstance(data, list) or len(data) > 1:
            fail('ambiguous_archive_uid', '归档 UID 对应多个或含混资源，拒绝复用。', 409)
        if not data:
            return None
        item = data[0]
        if not isinstance(item, dict) or item.get('Type') != 'Instance':
            fail('invalid_archive_lookup', '归档 UID 未对应唯一实例资源。', 502)
        instance_id = orthanc_id(item.get('ID'))
        if item.get('Path') != '/instances/' + instance_id:
            fail('invalid_archive_lookup', '归档资源路径与标识不一致。', 502)
        return instance_id

    def resource(self, level, resource_id, uid, uid_tag):
        actual_id = orthanc_id(resource_id)
        route = {'Instance': 'instances', 'Series': 'series', 'Study': 'studies'}[level]
        item = self._json('/' + route + '/' + actual_id, dicom=False)
        if (not isinstance(item, dict) or item.get('ID') != actual_id or item.get('Type') != level
                or not isinstance(item.get('MainDicomTags'), dict)
                or item['MainDicomTags'].get(uid_tag) != uid):
            fail('archive_parent_uid_mismatch', '归档检查/序列/实例身份与候选不一致。', 409)
        return item

    def file_hash(self, instance_id, expected_bytes):
        digest, size = hashlib.sha256(), 0
        try:
            with self.http.stream('GET', '/instances/' + orthanc_id(instance_id) + '/file',
                                  headers={'Accept': 'application/dicom', 'Accept-Encoding': 'identity'}) as response:
                if response.status_code != 200:
                    fail('archive_file_unresolved', '归档原文件尚未取得，不能确认已保存。', 502)
                if (response.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/dicom'
                        or response.headers.get('content-encoding', 'identity').strip().lower() != 'identity'):
                    fail('invalid_archive_file', '归档原文件运输格式不符合字节核对契约。', 502)
                length = response.headers.get('content-length')
                if length is not None and (not length.isdigit() or int(length) != expected_bytes):
                    fail('archive_content_conflict', '同一实例 UID 的原文件大小与候选不一致。', 409)
                for chunk in response.iter_raw(chunk_size=65536):
                    size += len(chunk)
                    if size > expected_bytes:
                        fail('archive_content_conflict', '同一实例 UID 的原文件大小与候选不一致。', 409)
                    digest.update(chunk)
        except httpx.HTTPError:
            fail('archive_file_unresolved', '归档原文件连接中断，尚未核实保存结果。')
        if size != expected_bytes:
            fail('archive_content_conflict', '同一实例 UID 的原文件大小与候选不一致。', 409)
        return digest.hexdigest()

    def reconcile(self, study_uid, series_uid, sop_uid, source_sha256, source_bytes):
        for value in (study_uid, series_uid, sop_uid):
            validate_uid(value)
        if (not isinstance(source_sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', source_sha256)
                or type(source_bytes) is not int or not 132 <= source_bytes <= MAX_FILE_BYTES):
            fail('invalid_candidate_binding', '候选原文件哈希或大小无效。', 422)
        start = datetime.now(timezone.utc).isoformat()
        instance_id = self.lookup_instance(sop_uid)
        if instance_id is not None:
            instance = self.resource('Instance', instance_id, sop_uid, 'SOPInstanceUID')
            series = self.resource('Series', instance.get('ParentSeries'), series_uid, 'SeriesInstanceUID')
            self.resource('Study', series.get('ParentStudy'), study_uid, 'StudyInstanceUID')
            if self.file_hash(instance_id, source_bytes) != source_sha256:
                fail('archive_content_conflict', '同一实例 UID 的归档原文件哈希与候选不一致。', 409)
        # Recheck logical target/policy and lookup after the read. This is still
        # a time-bounded observation, not a lock on other archive writers.
        self._check_system(self._json('/system', dicom=False))
        if self.lookup_instance(sop_uid) != instance_id:
            fail('archive_changed_during_check', '核对期间归档实例映射发生变化，结果未确认。', 409)
        pin = hashlib.sha256((self.config.archive_id + '\n' + self.config.base_url + '\n'
                              + self.config.expected_database_server_identifier).encode()).hexdigest()
        return {'format': 'pacs-read-only-reconciliation-v1',
                'state': 'matched_existing' if instance_id else 'absent_at_check',
                'archive_id': self.config.archive_id, 'target_fingerprint': pin,
                'orthanc_instance_id': instance_id, 'study_uid': study_uid, 'series_uid': series_uid,
                'sop_uid': sop_uid, 'source_sha256': source_sha256, 'source_bytes': source_bytes,
                'verified_present_at_check': instance_id is not None,
                'started_utc': start, 'completed_utc': datetime.now(timezone.utc).isoformat(),
                'archive_imported_by_tool': False, 'upload_allowed': False,
                'observation_only': True, 'database_identity_cryptographically_verified': False}


def reconcile_archive_instance(binding, config=None):
    """Structured unresolved/conflict outcomes; never blind upload or fake success."""
    result = {'format': 'pacs-read-only-reconciliation-v1', 'state': 'unresolved',
              'verified_present_at_check': None, 'archive_imported_by_tool': False,
              'upload_allowed': False, 'observation_only': True}
    try:
        with ReconciliationClient(config) as archive:
            return archive.reconcile(**binding)
    except HTTPException as error:
        detail = error.detail if isinstance(error.detail, dict) else {}
        reason = detail.get('reason', 'archive_check_failed')
        result['reason'] = reason
        if reason in ('archive_parent_uid_mismatch', 'archive_content_conflict', 'ambiguous_archive_uid'):
            result['state'] = 'conflict'
        result['completed_utc'] = datetime.now(timezone.utc).isoformat()
        return result
