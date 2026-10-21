"""Server-owned conversion versions; registration is explicit and never activates input."""
import hashlib
import json
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.core.config import settings
from app.core.storage import is_supported_storage_path
from app.services.dicom_conversion_integrity import (
    bounded_bytes, inspect_conversion_version, unique_pairs, reject_constant,
)
from app.services.pacs_client import fail, validate_uid
from app.services.dicom_input_plan import PlanError, fail as plan_fail

INSPECTION_LOCK = threading.Lock()


class Entry(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    case_id: StrictInt = Field(gt=0)
    archive_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    archive_fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')
    study_uid: str
    version_dir: str
    report_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    proposal_path: str
    proposal_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    snapshots_path: str
    snapshots_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


class Index(BaseModel):
    model_config = ConfigDict(extra='forbid')
    format: Literal['dicom-conversion-index-v1']
    entries: list[Entry] = Field(max_length=32)


@contextmanager
def _exclusive_index_file_lock(index_path):
    lock_path = index_path.with_name(index_path.name + '.lock')
    handle = None
    locked = False
    try:
        handle = lock_path.open('a+b')
        if os.name == 'nt':
            import msvcrt
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b'0')
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                plan_fail('conversion_registry_busy', '已有转换版本正在登记，请稍后重试。')
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                plan_fail('conversion_registry_busy', '已有转换版本正在登记，请稍后重试。')
        locked = True
        yield
    except OSError:
        plan_fail('conversion_registry_unavailable', '本机转换登记文件不可用；已保留转换产物。')
    finally:
        if handle is not None:
            if locked:
                try:
                    if os.name == 'nt':
                        import msvcrt
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
            handle.close()


def _index_path():
    path = Path(settings.DICOM_CONVERSION_INDEX_FILE).absolute()
    if not is_supported_storage_path(path) or path.resolve() != path or not path.parent.is_dir():
        plan_fail('conversion_index_path_unsupported', '转换登记索引必须位于已存在的E盘运行目录。')
    return path


def _anchored_file(path, cap):
    try:
        absolute = Path(path).absolute()
        resolved = absolute.resolve(strict=True)
        if not is_supported_storage_path(resolved) or resolved != absolute or not resolved.is_file():
            raise ValueError()
        raw = bounded_bytes(resolved, cap)
        return resolved, hashlib.sha256(raw).hexdigest()
    except Exception:
        plan_fail('conversion_registration_source_invalid', '转换来源文件必须存在于E盘且符合完整性预算。')


def register_verified_version(version_id, case_id, archive_id, archive_fingerprint,
                               study_uid, version_dir, proposal_path, snapshots_path):
    """Register only a fully reopened derivative; never activates model input."""
    if not INSPECTION_LOCK.acquire(blocking=False):
        plan_fail('conversion_registry_busy', '已有转换版本正在核对，请稍后重试。')
    try:
        try:
            absolute_dir = Path(version_dir).absolute()
            directory = absolute_dir.resolve(strict=True)
            if not is_supported_storage_path(directory) or directory != absolute_dir or not directory.is_dir():
                raise ValueError()
            proposal_file, proposal_sha = _anchored_file(proposal_path, 4 * 1024 * 1024)
            snapshots_file, snapshots_sha = _anchored_file(snapshots_path, 16 * 1024 * 1024)
            validate_uid(study_uid)
            report_file = directory / 'conversion-report.json'
            report_sha = hashlib.sha256(bounded_bytes(report_file, 4 * 1024 * 1024)).hexdigest()
            entry = Entry.model_validate({
                'version_id': version_id, 'case_id': case_id, 'archive_id': archive_id,
                'archive_fingerprint': archive_fingerprint, 'study_uid': study_uid,
                'version_dir': str(directory), 'report_sha256': report_sha,
                'proposal_path': str(proposal_file), 'proposal_sha256': proposal_sha,
                'snapshots_path': str(snapshots_file), 'snapshots_sha256': snapshots_sha,
            })
            proposal, snapshots = entry_inputs(entry)
            if not any(row.get('study_uid') == entry.study_uid for row in proposal.get('assignments', [])):
                raise ValueError()
            inspection = inspect_conversion_version(directory, report_sha, proposal, snapshots)
            if inspection.get('status') != 'verified_readonly':
                plan_fail('conversion_registration_integrity_required', '转换版本完整性复核未通过；索引未修改。')
        except PlanError:
            raise
        except Exception:
            plan_fail('conversion_registration_source_invalid', '转换计划、报告或版本目录无法匹配；索引未修改。')

        index_path = _index_path()
        with _exclusive_index_file_lock(index_path):
            try:
                existing = load_index()
            except Exception:
                plan_fail('conversion_index_invalid', '现有转换登记索引无效；未覆盖原文件。')
            same_id = next((row for row in existing if row.version_id == entry.version_id), None)
            if same_id is not None:
                if same_id == entry:
                    return {'status': 'already_registered', 'version_id': entry.version_id,
                            'model_input_eligible': False, 'current_mri_replaced': False}
                plan_fail('conversion_version_conflict', '此转换版本编号已绑定其他来源；索引未修改。')
            try:
                updated = Index(format='dicom-conversion-index-v1', entries=[*existing, entry])
            except Exception:
                plan_fail('conversion_index_capacity_or_schema', '转换索引容量已满或新版本结构无效；索引未修改。')
            raw = json.dumps(updated.model_dump(mode='json'), ensure_ascii=False,
                             indent=2, allow_nan=False).encode('utf-8')
            if len(raw) > 1024 * 1024:
                plan_fail('conversion_index_capacity_or_schema', '转换索引超过1MiB上限；索引未修改。')
            temp_path = None
            try:
                descriptor, temp_name = tempfile.mkstemp(prefix=index_path.name + '.', suffix='.tmp',
                                                         dir=str(index_path.parent))
                temp_path = Path(temp_name)
                with os.fdopen(descriptor, 'wb') as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_path, index_path)
            except OSError:
                plan_fail('conversion_index_write_failed', '转换版本登记未能原子保存；已保留转换产物。')
            finally:
                if temp_path is not None and temp_path.exists():
                    try:
                        temp_path.unlink()
                    except OSError:
                        pass
            return {'status': 'registered', 'version_id': entry.version_id,
                    'model_input_eligible': False, 'current_mri_replaced': False}
    finally:
        INSPECTION_LOCK.release()


def load_index():
    try:
        path = Path(settings.DICOM_CONVERSION_INDEX_FILE).absolute()
        if not is_supported_storage_path(path) or path.resolve() != path:
            raise ValueError()
        if not path.exists():
            return []
        raw = bounded_bytes(path, 1024 * 1024)
        value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique_pairs, parse_constant=reject_constant)
        index = Index.model_validate(value)
        ids = set()
        for row in index.entries:
            validate_uid(row.study_uid)
            if row.version_id in ids:
                raise ValueError()
            ids.add(row.version_id)
            for location in [row.version_dir, row.proposal_path, row.snapshots_path]:
                file = Path(location)
                if not file.is_absolute() or not is_supported_storage_path(file) or file.absolute() != file.resolve():
                    raise ValueError()
        return index.entries
    except Exception:
        fail('conversion_index_invalid', '本地转换版本索引无效，请核对服务端文件；未输出路径或原始内容。')


def read_anchored(path, expected_sha, cap):
    file = Path(path).absolute()
    if not is_supported_storage_path(file) or file.resolve() != file:
        raise ValueError()
    raw = bounded_bytes(file, cap)
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError()
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique_pairs, parse_constant=reject_constant)


def entry_inputs(entry):
    proposal = read_anchored(entry.proposal_path, entry.proposal_sha256, 4 * 1024 * 1024)
    snapshots = read_anchored(entry.snapshots_path, entry.snapshots_sha256, 16 * 1024 * 1024)
    if (proposal.get('case_id') != entry.case_id or proposal.get('archive_id') != entry.archive_id
            or proposal.get('archive_fingerprint') != entry.archive_fingerprint
            or proposal.get('data_role') != 'dicom-metadata-snapshot'
            or any(row.get('study_uid') != entry.study_uid for row in proposal.get('assignments', []))):
        raise ValueError()
    return proposal, snapshots


def inspect_entry(entry):
    if not INSPECTION_LOCK.acquire(blocking=False):
        fail('conversion_inspection_busy', '已有转换版本正在核对，请稍后重试。', 409)
    try:
        try:
            proposal, snapshots = entry_inputs(entry)
        except Exception:
            return {'status': 'invalid', 'reason': 'conversion_registered_source_mismatch',
                    'message': '登记的来源文件不可读、版本不同或病例来源不符；合成版本不关联真实病例。',
                    'model_input_eligible': False, 'archive_or_business_database_written': False}
        report = inspect_conversion_version(entry.version_dir, entry.report_sha256, proposal, snapshots)
        try:
            read_anchored(entry.proposal_path, entry.proposal_sha256, 4 * 1024 * 1024)
            read_anchored(entry.snapshots_path, entry.snapshots_sha256, 16 * 1024 * 1024)
        except Exception:
            return {'status': 'invalid', 'reason': 'conversion_registered_source_changed',
                    'message': '检查窗口内登记的来源文件改变；请重新核对版本。', 'model_input_eligible': False}
        # Allow only display fields; no server paths, free text, credentials, pixels.
        return {key: report[key] for key in ['status', 'reason', 'model_input_eligible',
                'archive_or_business_database_written', 'live_archive_reconciled', 'reviewer_authenticated',
                'data_role', 'plan_revision', 'report_sha256', 'outputs', 'message'] if key in report}
    finally:
        INSPECTION_LOCK.release()


def check_archive_entry(entry, config):
    if not INSPECTION_LOCK.acquire(blocking=False):
        fail('conversion_inspection_busy', '已有转换版本正在核对，请稍后重试。', 409)
    try:
        try:
            proposal, snapshots = entry_inputs(entry)
        except Exception:
            return {'status':'invalid','reason':'conversion_registered_source_mismatch',
                    'message':'登记来源缺失、变更或不匹配；没有取得归档来源状态。','live_archive_reconciled':False}
        from app.services.dicom_conversion_source import check_conversion_sources
        report = check_conversion_sources(entry.version_dir,entry.report_sha256,proposal,snapshots,config)
        try:
            entry_inputs(entry)
        except Exception:
            return {'status':'invalid','reason':'conversion_registered_source_changed',
                    'message':'核对窗口内登记来源文件改变。','live_archive_reconciled':False}
        return report
    finally:
        INSPECTION_LOCK.release()

