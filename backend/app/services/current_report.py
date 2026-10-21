"""Resolve only reports bound to the current successful model analysis."""
from app.models.analysis_run import AnalysisRun
from app.models.report import Report
from app.services.artifact_integrity import analysis_problem


def current_model_report(mri, db):
    if not mri or not mri.analysis_run_id or mri.segmentation_source != "model":
        return None
    run = db.get(AnalysisRun, mri.analysis_run_id)
    if (not run or run.state != "succeeded" or run.mri_id != mri.id
            or run.case_id != mri.case_id or not run.result_json):
        return None
    if analysis_problem(mri, run):
        return None
    return (db.query(Report)
            .filter(Report.case_id == mri.case_id, Report.analysis_run_id == run.id)
            .order_by(Report.id.desc()).first())
