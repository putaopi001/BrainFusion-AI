from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.mri import MRI
from app.schemas.annotation import AnnotationCreate
from app.services import annotation_service
from app.services import mri_service
from app.services.mri_preview_service import generate_mri_previews
from app.services.radiomics_service import extract_radiomics


router = APIRouter(prefix="/mri", tags=["mri"])
BACKEND_DIR = Path(__file__).resolve().parents[2]


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


def _preview_urls_for(slice_path: str | None) -> list[str]:
    preview_urls: list[str] = []
    preview_views = {"axial": [], "coronal": [], "sagittal": []}
    if slice_path:
        path = Path(slice_path)
        if not path.is_absolute():
            path = BACKEND_DIR / path
        preview_dir = path.parent
        if preview_dir.exists():
            for img in preview_dir.glob("*.png"):
                url = "/" + img.relative_to(BACKEND_DIR).as_posix()
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

    return {
        "code": 200,
        "data": {
            "id": mri.id,
            "filename": mri.filename,
            "file_url": mri.web_path,
            "slice_url": preview_urls[0] if preview_urls else None,
            "preview_urls": preview_urls,
            "preview_views": preview_views,
            "has_preview": len(preview_urls) > 0,
            "modality": mri.modality,
            "status": mri.status,
            "display_status": mri_service.compute_display_status(mri),
            "doctor_verified": bool(mri.doctor_verified),
            "volume_ready": bool(mri.filepath),
            "preview_error": mri.preview_error,
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
def get_volume_metadata(case_id: int, db: Session = Depends(get_db)):
    mri = _get_latest_mri(case_id, db)
    source = mri_service.resolve_filepath(mri)
    if not source:
        raise HTTPException(status_code=404, detail="MRI file is missing")
    try:
        metadata = mri_service.get_volume_metadata(source)
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"{type(error).__name__}: {error}")
    metadata["id"] = mri.id
    metadata["filename"] = mri.filename
    return {"code": 200, "data": metadata}


@router.get("/{case_id}/slice/{view}/{index}")
def get_slice_png(
    case_id: int,
    view: str,
    index: int,
    ww: float | None = Query(default=None),
    wl: float | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if view not in mri_service.VIEW_AXIS:
        raise HTTPException(status_code=404, detail="view must be axial|coronal|sagittal")
    mri = _get_latest_mri(case_id, db)
    source = mri_service.resolve_filepath(mri)
    if not source:
        raise HTTPException(status_code=404, detail="MRI file is missing")

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
                "source": mri.segmentation_source or "mock",
                "mask_url": "/" + mask_path.relative_to(BACKEND_DIR).as_posix(),
                "disclaimer": "分割掩膜（模拟或医生上传），非真实 AI 模型输出。",
                "shape": list(mask.shape),
                "views": {view: int(mask.shape[axis]) for view, axis in mri_service.VIEW_AXIS.items()},
            },
        }
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

    mask_path = source.parent / "seg_mask.nii.gz"
    content = await file.read()
    mask_path.write_bytes(content)

    try:
        volume_shape = list(mri_service.load_volume(source)[0].shape)
        mask_shape = list(mri_service.load_volume(mask_path)[0].shape)
        if volume_shape != mask_shape:
            mask_path.unlink(missing_ok=True)
            raise HTTPException(status_code=422, detail=f"mask shape {mask_shape} does not match volume shape {volume_shape}")
    except HTTPException:
        raise
    except Exception as error:
        mask_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"invalid mask file: {error}")

    mri.segmentation_source = "uploaded"
    db.commit()
    return {"code": 200, "message": "segmentation saved", "data": {"shape": mask_shape}}


@router.get("/{case_id}/mask/{view}/{index}")
def get_mask_png(case_id: int, view: str, index: int, db: Session = Depends(get_db)):
    if view not in mri_service.VIEW_AXIS:
        raise HTTPException(status_code=404, detail="view must be axial|coronal|sagittal")
    mri = _get_latest_mri(case_id, db)
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
    db: Session = Depends(get_db),
):
    if view not in mri_service.VIEW_AXIS:
        raise HTTPException(status_code=404, detail="view must be axial|coronal|sagittal")
    mri = _get_latest_mri(case_id, db)
    source = mri_service.resolve_filepath(mri)
    if not source:
        raise HTTPException(status_code=404, detail="MRI file is missing")
    try:
        result = mri_service.get_voxel_value(source, view, index, float(nx), float(ny))
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"{type(error).__name__}: {error}")
    return {"code": 200, "data": result}


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
def verify_mri(case_id: int, db: Session = Depends(get_db)):
    mri = _get_latest_mri(case_id, db)
    mri.doctor_verified = True
    db.commit()
    return {"code": 200, "message": "AI result verified", "data": {"doctor_verified": True}}


@router.get("/{case_id}/annotations")
def get_annotations(case_id: int, db: Session = Depends(get_db)):
    mri = _get_latest_mri(case_id, db)
    items = annotation_service.list_annotations(db, mri.id)
    return {"code": 200, "data": [annotation_service.serialize_annotation(item) for item in items]}


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
