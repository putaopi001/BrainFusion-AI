"""Single local worker, persistent job records and subprocess GPU isolation."""
import json
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.database import SessionLocal
from app.models.analysis_run import AnalysisRun
from app.models.case import Case
from app.models.mri import MRI
from app.models.report import Report
from app.services.segmentation_metrics import region_volumes
from app.services.worker_error import worker_failure
from app.core.time import utc_iso

BACKEND = Path(__file__).resolve().parents[2]
executor = ThreadPoolExecutor(max_workers=1)
submission_lock = threading.Lock()


def serialize(run):
    metadata_error = None
    try:
        result = json.loads(run.result_json) if run.result_json else None
    except (ValueError, TypeError):
        result, metadata_error = None, 'Invalid saved analysis metadata; historical record retained.'
    return {"id": run.id, "case_id": run.case_id, "state": run.state,
            "result": result,
            "error": metadata_error or run.error, "created_time": utc_iso(run.created_time),
            "finished_time": utc_iso(run.finished_time)}


def execute(run_id):
    db = SessionLocal()
    try:
        run = db.get(AnalysisRun, run_id)
        if run is None or run.state != "queued":
            return
        run.state = "running"
        db.commit()
        request = json.loads(run.request_json)
        directory = Path(request["output_dir"])
        directory.mkdir(parents=True, exist_ok=True)
        request_file = directory / "request.json"
        request_file.write_text(json.dumps(request, indent=2), encoding="utf-8")
        with (directory / "worker.log").open("w", encoding="utf-8") as log:
            completed = subprocess.run([sys.executable, str(BACKEND / "tools/run_segmentation.py"),
                                        "--request", str(request_file)], cwd=BACKEND,
                                       stdout=log, stderr=log, timeout=1200)
        if completed.returncode:
            raise RuntimeError(worker_failure(directory / 'worker.log', 'Segmentation worker'))
        result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
        expected_input_sha256 = request.get("expected_input_sha256")
        if expected_input_sha256 is not None and result.get("input_sha256") != expected_input_sha256:
            raise RuntimeError("Inference input bytes no longer match the reviewed DICOM conversion")
        result["volumes_ml"] = region_volumes(result["mask_path"])
        mri = db.get(MRI, run.mri_id)
        if mri.analysis_run_id != run.id:
            raise RuntimeError("MRI changed during inference; result preserved but not applied")
        mri.segmentation_path = result["mask_path"]
        mri.segmentation_source = "model"
        mri.status = "analyzed"
        mri.doctor_verified = False
        mri.verified_run_id = None
        case = db.get(Case, run.case_id)
        case.status = "analyzed"
        summary = ["真实预训练模型：" + result["model"], "分析版本：" + run.id,
                   "区域体积 (mL)：" + json.dumps(result["volumes_ml"], ensure_ascii=False),
                   "此结果为分割，不提供肿瘤分型概率或生存预测。"]
        db.add(Report(case_id=run.case_id, analysis_run_id=run.id, risk_level="unavailable",
                      summary=json.dumps(summary, ensure_ascii=False),
                      recommendation=json.dumps(["请医生核对分割边界和原始影像。"], ensure_ascii=False)))
        run.result_json = json.dumps(result, ensure_ascii=False)
        run.state = "succeeded"
        run.finished_time = datetime.utcnow()
        db.commit()
    except Exception as error:
        db.rollback()
        run = db.get(AnalysisRun, run_id)
        if run:
            run.state, run.error, run.finished_time = "failed", str(error), datetime.utcnow()
            mri = db.get(MRI, run.mri_id)
            if mri and mri.analysis_run_id == run.id:
                mri.status = "failed"
            db.commit()
    finally:
        db.close()


def recover_interrupted_jobs():
    # Single-process prototype: restart explicitly fails queued/running jobs,
    # preserving logs and allowing a user-visible retry, never false success.
    db = SessionLocal()
    try:
        for run in db.query(AnalysisRun).filter(AnalysisRun.state.in_(["queued", "running"])).all():
            run.state, run.error = "failed", "Service restarted; please retry this run"
            run.finished_time = datetime.utcnow()
            mri = db.get(MRI, run.mri_id)
            if mri and mri.analysis_run_id == run.id:
                mri.status = "failed"
        db.commit()
    finally:
        db.close()
