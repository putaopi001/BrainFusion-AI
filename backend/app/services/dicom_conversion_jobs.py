"""Persistent, resumable local conversion jobs; no automatic model activation."""
import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.core.storage import is_supported_storage_path
from app.services.dicom_conversion import convert_and_verify
from app.services.dicom_conversion_registry import register_verified_version
from app.services.dicom_input_plan import PlanError, validate_plan
from app.services.dicom_conversion_integrity import unique_pairs, reject_constant

JOB_FORMAT = "dicom-conversion-job-v1"
JOB_ID = re.compile(r"^[a-f0-9]{32}$")
VERSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_LOCAL_LOCKS = {}
_LOCAL_LOCKS_GUARD = threading.Lock()
_JOB_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dicom-conversion")
_SUBMISSIONS = {}
_SUBMISSIONS_GUARD = threading.Lock()


def _utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fault(reason, message):
    raise PlanError(reason, message)

def read(path, cap):
    resolved = Path(path).resolve(strict=True)
    if not is_supported_storage_path(resolved) or not resolved.is_file() or resolved.stat().st_size > cap:
        _fault("conversion_job_input_invalid", "转换作业输入必须是受限大小的E盘文件。")
    with resolved.open("rb") as handle:
        raw = handle.read(cap + 1)
    if len(raw) > cap:
        _fault("conversion_job_input_invalid", "转换作业输入超过大小限制。")
    try:
        value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_pairs, parse_constant=reject_constant)
    except Exception:
        _fault("conversion_job_input_invalid", "转换作业输入格式无效。")
    return value, hashlib.sha256(raw).hexdigest()

def _root(create=False):
    index = Path(settings.DICOM_CONVERSION_INDEX_FILE).absolute()
    try:
        parent = index.parent.resolve(strict=True)
    except FileNotFoundError:
        # A fresh Docker runtime may not have created the optional local job
        # directory yet. Listing jobs is read-only and should behave as empty;
        # only a write path may create the configured runtime directory.
        parent = index.parent.resolve(strict=False)
    root = parent / "dicom-conversion-jobs"
    if not is_supported_storage_path(parent) or parent != index.parent or root.resolve() != root:
        _fault("conversion_jobs_path_unsupported", "转换作业目录必须位于配置的E盘运行根。")
    if create:
        parent.mkdir(parents=True, exist_ok=True)
        root.mkdir(exist_ok=True)
    return root


def _local_lock(job_id):
    with _LOCAL_LOCKS_GUARD:
        return _LOCAL_LOCKS.setdefault(job_id, threading.Lock())


@contextmanager
def _file_lock(path, blocking=True):
    handle = None
    acquired = False
    local = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("a+b")
        if os.name == "nt":
            import msvcrt
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
            except OSError:
                yield False
                return
            acquired = True
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            except OSError:
                yield False
                return
            acquired = True
        yield True
    except PlanError:
        raise
    except OSError:
        _fault("conversion_job_storage_unavailable", "转换作业账本暂不可用；原始输入保持不变。")
    finally:
        if handle is not None:
            if acquired:
                try:
                    if os.name == "nt":
                        import msvcrt
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
            handle.close()


@contextmanager
def _run_lock(job_id, blocking=False):
    local = _local_lock(job_id)
    if not local.acquire(blocking=blocking):
        yield False
        return
    try:
        with _file_lock(_root() / job_id / "run.lock", blocking=blocking) as acquired:
            yield acquired
    finally:
        local.release()


def _job_file(job_id):
    if not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id):
        _fault("conversion_job_not_found", "转换作业不存在。")
    root = _root()
    path = root / job_id / "job.json"
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        _fault("conversion_job_not_found", "转换作业不存在。")
    if not is_supported_storage_path(resolved) or resolved.parent.parent != root.resolve(strict=True):
        _fault("conversion_job_invalid", "转换作业记录范围无效。")
    return path


def _read_job(job_id):
    path = _job_file(job_id)
    try:
        raw = path.read_bytes()
        if len(raw) > 128 * 1024:
            raise ValueError()
        row = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_pairs, parse_constant=reject_constant)
        if row.get("format") != JOB_FORMAT or row.get("job_id") != job_id:
            raise ValueError()
        return row
    except Exception:
        _fault("conversion_job_record_invalid", "转换作业记录不可读取；保留原文件待检查。")


def _write_job(job_id, row, state_lock_held=False):
    if not state_lock_held:
        with _file_lock(_job_file(job_id).with_name("state.lock"), blocking=True) as acquired:
            if not acquired:
                _fault("conversion_job_busy", "转换作业状态正被更新，请重试。")
            return _write_job(job_id, row, state_lock_held=True)
    path = _job_file(job_id)
    raw = json.dumps(row, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    if len(raw) > 128 * 1024:
        _fault("conversion_job_record_too_large", "转换作业记录超过大小限制。")
    temp = None
    try:
        fd, name = tempfile.mkstemp(prefix="job.", suffix=".tmp", dir=str(path.parent))
        temp = Path(name)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except OSError:
        _fault("conversion_job_write_failed", "转换作业状态未能原子保存；原始文件保持不变。")
    finally:
        if temp is not None and temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass


def _public(row):
    # Input/output paths and original-file manifests stay server-side.
    public = {key: row.get(key) for key in (
        "job_id", "case_id", "version_id", "state", "attempt", "created_utc",
        "updated_utc", "started_utc", "finished_utc", "reason", "registered",
        "model_input_eligible", "current_mri_replaced", "inference_performed")}
    public["all_voxels_compared"] = (row.get("result") or {}).get("all_voxels_compared")
    return public


def _read_input(path, cap):
    resolved = Path(path).resolve(strict=True)
    if not is_supported_storage_path(resolved) or not resolved.is_file() or resolved.stat().st_size > cap:
        _fault("conversion_job_input_invalid", "转换作业输入必须是受限大小的E盘文件。")
    return resolved.read_bytes()


def create_job(proposal_path, snapshots_path, source_files_path, output_dir,
               register_version_id=None, job_id=None):
    job_id = job_id or uuid.uuid4().hex
    if not JOB_ID.fullmatch(job_id):
        _fault("conversion_job_id_invalid", "转换作业编号格式无效。")
    if register_version_id is not None and not VERSION_ID.fullmatch(register_version_id):
        _fault("conversion_version_id_invalid", "转换版本编号格式无效。")
    proposal = Path(proposal_path).resolve(strict=True)
    snapshots = Path(snapshots_path).resolve(strict=True)
    source_files = Path(source_files_path).resolve(strict=True)
    output = Path(output_dir).absolute()
    if not is_supported_storage_path(output) or output.resolve() != output or output.exists() or not output.parent.is_dir():
        _fault("fresh_conversion_directory_required", "转换作业必须指向现有E盘父目录中的新输出目录。")
    proposal_value, proposal_sha = read(proposal, 4 * 1024 * 1024)
    snapshots_value, snapshots_sha = read(snapshots, 16 * 1024 * 1024)
    source_value, source_sha = read(source_files, 1024 * 1024)
    plan = validate_plan(proposal_value, snapshots_value)
    expected_uids = {instance["instance_uid"] for source in plan["sources"].values() for instance in source["instances"]}
    if not isinstance(source_value, dict) or set(source_value) != expected_uids:
        _fault("original_file_set_mismatch", "作业清单必须逐一包含规划中的原始DICOM实例。")
    for path in (proposal, snapshots, source_files):
        if not is_supported_storage_path(path) or not path.is_file():
            _fault("conversion_job_input_invalid", "转换作业输入必须位于E盘。")
    root = _root(create=True)
    folder = root / job_id
    staging = root / ("." + job_id + ".prepare-" + uuid.uuid4().hex)
    if folder.exists():
        _fault("conversion_job_conflict", "此转换作业编号已存在；没有覆盖旧作业。")
    staging.mkdir()
    try:
        inputs = staging / "inputs"
        inputs.mkdir()
        copied = {}
        for key, source in (("proposal", proposal), ("snapshots", snapshots), ("source_files", source_files)):
            dest = inputs / (key + ".json")
            raw = _read_input(source, {"proposal": 4*1024*1024, "snapshots": 16*1024*1024, "source_files": 1024*1024}[key])
            expected = {"proposal": proposal_sha, "snapshots": snapshots_sha, "source_files": source_sha}[key]
            if hashlib.sha256(raw).hexdigest() != expected:
                _fault("conversion_job_input_changed", "作业输入在登记期间发生变化。")
            with dest.open("xb") as handle:
                handle.write(raw)
            copied[key] = {"path": str(folder / "inputs" / (key + ".json")), "sha256": expected}
        row = {"format": JOB_FORMAT, "job_id": job_id, "case_id": plan["case_id"],
               "version_id": register_version_id, "requested_version_id": register_version_id, "register": register_version_id is not None,
               "state": "queued", "attempt": 1, "created_utc": _utc(), "updated_utc": _utc(),
               "started_utc": None, "finished_utc": None, "reason": None, "registered": False,
               "model_input_eligible": False, "current_mri_replaced": False, "inference_performed": False,
               "inputs": copied, "output_base": str(output), "output_dir": None,
               "result": None}
        (staging / "job.json").write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
        staging.rename(folder)
    except Exception:
        # A uniquely-created staging directory is left intact for forensic recovery.
        raise
    return _public(row)


def _attempt_version(base, attempt):
    if base is None or attempt == 1:
        return base
    suffix = "_r" + str(attempt)
    return base[:64-len(suffix)] + suffix


def _attempt_output_path(base, job_id, attempt):
    output = Path(base)
    if attempt > 1:
        output = output.with_name("bf-" + job_id[:12] + "-a" + str(attempt))
    probe = output / "original-byte-snapshots" / ("0" * 64 + ".dcm")
    if len(str(probe)) > 240:
        output = Path(base).with_name("bf-" + job_id[:12] + "-a" + str(attempt))
        probe = output / "original-byte-snapshots" / ("0" * 64 + ".dcm")
    if len(str(probe)) > 240:
        _fault("conversion_output_path_too_long", "转换输出路径过深，无法安全保存原始DICOM快照；请改用较短的E盘输出父目录。")
    return output


def run_job(job_id, expected_attempt=None):
    with _run_lock(job_id, blocking=False) as acquired:
        if not acquired:
            _fault("conversion_job_running", "此转换作业已在另一执行器中运行。")
        row = _read_job(job_id)
        if expected_attempt is not None and row["attempt"] != expected_attempt:
            _fault("conversion_job_stale", "转换作业尝试次数已改变，旧排队请求不再执行。")
        if row["state"] == "succeeded":
            return _public(row)
        if row["state"] != "queued":
            _fault("conversion_job_not_retryable", "仅排队中的转换作业可以执行或重试。")
        now = _utc()
        attempt = row["attempt"]
        row.update(state="running", started_utc=now, finished_utc=None, updated_utc=now,
                   reason=None, output_dir=None)
        _write_job(job_id, row)
        try:
            output = _attempt_output_path(row["output_base"], job_id, attempt)
            if output.exists():
                _fault("fresh_conversion_directory_required", "转换输出已存在，没有覆盖旧文件。")
            row["output_dir"] = str(output)
            proposal, proposal_sha = read(row["inputs"]["proposal"]["path"], 4*1024*1024)
            snapshots, snapshots_sha = read(row["inputs"]["snapshots"]["path"], 16*1024*1024)
            source_files, source_sha = read(row["inputs"]["source_files"]["path"], 1024*1024)
            if any(actual != row["inputs"][key]["sha256"] for key, actual in (
                    ("proposal", proposal_sha), ("snapshots", snapshots_sha), ("source_files", source_sha))):
                _fault("conversion_job_input_changed", "已排队作业输入发生变化；原始文件未激活。")
            report = convert_and_verify(proposal, snapshots, source_files, output)
            registration = None
            version_id = _attempt_version(row["requested_version_id"], attempt)
            if row["register"]:
                registration = register_verified_version(version_id, row["case_id"], proposal["archive_id"],
                    proposal["archive_fingerprint"], proposal["assignments"][0]["study_uid"],
                    output, row["inputs"]["proposal"]["path"], row["inputs"]["snapshots"]["path"])
            row.update(state="succeeded", version_id=version_id, finished_utc=_utc(), updated_utc=_utc(), reason=None,
                       registered=registration is not None,
                       model_input_eligible=False, current_mri_replaced=False, inference_performed=False,
                       result={"data_role": report["data_role"], "all_voxels_compared": sum(
                           item["all_voxels_compared"] for item in report["outputs"].values()),
                           "registration_status": registration["status"] if registration else None,
                           "version_id": version_id})
            row["output_dir"] = str(output)
            _write_job(job_id, row)
            return _public(row)
        except PlanError as error:
            _finish_failure(row, error.reason)
        except (OSError, ValueError, UnicodeError, RecursionError, KeyError, IndexError):
            _finish_failure(row, "invalid_input_files")
        except Exception:
            _finish_failure(row, "conversion_failed")
        return _public(_read_job(job_id))


def _finish_failure(row, reason):
    row.update(state="failed", finished_utc=_utc(), updated_utc=_utc(), reason=reason,
               model_input_eligible=False, current_mri_replaced=False, inference_performed=False)
    _write_job(row["job_id"], row)


def retry_job(job_id, case_id=None, expected_attempt=None):
    with _file_lock(_job_file(job_id).with_name("state.lock"), blocking=True) as acquired:
        if not acquired:
            _fault("conversion_job_busy", "转换作业状态正被更新，请重试。")
        row = _read_job(job_id)
        if case_id is not None and row["case_id"] != case_id:
            _fault("conversion_job_not_found", "此病例没有该转换作业。")
        if expected_attempt is not None and row["attempt"] != expected_attempt:
            _fault("conversion_job_stale", "转换作业已更新，请刷新后重试。")
        if row["state"] not in {"failed", "interrupted"}:
            _fault("conversion_job_not_retryable", "当前作业状态不允许重试。")
        if row["attempt"] >= 8:
            _fault("conversion_job_attempt_limit", "此转换作业已达到重试次数上限。")
        row.update(state="queued", attempt=row["attempt"] + 1, updated_utc=_utc(),
                   started_utc=None, finished_utc=None, reason=None, result=None, output_dir=None)
        _write_job(job_id, row, state_lock_held=True)
    return _public(row)


def _recover_if_interrupted(job_id):
    with _run_lock(job_id, blocking=False) as acquired:
        if not acquired:
            return _public(_read_job(job_id))
        with _file_lock(_job_file(job_id).with_name("state.lock"), blocking=True) as state_acquired:
            if not state_acquired:
                return _public(_read_job(job_id))
            row = _read_job(job_id)
            if row["state"] == "running":
                row.update(state="interrupted", finished_utc=_utc(), updated_utc=_utc(),
                           reason="worker_interrupted_before_completion", model_input_eligible=False,
                           current_mri_replaced=False, inference_performed=False)
                _write_job(job_id, row, state_lock_held=True)
            return _public(row)


def prepared_job(job_id, case_id, expected_attempt):
    """Resolve only persisted server inputs; a browser supplies no file paths."""
    row = _read_job(job_id)
    if row["case_id"] != case_id:
        _fault("conversion_job_not_found", "此病例没有该转换作业。")
    if row["attempt"] != expected_attempt:
        _fault("conversion_job_stale", "转换作业已更新，请刷新后启动。")
    if row["state"] != "queued":
        _fault("conversion_job_not_startable", "只有等待执行的准备作业可以启动；失败作业请使用重试。")
    values = {}
    try:
        for key, cap in (("proposal", 4*1024*1024), ("snapshots", 16*1024*1024), ("source_files", 1024*1024)):
            value, sha = read(row["inputs"][key]["path"], cap)
            if sha != row["inputs"][key]["sha256"]:
                _fault("conversion_job_input_changed", "准备后的转换输入已经改变，请重新准备并核对。")
            values[key] = value
        plan = validate_plan(values["proposal"], values["snapshots"])
    except PlanError:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        _fault("conversion_job_input_invalid", "已准备的来源文件不可用，请重新准备并核对。")
    if plan["case_id"] != case_id:
        _fault("conversion_job_not_found", "转换计划与当前病例不一致。")
    return _public(row), plan


def submit_job(job_id):
    """Deduplicate submissions per attempt, including the executor queue wait."""
    attempt = _read_job(job_id)["attempt"]
    key = (job_id, attempt)
    with _SUBMISSIONS_GUARD:
        existing = _SUBMISSIONS.get(key)
        if existing is not None and not existing.done():
            return existing
        future = _JOB_EXECUTOR.submit(run_job, job_id, expected_attempt=attempt)
        _SUBMISSIONS[key] = future

    def forget(completed):
        with _SUBMISSIONS_GUARD:
            if _SUBMISSIONS.get(key) is completed:
                _SUBMISSIONS.pop(key, None)
    future.add_done_callback(forget)
    return future


def list_jobs(case_id=None):
    root = _root()
    if not root.exists():
        return []
    rows = []
    for path in sorted(root.glob("*/job.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        if len(rows) >= 100:
            break
        job_id = path.parent.name
        if not JOB_ID.fullmatch(job_id):
            continue
        row = _read_job(job_id)
        if case_id is not None and row["case_id"] != case_id:
            continue
        rows.append(_recover_if_interrupted(job_id))
    return rows










