"""Bounded, explicitly registered local MR derivatives -> authenticated Orthanc.

No browser paths, raw uploads, patient creation, case binding or AI activation.
The registry pins preparation and technical source/pixel review records. It is
not a clinical deidentification certification. Originals are always read-only.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import threading
import time
from uuid import uuid4

from fastapi import HTTPException
import pydicom

from app.core.config import settings
from app.core.storage import is_supported_storage_path
from app.services.dicom_viewing_derivative import PROFILE, KEEP, IDENTITY
from app.services.dicom_series import validate_series
from app.services.pacs_client import PacsClient, fail, load_config

DATA_ROOT = Path(settings.PACS_DERIVED_DIR)
ID = r'^[0-9a-f]{64}$'
_json_lock = threading.RLock()


def digest(raw): return hashlib.sha256(raw).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()


def read_json(path, limit=4*1024*1024):
    with _json_lock:
        if path.stat().st_size > limit: fail('import_record_invalid', '导入记录超过大小限制。', 409)
        return json.loads(path.read_text(encoding='utf-8-sig'))


def write_json(path, value):
    with _json_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        # Windows readers can briefly deny DELETE sharing. Serialize our own
        # readers and tolerate a bounded external read; never truncate state.json.
        for attempt in range(50):
            try:
                temporary.replace(path)
                return
            except PermissionError:
                if attempt==49: raise
                time.sleep(.01)


@contextmanager
def import_lock():
    root = Path(settings.PACS_IMPORT_JOBS_DIR).resolve()
    if not is_supported_storage_path(root): fail('import_config_invalid', '本机导入记录必须位于受支持的绝对运行路径。')
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'import.lock').open('a+b') as handle:
        if handle.tell() == 0: handle.write(b'0'); handle.flush()
        handle.seek(0)
        acquired = False
        try:
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError:
                fail('import_busy', '已有归档导入正在执行，请查看当前状态后再试。', 409)
            yield root
        finally:
            if acquired:
                handle.seek(0)
                if os.name == 'nt': msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else: fcntl.flock(handle, fcntl.LOCK_UN)


def registry():
    path = Path(settings.PACS_IMPORT_REGISTRY_FILE).resolve()
    if not is_supported_storage_path(path): fail('import_config_invalid', '本机导入登记必须位于受支持的绝对运行路径。')
    if not path.exists(): return []
    try:
        value = read_json(path, 128*1024)
        rows = value['items']
        if value['format_version'] != 1 or not isinstance(rows, list) or len(rows)>64: raise ValueError()
        if len({row['candidate_id'] for row in rows}) != len(rows): raise ValueError()
        for row in rows:
            if not re.fullmatch(ID, row['candidate_id']): raise ValueError()
            public_candidate(row)  # Also checks the public field types.
        return rows
    except Exception:
        fail('import_registry_invalid', '导入登记损坏，请由本机准备工具重新核对；没有执行导入。', 409)


def public_candidate(row):
    fields = ('candidate_id','label','instance_count','study_uid','series_uid','collection_doi','license_url')
    result = {key: row[key] for key in fields}
    if not isinstance(result['label'], str) or not 1 <= len(result['label']) <= 100: raise ValueError()
    if not isinstance(result['instance_count'], int) or not 2 <= result['instance_count'] <= 512: raise ValueError()
    result.update(scope='已核对公开MR派生资料，仅本地研究阅片', clinical_certification=False, ai_activation=False)
    return result


def candidate(candidate_id):
    if not re.fullmatch(ID, candidate_id): fail('invalid_candidate_id', '导入资料编号无效。', 422)
    for row in registry():
        if row['candidate_id'] == candidate_id: return row
    fail('import_candidate_missing', '没有找到已登记的本机导入资料。', 404)


def checked_candidate(row, config):
    try:
        raw_root = Path(row['directory'])
        root = raw_root.resolve(strict=True)
        if raw_root.is_symlink() or not root.is_relative_to(DATA_ROOT.resolve()) or root == DATA_ROOT.resolve(): raise ValueError()
        if (root/'FAILED.txt').exists(): raise ValueError()
        for name, key in [('derivative-manifest.json','manifest_sha256'),('preparation-report.json','report_sha256')]:
            if digest((root/name).read_bytes()) != row[key]:
                fail('import_candidate_changed', '准备记录已变化，请重新核对来源与像素；未开始导入。', 409)
        review = Path(row['review_record']).resolve(strict=True)
        if not is_supported_storage_path(review) or digest(review.read_bytes()) != row['review_sha256']:
            fail('import_review_changed', '技术复核记录已变化，请重新登记；未开始导入。', 409)
        manifest, report = read_json(root/'derivative-manifest.json'), read_json(root/'preparation-report.json')
        if report.get('format_version') == 2:
            from app.services.public_mr_preparation import validate_prepared_review
            validate_prepared_review(root, manifest, report)
        if (manifest['profile'] != PROFILE or report['profile'] != PROFILE or report['status'] != 'prepared_and_verified'
                or report['license_url'] != 'https://creativecommons.org/licenses/by/4.0/'
                or report['license_url'] != row['license_url'] or report['collection_doi'] != row['collection_doi']
                or manifest['data_role'] != 'public-clinical-derived-local-viewing-only'
                or report['ai_activation'] is not False or report['clinical_deidentification_certified'] is not False): raise ValueError()
        records = manifest['instances']
        if (not 2 <= len(records) <= 512 or len(records) != manifest['instance_count']
                or len(records) != row['instance_count'] or manifest['study_uid'] != row['study_uid']
                or manifest['series_uid'] != row['series_uid']): raise ValueError()
        paths, metadata, total = [], [], 0
        for record in records:
            path = (root/'instances'/record['derived_filename']).resolve(strict=True)
            if path.parent != (root/'instances').resolve() or path.suffix != '.dcm' or path.stat().st_size > 64*1024*1024: raise ValueError()
            raw = path.read_bytes(); total += len(raw)
            if total > 256*1024*1024: raise ValueError()
            if digest(raw) != record['derived_sha256']:
                fail('import_file_changed', 'DICOM文件与核对记录不一致，未开始导入。', 409)
            ds = pydicom.dcmread(io.BytesIO(raw))
            if (str(ds.StudyInstanceUID) != manifest['study_uid'] or str(ds.SeriesInstanceUID) != manifest['series_uid']
                    or str(ds.FrameOfReferenceUID) != manifest['frame_uid'] or str(ds.SOPInstanceUID) != record['derived_sop_uid']
                    or str(ds.PatientID) != manifest['patient_id'] or str(ds.PatientName) != manifest['patient_id']
                    or str(ds.file_meta.MediaStorageSOPInstanceUID) != str(ds.SOPInstanceUID)
                    or str(ds.file_meta.TransferSyntaxUID) != str(pydicom.uid.ExplicitVRLittleEndian)
                    or str(ds.DeidentificationMethod) != PROFILE or str(ds.PatientIdentityRemoved) != 'YES'
                    or str(ds.get('BurnedInAnnotation','')) == 'YES'
                    or not {e.keyword for e in ds}.issubset(KEEP | IDENTITY)
                    or any(e.tag.is_private or e.VR == 'SQ' or (e.VR in ('DA','DT','TM') and str(e.value)) for e in ds)
                    or digest(ds.PixelData) != record['pixel_sha256']): raise ValueError()
            ds.pixel_array  # Decode the exact bytes once before the first archive write.
            del ds.PixelData
            metadata.append(ds.to_json_dict())
            paths.append((record, path))
        if len({p for _,p in paths}) != len(paths) or set((root/'instances').iterdir()) != {p for _,p in paths}: raise ValueError()
        validate_series(config, metadata, manifest['study_uid'], manifest['series_uid'], [r['derived_sop_uid'] for r in records])
        return manifest, paths
    except HTTPException:
        raise
    except Exception:
        fail('import_candidate_invalid', '导入资料不满足已登记的公开MR派生、像素或空间契约；没有开始导入。', 409)


def state_files():
    return Path(settings.PACS_IMPORT_JOBS_DIR).glob('*/state.json')


def public_state(state):
    return {key:state.get(key) for key in ('id','candidate_id','archive_id','state','created_utc','updated_utc',
            'total','verified','stored_new','already_stored','error','error_reason','study_uid','series_uid','elapsed_seconds')}


def current(candidate_id, config=None):
    config = config or load_config()
    try:
        rows = [read_json(path) for path in state_files()]
        rows = [row for row in rows if row['candidate_id']==candidate_id and row['archive_fingerprint']==config.endpoint_fingerprint
                and row['archive_id']==config.archive_id]
        return public_state(max(rows,key=lambda r:r['created_utc'])) if rows else None
    except Exception:
        fail('import_state_invalid','导入回执无法读取；请保留记录并由本机维护检查，不能冒报完成。',409)


def save_state(directory, state):
    state['updated_utc'] = now()
    write_json(directory/'state.json', state)


def execute(candidate_id, acknowledge):
    if acknowledge is not True: fail('import_acknowledgement_required', '请确认只导入已核对的本机资料，且此操作不自动关联病例或提交AI。', 422)
    row = candidate(candidate_id)
    config = load_config()
    if not config.expected_database_server_identifier:
        fail('import_archive_unpinned', '请先固定本地归档服务标识再导入。', 409)
    try:
        context = import_lock()
        with context as root:
            manifest, paths = checked_candidate(row, config)
            started = datetime.now(timezone.utc)
            state = dict(id=uuid4().hex, candidate_id=candidate_id, archive_id=config.archive_id,
                         archive_fingerprint=config.endpoint_fingerprint, state='queued', created_utc=now(),
                         total=len(paths), verified=0, stored_new=0, already_stored=0, error=None, error_reason=None,
                         study_uid=manifest['study_uid'], series_uid=manifest['series_uid'], receipts=[])
            directory = root/state['id']; directory.mkdir()
            save_state(directory,state)
            try:
                state['state']='running'; save_state(directory,state)
                with PacsClient(config) as archive:
                    if archive.version != '1.13.0': fail('import_archive_version', '当前导入仅验证Orthanc1.13.0，请核对版本。', 409)
                    for record, path in paths:
                        raw = path.read_bytes()
                        if digest(raw) != record['derived_sha256']: fail('import_file_changed', '导入期间文件变化，已停止；部分实例可能已归档。',409)
                        response=archive.http.post('/instances',content=raw,headers={'Content-Type':'application/dicom','Expect':''})
                        if response.status_code != 200: fail('import_upload_failed', '归档未接受实例，已停止；可在服务恢复后重试。',502)
                        receipt=response.json(); resource=receipt.get('ID','')
                        if receipt.get('Status') not in ('Success','AlreadyStored') or not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{8}){4}',resource):
                            fail('import_receipt_invalid','归档回执无效，已停止；没有冒报完成。',502)
                        stored=archive.http.get('/instances/'+resource+'/file')
                        if stored.status_code!=200 or digest(stored.content)!=record['derived_sha256']:
                            fail('import_stored_bytes_mismatch','归档回读字节不一致，已停止；原UID可能已对应其他内容。',409)
                        state['receipts'].append(dict(orthanc_id=resource,sop_uid=record['derived_sop_uid'],
                              sha256=record['derived_sha256'],status=receipt['Status']))
                        state['verified']+=1
                        state['stored_new' if receipt['Status']=='Success' else 'already_stored']+=1
                        save_state(directory,state)
                    if archive._json('/system',dicom=False).get('DatabaseServerIdentifier')!=config.expected_database_server_identifier:
                        fail('import_archive_changed','导入期间归档标识变化，拒绝标为完成。',409)
                # Recheck source/review pins, files and current destination after all writes.
                checked_candidate(row,config)
                if load_config().endpoint_fingerprint != config.endpoint_fingerprint:
                    fail('import_archive_changed','导入期间归档配置变化，拒绝标为完成。',409)
                state['state']='succeeded'
            except Exception as exc:
                state['state']='failed'
                state['error_reason']=exc.detail['reason'] if isinstance(exc,HTTPException) and isinstance(exc.detail,dict) else 'import_transport_failed'
                state['error']=exc.detail['message'] if isinstance(exc,HTTPException) and isinstance(exc.detail,dict) else '导入通信或记录核对失败，已停止；部分实例可能已归档，可重试并逐份回读。'
            state['elapsed_seconds']=round((datetime.now(timezone.utc)-started).total_seconds(),3)
            save_state(directory,state)
            return public_state(state)
    except HTTPException as exc:
        if isinstance(exc.detail,dict) and exc.detail.get('reason')=='import_busy':
            active=current(candidate_id,config)
            if active and active['state'] in ('queued','running'): return active
        raise


def recover_interrupted():
    if not Path(settings.PACS_IMPORT_JOBS_DIR).exists(): return
    try:
        with import_lock():
            for path in state_files():
                try:
                    state=read_json(path)
                    if not isinstance(state,dict) or state.get('state') not in ('queued','running','succeeded','failed'):
                        raise ValueError('Invalid import state')
                except (HTTPException,ValueError,OSError):
                    import warnings
                    warnings.warn('PACS import receipt unreadable; original retained for local repair')
                    continue
                if state['state'] in ('queued','running'):
                    state.update(state='failed',error_reason='import_interrupted',error='服务重启使导入中断；已归档实例保留，重试将按原字节逐份核对。')
                    save_state(path.parent,state)
    except HTTPException as exc:
        if not isinstance(exc.detail,dict) or exc.detail.get('reason')!='import_busy': raise
