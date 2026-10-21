"""Authenticated version-bound DICOM role-review journal. It never activates AI input."""
import hashlib,json,os,threading,uuid
from datetime import datetime,timezone
from pathlib import Path
from app.core.config import settings
from app.core.storage import is_supported_storage_path
from app.services.dicom_conversion_registry import entry_inputs
from app.services.dicom_input_plan import ROLES,validate_plan
from app.services.pacs_client import fail
_LOCK=threading.RLock();_MAX_BYTES=4*1024*1024;_MAX_RECORDS=1024;_FORMAT="dicom-conversion-role-review-journal-v1"
def _canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)
def _journal_path():
    index=Path(settings.DICOM_CONVERSION_INDEX_FILE).absolute()
    if not is_supported_storage_path(index) or index.resolve()!=index:fail("conversion_review_storage_invalid","角色审核记录必须位于受支持的 E 盘运行目录。",503)
    path=index.with_name("dicom-conversion-role-reviews.json")
    if not is_supported_storage_path(path) or path.resolve()!=path:fail("conversion_review_storage_invalid","角色审核记录路径不符合本地运行约束。",503)
    return path
def _read(path):
    if not path.exists():return {"format":_FORMAT,"records":[]}
    try:
        raw=path.read_bytes()
        if len(raw)>_MAX_BYTES:raise ValueError()
        value=json.loads(raw.decode("utf-8-sig"))
        if not isinstance(value,dict) or set(value)!={"format","records"} or value["format"]!=_FORMAT or not isinstance(value["records"],list) or len(value["records"])>_MAX_RECORDS:raise ValueError()
        return value
    except Exception:fail("conversion_review_journal_invalid","角色审核历史文件损坏或超出上限；未覆盖原记录。",503)
def _write(path,doc):
    raw=(_canonical(doc)+"\n").encode("utf-8")
    if len(raw)>_MAX_BYTES:fail("conversion_review_journal_full","角色审核历史达到本地容量上限；原记录保持不变。",507)
    temp=path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
    try:
        with temp.open("xb") as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        try:temp.unlink(missing_ok=True)
        except OSError:pass
def describe(entry):
    try:proposal,snapshots=entry_inputs(entry);plan=validate_plan(proposal,snapshots)
    except Exception:fail("conversion_role_source_invalid","转换角色声明或锚定来源无法核对。",409)
    rows=[]
    for role in ROLES:
        s=plan["sources"][role];e=s["role_declaration"]
        rows.append({"role":role,"study_uid":s["study_uid"],"series_uid":s["series_uid"],
          "series_metadata_sha256":s["series_metadata_sha256"],"frame_of_reference_uid":s["frame_of_reference_uid"],
          "geometry_sha256":hashlib.sha256(_canonical(s["geometry"]).encode()).hexdigest(),
          "evidence":{"basis":e["basis"],"evidence_sha256":e["evidence_sha256"],"evidence_reference":e["evidence_reference"],"confirmed_at":e["confirmed_at"]}})
    return {"plan_revision":plan["plan_revision"],"data_role":plan["data_role"],"assignments":rows,
      "assignment_set_sha256":hashlib.sha256(_canonical(rows).encode()).hexdigest(),
      "review_allowed":plan["data_role"]=="dicom-metadata-snapshot","role_confirmation_status":"awaiting_authenticated_local_review",
      "model_input_eligible":False,"current_mri_replaced":False}
from contextlib import contextmanager
@contextmanager
def journal_lock():
    """Serialize version approval reads with activation commit in this process."""
    with _LOCK:
        yield

def history(entry):
    binding={"version_id":entry.version_id,"report_sha256":entry.report_sha256,"proposal_sha256":entry.proposal_sha256,"snapshots_sha256":entry.snapshots_sha256}
    with _LOCK:doc=_read(_journal_path())
    return [r for r in doc["records"] if r.get("binding")==binding]
def record(entry,decision,plan_revision,assignment_set_sha256,identity,source_check=None):
    if decision not in ("approve","reject"):fail("invalid_role_review_decision","角色审核决定无效。",422)
    view=describe(entry)
    if view["plan_revision"]!=plan_revision or view["assignment_set_sha256"]!=assignment_set_sha256:fail("conversion_role_review_stale","角色声明或转换版本已变化，请重新打开并核对。",409)
    if decision=="approve":
        if not view["review_allowed"]:fail("synthetic_conversion_not_reviewable","合成工程夹具不能取得真实DICOM角色审批。",409)
        if not isinstance(source_check,dict) or source_check.get("status")!="matched_at_check" or source_check.get("data_role")!="dicom-metadata-snapshot" or source_check.get("plan_revision")!=plan_revision or source_check.get("report_sha256")!=entry.report_sha256 or source_check.get("archive_id")!=entry.archive_id or source_check.get("archive_fingerprint")!=entry.archive_fingerprint:
            fail("conversion_archive_review_required","审批前必须完成当前归档原字节与元数据核对。",409)
    user=identity.get("user") if isinstance(identity,dict) else None
    if not isinstance(user,dict) or user.get("role")!="doctor" or not isinstance(user.get("id"),str) or not isinstance(user.get("username"),str):fail("authenticated_local_doctor_required","此操作需要有效的本地医生角色会话。",403)
    source={k:source_check.get(k) for k in ("status","completed_utc","instances_checked","raw_byte_passes")} if source_check else None
    row={"review_id":uuid.uuid4().hex,"binding":{"version_id":entry.version_id,"report_sha256":entry.report_sha256,"proposal_sha256":entry.proposal_sha256,"snapshots_sha256":entry.snapshots_sha256},
      "plan_revision":plan_revision,"assignment_set_sha256":assignment_set_sha256,"decision":decision,"source_check":source,
      "reviewer":{"id":user["id"],"username":user["username"],"display_name":user.get("display_name",user["username"]),"role":"doctor",
      "authentication_method":identity.get("authentication_method"),"professional_credential_verified":False},
      "reviewed_utc":datetime.now(timezone.utc).isoformat(),"model_input_eligible":False,"current_mri_replaced":False}
    with _LOCK:
        path=_journal_path();doc=_read(path)
        if len(doc["records"])>=_MAX_RECORDS:fail("conversion_review_journal_full","角色审核历史达到本地记录上限；原记录保持不变。",507)
        doc["records"].append(row);_write(path,doc)
    return row


