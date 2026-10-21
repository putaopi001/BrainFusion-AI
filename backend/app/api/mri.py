from pathlib import Path
import json
from uuid import uuid4
from typing import Literal
import nibabel as nib

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.mri import MRI
from app.schemas.annotation import AnnotationCreate
from app.services import annotation_service
from app.services import mri_service
from app.services.mri_preview_service import generate_mri_previews
from app.services.radiomics_service import extract_radiomics
from app.services.artifact_integrity import analysis_problem
from app.models.analysis_run import AnalysisRun
from app.core.storage import resolve_stored_path, public_upload_path
from app.models.world_measurement import MRIWorldMeasurement
from app.schemas.world_measurement import WorldMeasurementCreate, ViewStateCreate
from app.services import world_measurement_service, view_state_service


router = APIRouter(prefix="/mri", tags=["mri"])
BACKEND_DIR = Path(__file__).resolve().parents[2]
SequenceKey = Literal['t1c', 't1n', 't2w', 't2f']


def _view_source(mri, sequence):
    try:
        source, selected, available = mri_service.resolve_view_sequence(mri, sequence)
    except Exception as error:
        raise HTTPException(422, 'Four-sequence viewing unavailable: ' + str(error))
    if not source:
        raise HTTPException(404, 'MRI file is missing')
    return source, selected, available


def _get_latest_mri(case_id: int, db: Session) -> MRI:
    mri = (
        db.query(MRI)
        .filter(MRI.case_id == case_id)
        .order_by(MRI.id.desc())
        .first()
    )
    if not mri:
        raise HTTPException(status_code=404, detail="MRI not found")
    return mri


def _source_lineage_summary(mri):
    if not mri.source_provenance_json:
        return None
    try:
        value = json.loads(mri.source_provenance_json)
        return {key: value.get(key) for key in ("format", "conversion_version_id", "plan_revision",
                "model_input_contract", "archive_id", "study_uid", "activated_utc", "inference_performed")}
    except (ValueError, TypeError):
        return {"integrity_status": "invalid"}


def _preview_urls_for(slice_path: str | None) -> list[str]:
    preview_urls: list[str] = []
    preview_views = {"axial": [], "coronal": [], "sagittal": []}
    if slice_path:
        path = resolve_stored_path(slice_path)
        preview_dir = path.parent
        if preview_dir.exists():
            for img in preview_dir.glob("*.png"):
                url = public_upload_path(img)
                if not url:
                    continue
                preview_urls.append(url)
                name = img.name.lower()
                if "axial" in name:
                    preview_views["axial"].append(url)
                elif "coronal" in name:
                    preview_views["coronal"].append(url)
                elif "sagittal" in name:
                    preview_views["sagittal"].append(url)
    for key in preview_views:
        preview_views[key].sort()
    return preview_urls, preview_views


@router.get("/{case_id}")
def get_mri(case_id: int, db: Session = Depends(get_db)):
    mri = _get_latest_mri(case_id, db)
    preview_urls, preview_views = _preview_urls_for(mri.slice_path)
    problem = analysis_problem(mri, db.get(AnalysisRun, mri.analysis_run_id) if mri.analysis_run_id else None) if mri.segmentation_source == 'model' else None

    return {
        "code": 200,
        "data": {
            "id": mri.id,
            "filename": mri.filename,
            "input_source": mri.input_source if mri.input_source else "legacy",
            "file_url": mri.web_path,
            "slice_url": preview_urls[0] if preview_urls else None,
            "preview_urls": preview_urls,
            "preview_views": preview_views,
            "has_preview": len(preview_urls) > 0,
            "modality": mri.modality,
            "status": mri.status,
            "display_status": mri_service.compute_display_status(mri),
            "doctor_verified": bool(mri.doctor_verified and not problem),
            "analysis_stale": bool(problem), "stale_reason": problem,
            "volume_ready": bool(mri.filepath),
            "preview_error": mri.preview_error,
            "sequences": list(json.loads(mri.sequences_json)) if mri.sequences_json else [],
            "source_provenance": _source_lineage_summary(mri),
            "analysis_run_id": mri.analysis_run_id,
            "verified_run_id": mri.verified_run_id,
        },
    }


@router.post("/{case_id}/preview")
def regenerate_preview(case_id: int, db: Session = Depends(get_db)):
    mri = _get_latest_mri(case_id, db)
    source = mri_service.resolve_filepath(mri)
    if not source:
        raise HTTPException(status_code=404, detail="MRI file is missing")

    mri.status = "processing"
    db.commit()
    try:
        preview_paths = generate_mri_previews(source, source.parent / "previews", mri.id)
        mri.slice_path = str(preview_paths[0])
        mri.preview_error = None
        mri.status = "preview_ready"
        db.commit()
        return {"code": 200, "preview_count": len(preview_paths), "status": mri.status}
    except Exception as error:
        db.rollback()
        mri.preview_error = f"{type(error).__name__}: {error}"
        mri.status = "failed"
        db.commit()
        raise HTTPException(status_code=422, detail=mri.preview_error)


@router.get("/{case_id}/volume")
def get_volume_metadata(case_id: int, sequence: SequenceKey | None = None, db: Session = Depends(get_db)):
    mri = _get_latest_mri(case_id, db)
    source, selected, available = _view_source(mri, sequence)
    try:
        metadata = dict(mri_service.get_volume_metadata(source))
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"{type(error).__name__}: {error}")
    metadata["id"] = mri.id
    metadata["filename"] = mri.filename
    metadata['sequence'] = selected
    metadata['available_sequences'] = available
    source_stat = source.stat()
    metadata['source_revision'] = f'{source_stat.st_size}-{source_stat.st_mtime_ns}'
    metadata['nifti_url'] = f'/mri/{case_id}/nifti?mri_id={mri.id}&revision={metadata["source_revision"]}' + (f'&sequence={selected}' if selected else '')
    metadata['spatial_constraint'] = 'Four sequences must already share shape/affine, orthogonal orientation and 1 mm spacing. No automatic registration or resampling.' if available else 'Legacy single volume; sequence identity unavailable.'
    return {"code": 200, "data": metadata}


@router.get("/{case_id}/nifti")
def get_view_nifti(case_id: int, mri_id: int, revision: str, sequence: SequenceKey | None = None,
                   db: Session = Depends(get_db)):
    """Original bytes for the validated sequence, never a resampled preview."""
    mri = _get_latest_mri(case_id, db)
    if mri.id != mri_id:
        raise HTTPException(409, 'MRI version changed; reload the workstation')
    source, _, _ = _view_source(mri, sequence)
    source_stat = source.stat()
    if revision != f'{source_stat.st_size}-{source_stat.st_mtime_ns}':
        raise HTTPException(409, 'MRI file changed; reload the workstation')
    return FileResponse(source, media_type='application/octet-stream',
                        headers={'Cache-Control': 'no-store'})


@router.get("/{case_id}/slice/{view}/{index}")
def get_slice_png(
    case_id: int,
    view: str,
    index: int,
    ww: float | None = Query(default=None),
    wl: float | None = Query(default=None),
    sequence: SequenceKey | None = None,
    db: Session = Depends(get_db),
):
    if view not in mri_service.VIEW_AXIS:
        raise HTTPException(status_code=404, detail="view must be axial|coronal|sagittal")
    mri = _get_latest_mri(case_id, db)
    source, _, _ = _view_source(mri, sequence)

    if ww is None or wl is None:
        meta = mri_service.get_volume_metadata(source)
        default_ww = meta["display_max"] - meta["display_min"]
        default_wl = (meta["display_max"] + meta["display_min"]) / 2.0
        ww = ww if ww is not None else default_ww
        wl = wl if wl is not None else default_wl

    try:
        png = mri_service.render_slice_png(source, view, index, float(ww), float(wl))
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"{type(error).__name__}: {error}")
    return StreamingResponse(iter([png]), media_type="image/png")


@router.get("/{case_id}/segmentation")
def get_segmentation_info(case_id: int, db: Session = Depends(get_db)):
    mri = _get_latest_mri(case_id, db)
    if mri.segmentation_source == 'model':
        problem = analysis_problem(mri, db.get(AnalysisRun, mri.analysis_run_id) if mri.analysis_run_id else None)
        if problem:
            return {'code': 200, 'data': {'available': False, 'source': 'unavailable', 'stale': True,
                    'analysis_run_id': mri.analysis_run_id, 'stale_reason': problem, 'disclaimer': '模型分割已失效：' + problem}}
    source = mri_service.resolve_filepath(mri)
    if not source:
        raise HTTPException(status_code=404, detail="MRI file is missing")
    try:
        mask_path = mri_service.ensure_segmentation_mask(mri, source)
        _, _, _ = mri_service.load_volume(source)
        mask = mri_service.load_volume(mask_path)[0]
        return {
            "code": 200,
            "data": {
                "available": True,
                "source": mri.segmentation_source or "unavailable",
                "analysis_run_id": mri.analysis_run_id,
                "mask_url": public_upload_path(mask_path),
                "disclaimer": "真实模型输出，需医生核对。" if mri.segmentation_source == "model" else "上传的参考掩膜，非模型预测。",
                "shape": list(mask.shape),
                "views": {view: int(mask.shape[axis]) for view, axis in mri_service.VIEW_AXIS.items()},
            },
        }
    except FileNotFoundError:
        return {"code": 200, "data": {"available": False, "source": "unavailable"}}
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"{type(error).__name__}: {error}")


@router.post("/{case_id}/segmentation")
async def upload_segmentation(case_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    mri = _get_latest_mri(case_id, db)
    source = mri_service.resolve_filepath(mri)
    if not source:
        raise HTTPException(status_code=404, detail="MRI file is missing")
    if not file.filename or not file.filename.lower().endswith((".nii", ".nii.gz")):
        raise HTTPException(status_code=415, detail="only .nii/.nii.gz mask files are supported")

    from app.api.analysis import ensure_idle, submission_lock
    from app.services.segmentation_metrics import validate_mask
    ensure_idle(case_id, db)
    mask_path = source.parent / ("uploaded_mask_" + uuid4().hex + ".nii.gz")
    content = await file.read(128 * 1024**2 + 1)
    await file.close()
    if len(content) > 128 * 1024**2:
        raise HTTPException(413, "Mask exceeds 128 MiB")
    if not content.startswith(b"\x1f\x8b"):
        mask_path = mask_path.with_suffix("")
    mask_path.write_bytes(content)

    try:
        mask_shape = list(validate_mask(nib.load(str(mask_path)), nib.load(str(source))).shape)
    except HTTPException:
        raise
    except Exception as error:
        mask_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"invalid mask file: {error}")

    with submission_lock:
        db.expire_all()
        ensure_idle(case_id, db)
        mri.segmentation_source = "uploaded"
        mri.segmentation_path = str(mask_path)
        mri.doctor_verified, mri.verified_run_id, mri.analysis_run_id = False, None, None
        db.commit()
        return {"code": 200, "message": "segmentation saved", "data": {"shape": mask_shape}}


@router.get("/{case_id}/mask/{view}/{index}")
def get_mask_png(case_id: int, view: str, index: int, version: str | None = None, db: Session = Depends(get_db)):
    if view not in mri_service.VIEW_AXIS:
        raise HTTPException(status_code=404, detail="view must be axial|coronal|sagittal")
    mri = _get_latest_mri(case_id, db)
    if mri.segmentation_source == 'model':
        problem = analysis_problem(mri, db.get(AnalysisRun, mri.analysis_run_id) if mri.analysis_run_id else None)
        if problem or (version is not None and version != mri.analysis_run_id):
            raise HTTPException(409, problem or 'Displayed mask version is no longer current; refresh the case.')
    source = mri_service.resolve_filepath(mri)
    if not source:
        raise HTTPException(status_code=404, detail="MRI file is missing")
    try:
        mask_path = mri_service.ensure_segmentation_mask(mri, source)
        png = mri_service.render_mask_png(mask_path, view, index)
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"{type(error).__name__}: {error}")
    return StreamingResponse(iter([png]), media_type="image/png")


@router.get("/{case_id}/voxel")
def get_voxel_value(
    case_id: int,
    view: str,
    index: int,
    nx: float,
    ny: float,
    sequence: SequenceKey | None = None,
    db: Session = Depends(get_db),
):
    if view not in mri_service.VIEW_AXIS:
        raise HTTPException(status_code=404, detail="view must be axial|coronal|sagittal")
    mri = _get_latest_mri(case_id, db)
    source, selected, _ = _view_source(mri, sequence)
    try:
        result = mri_service.get_voxel_value(source, view, index, float(nx), float(ny))
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"{type(error).__name__}: {error}")
    return {"code": 200, "data": {**result, 'sequence': selected}}


@router.get("/{case_id}/radiomics")
def get_radiomics(case_id: int, db: Session = Depends(get_db)):
    mri = _get_latest_mri(case_id, db)
    source = mri_service.resolve_filepath(mri)
    if not source:
        raise HTTPException(status_code=404, detail="MRI file is missing")
    try:
        features = extract_radiomics(source)
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"{type(error).__name__}: {error}")
    return {"code": 200, "data": features}


@router.post("/{case_id}/verify")
def verify_mri(case_id: int, run_id: str = Query(...), db: Session = Depends(get_db)):
    mri = _get_latest_mri(case_id, db)
    from app.models.analysis_run import AnalysisRun
    run = db.get(AnalysisRun, run_id)
    if (run_id != mri.analysis_run_id or not run or run.state != "succeeded"
            or mri.segmentation_source != "model" or run.case_id != case_id or run.mri_id != mri.id):
        raise HTTPException(409, "Only the current successful model result can be verified")
    problem = analysis_problem(mri, run)
    if problem:
        raise HTTPException(409, problem)
    mri.doctor_verified = True
    mri.verified_run_id = run_id
    db.commit()
    return {"code": 200, "message": "AI result verified", "data": {"doctor_verified": True}}


@router.get("/{case_id}/annotations")
def get_annotations(case_id: int, db: Session = Depends(get_db)):
    mri = _get_latest_mri(case_id, db)
    items = annotation_service.list_annotations(db, mri.id)
    return {"code": 200, "data": [annotation_service.serialize_annotation(item) for item in items]}


@router.get("/{case_id}/measurements")
def get_world_measurements(case_id: int, db: Session = Depends(get_db)):
    return {'code': 200, 'data': world_measurement_service.list_measurements(_get_latest_mri(case_id, db), db)}


@router.get("/{case_id}/view-state")
def get_cornerstone_view_state(case_id: int, db: Session = Depends(get_db)):
    return {'code': 200, 'data': view_state_service.latest_view(_get_latest_mri(case_id, db), db)}


@router.post("/{case_id}/view-state")
def save_cornerstone_view_state(case_id: int, payload: ViewStateCreate, db: Session = Depends(get_db)):
    return {'code': 200, 'data': view_state_service.save_view(_get_latest_mri(case_id, db), db, payload)}


@router.post("/{case_id}/measurements")
def create_world_measurement(case_id: int, payload: WorldMeasurementCreate, db: Session = Depends(get_db)):
    return {'code': 200, 'data': world_measurement_service.save_measurement(_get_latest_mri(case_id, db), db, payload)}


@router.delete("/{case_id}/measurements/{measurement_id}")
def delete_world_measurement(case_id: int, measurement_id: int, mri_id: int, db: Session = Depends(get_db)):
    mri = _get_latest_mri(case_id, db)
    if mri_id != mri.id:
        raise HTTPException(409, 'MRI version changed; reopen the workstation')
    item = db.query(MRIWorldMeasurement).filter_by(id=measurement_id, mri_id=mri.id, case_id=case_id).first()
    if item is None:
        raise HTTPException(404, 'measurement not found')
    db.delete(item)
    db.commit()
    return {'code': 200, 'message': 'measurement deleted'}


@router.post("/{case_id}/annotations")
def create_annotation(case_id: int, payload: AnnotationCreate, db: Session = Depends(get_db)):
    mri = _get_latest_mri(case_id, db)
    annotation = annotation_service.create_annotation(db, mri.id, case_id, payload)
    return {"code": 200, "data": {"id": annotation.id}}


@router.delete("/{case_id}/annotations/{annotation_id}")
def delete_annotation(case_id: int, annotation_id: int, db: Session = Depends(get_db)):
    mri = _get_latest_mri(case_id, db)
    annotation = annotation_service.delete_annotation(db, mri.id, annotation_id)
    if not annotation:
        raise HTTPException(status_code=404, detail="annotation not found")
    return {"code": 200, "message": "annotation deleted"}


@router.delete("/{case_id}/annotations")
def delete_all_annotations(case_id: int, db: Session = Depends(get_db)):
    mri = _get_latest_mri(case_id, db)
    count = annotation_service.delete_all_annotations(db, mri.id)
    return {"code": 200, "message": f"deleted {count} annotations", "data": {"deleted": count}}
