"""Bounded, read-only Orthanc/QIDO client. No arbitrary URLs or browser credentials."""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, field_validator

from app.core.config import settings
from app.core.storage import is_supported_storage_path

UID_PATTERN = r'(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))+'
MAX_JSON_BYTES = 4 * 1024 * 1024


def fail(reason, message, status=503):
    raise HTTPException(status, detail={'reason': reason, 'message': message}, headers={'Cache-Control': 'no-store'})


def validate_uid(value):
    if not isinstance(value, str) or len(value) > 64 or not re.fullmatch(UID_PATTERN, value):
        fail('invalid_uid', 'DICOM UID 必须为不超过64字符的数字点分标识。', 422)
    return value


class PacsConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    format_version: int = Field(strict=True, ge=1, le=1)
    archive_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    base_url: str
    username: str = Field(min_length=1, max_length=128)
    password: SecretStr
    # Operator enables only after source/license and pixel deidentification review.
    allow_pixel_read: StrictBool = False
    # Local operator pin for reconciliation and study links, never browser input.
    expected_database_server_identifier: str | None = Field(
        default=None, pattern=r'^[a-zA-Z0-9_-]{1,128}$')

    @field_validator('base_url')
    @classmethod
    def local_origin(cls, value):
        origin = urlsplit(value)
        loopback = origin.hostname in ('127.0.0.1', '::1')
        docker_host = settings.PACS_ALLOW_DOCKER_HOST and origin.hostname == 'host.docker.internal'
        if (origin.scheme not in ('http', 'https') or not (loopback or docker_host)
                or origin.username or origin.password or origin.query or origin.fragment
                or origin.path not in ('', '/') or not origin.port):
            raise ValueError('Only an explicitly permitted local origin with a port is supported')
        if settings.PACS_ALLOW_DOCKER_HOST and loopback:
            # The persisted workstation config correctly uses loopback on Windows.
            # Inside Docker, loopback points back into the container, so map only
            # those two explicit loopback hosts to Docker Desktop's host gateway.
            value = origin._replace(netloc=f'host.docker.internal:{origin.port}').geturl()
        return value.rstrip('/')

    @field_validator('username')
    @classmethod
    def basic_user(cls, value):
        if ':' in value or any(ord(c) < 32 for c in value):
            raise ValueError('Invalid Basic auth username')
        return value

    @field_validator('password')
    @classmethod
    def nonempty_password(cls, value):
        if not value.get_secret_value():
            raise ValueError('Empty password is not supported')
        return value

    @property
    def endpoint_fingerprint(self):
        identity = self.base_url
        if self.expected_database_server_identifier is not None:
            identity += '\n' + self.expected_database_server_identifier
        return hashlib.sha256(identity.encode()).hexdigest()


def load_config():
    try:
        path = Path(settings.PACS_CONFIG_FILE).resolve()
        if not is_supported_storage_path(path):
            fail('invalid_config', '本地归档配置路径必须为受支持的绝对运行路径。')
        if not path.exists():
            fail('unconfigured', '本地 PACS 尚未配置，DICOM 归档与阅片尚不可用。')
        if path.stat().st_size > 16384:
            fail('invalid_config', '本地 PACS 配置无效，请检查服务端配置。')
        return PacsConfig.model_validate_json(path.read_text(encoding='utf-8-sig'))
    except HTTPException:
        raise
    except Exception:
        # Never expose Pydantic input values, paths, credentials or upstream bodies.
        fail('invalid_config', '本地 PACS 配置无效，请检查服务端配置。')


def tag_value(item, tag, required=False):
    try:
        attr = item.get(tag, {})
        values = attr.get('Value', [])
        if not isinstance(values, list):
            raise ValueError()
        if not values:
            if required:
                raise ValueError()
            return None
        if len(values) != 1 or not isinstance(values[0], (str, int, float)):
            raise ValueError()
        return str(values[0])
    except (AttributeError, ValueError, TypeError):
        fail('invalid_metadata', '归档返回的 DICOM 元数据缺失或格式错误。', 502)


def metadata_uid(item, tag, required=True):
    value = tag_value(item, tag, required)
    if value is None:
        return None
    try:
        return validate_uid(value)
    except HTTPException:
        fail('invalid_metadata', '归档返回了非法 DICOM UID。', 502)


class PacsClient:
    def __init__(self, config=None):
        self.config = config or load_config()
        self.http = httpx.Client(base_url=self.config.base_url,
                                 auth=(self.config.username, self.config.password.get_secret_value()),
                                 timeout=httpx.Timeout(10., connect=2.), trust_env=False,
                                 follow_redirects=False)

    def __enter__(self):
        try:
            # Reject an unauthenticated archive, rather than merely trusting its config.
            with self.http.stream('GET', '/system', auth=None) as response:
                if response.status_code != 401:
                    fail('archive_auth_required', '归档未强制鉴权或地址不是受支持的 Orthanc，拒绝连接。')
            system = self._json('/system', dicom=False)
            if not isinstance(system, dict) or not isinstance(system.get('Version'), str):
                fail('invalid_archive', '归档系统信息不符合 Orthanc 接口。', 502)
            expected = self.config.expected_database_server_identifier
            if expected is not None and system.get('DatabaseServerIdentifier') != expected:
                fail('archive_identity_mismatch', '归档服务标识与本地配置不一致，拒绝复用关联。', 409)
            self.version = system['Version']
            self.system = system
            return self
        except httpx.HTTPError:
            self.http.close()
            fail('unavailable', '无法连接本地 PACS，请检查归档服务与 DICOMweb 插件。')
        except Exception:
            self.http.close()
            raise

    def __exit__(self, *_):
        self.http.close()

    def _json(self, path, params=None, dicom=True):
        accept = 'application/dicom+json' if dicom else 'application/json'
        try:
            with self.http.stream('GET', path, params=params, headers={'Accept': accept}) as response:
                if dicom and response.status_code == 204:
                    return []
                if response.status_code == 404:
                    fail('not_found', '归档资源或 DICOMweb 接口不存在。', 404)
                if response.status_code in (401, 403):
                    fail('authentication_failed', '本地 PACS 服务端凭据未通过鉴权。')
                if response.status_code != 200:
                    fail('upstream_error', '本地 PACS 返回非成功状态，未取得归档结果。', 502)
                content_type = response.headers.get('content-type', '').split(';')[0].strip().lower()
                if content_type not in ('application/dicom+json', 'application/json'):
                    fail('invalid_metadata', '本地 PACS 未返回受支持的 JSON 元数据。', 502)
                body = bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    body.extend(chunk)
                    if len(body) > MAX_JSON_BYTES:
                        fail('metadata_too_large', '归档元数据超过单次读取上限，请缩小查询。', 502)
                return json.loads(body)
        except httpx.HTTPError:
            fail('unavailable', '无法连接本地 PACS，请检查归档服务与 DICOMweb 插件。')
        except (ValueError, UnicodeError):
            fail('invalid_metadata', '归档返回的 JSON 元数据格式错误。', 502)

    def query(self, level, study_uid=None, series_uid=None, limit=100, offset=0):
        path = '/dicom-web/studies'
        params = {'limit': limit, 'offset': offset}
        if level == 'studies':
            if study_uid:
                params['StudyInstanceUID'] = validate_uid(study_uid)
        else:
            path += '/' + validate_uid(study_uid) + '/series'
            if level == 'instances':
                path += '/' + validate_uid(series_uid) + '/instances'
                params['includefield'] = '00200052'
            elif level != 'series':
                raise ValueError('Unsupported internal query level')
        raw = self._json(path, params)
        if not isinstance(raw, list) or len(raw) > limit:
            fail('invalid_metadata', '归档返回的列表格式或分页上限不符合读取契约。', 502)
        result, seen = [], set()
        for item in raw:
            if not isinstance(item, dict):
                fail('invalid_metadata', '归档返回的 DICOM JSON 项无效。', 502)
            actual_study = metadata_uid(item, '0020000D', level == 'studies') or study_uid
            if study_uid and actual_study != study_uid:
                fail('uid_mismatch', '归档返回的检查 UID 与请求不一致。', 502)
            row = {'study_uid': actual_study}
            if level == 'studies':
                modality_attr = item.get('00080061', {})
                if not isinstance(modality_attr, dict):
                    fail('invalid_metadata', '归档模态属性格式错误。', 502)
                modalities = modality_attr.get('Value', [])
                if not isinstance(modalities, list) or not all(isinstance(v, str) for v in modalities):
                    fail('invalid_metadata', '归档模态列表格式错误。', 502)
                row.update(study_date=tag_value(item, '00080020'),
                           modalities=modalities,
                           series_count=tag_value(item, '00201206'), instance_count=tag_value(item, '00201208'))
                key = actual_study
            else:
                actual_series = metadata_uid(item, '0020000E', level == 'series') or series_uid
                if series_uid and actual_series != series_uid:
                    fail('uid_mismatch', '归档返回的序列 UID 与请求不一致。', 502)
                row['series_uid'] = actual_series
                if level == 'series':
                    row.update(modality=tag_value(item, '00080060'), series_number=tag_value(item, '00200011'),
                               instance_count=tag_value(item, '00201209'))
                    key = actual_series
                else:
                    row.update(instance_uid=metadata_uid(item, '00080018'),
                               sop_class_uid=metadata_uid(item, '00080016'),
                               frame_of_reference_uid=metadata_uid(item, '00200052', False),
                               instance_number=tag_value(item, '00200013'), frames=tag_value(item, '00280008'))
                    key = row['instance_uid']
            if key in seen:
                fail('duplicate_uid', '归档列表包含重复 UID，拒绝含混映射。', 502)
            seen.add(key)
            result.append(row)
        return result
