from sqlalchemy.orm import Session

from app.models.annotation import MRIAnnotation
from app.schemas.annotation import AnnotationCreate


def serialize_annotation(item: MRIAnnotation) -> dict:
    """Convert an MRIAnnotation ORM object to a JSON-friendly dict."""
    return {
        "id": item.id,
        "mri_id": item.mri_id,
        "case_id": item.case_id,
        "view": item.view,
        "slice_index": item.slice_index,
        "tool": item.tool,
        "annotation_type": item.annotation_type,
        "color": item.color,
        "x": item.x,
        "y": item.y,
        "width": item.width,
        "height": item.height,
        "points": item.points,
        "voxel_coordinate": item.voxel_coordinate,
        "note": item.note,
        "created_by": item.created_by,
        "created_time": item.created_time.isoformat() if item.created_time else None,
    }


def list_annotations(db: Session, mri_id: int) -> list[MRIAnnotation]:
    return (
        db.query(MRIAnnotation)
        .filter(MRIAnnotation.mri_id == mri_id)
        .order_by(MRIAnnotation.id.asc())
        .all()
    )


def create_annotation(db: Session, mri_id: int, case_id: int, payload: AnnotationCreate) -> MRIAnnotation:
    annotation = MRIAnnotation(
        mri_id=mri_id,
        case_id=case_id,
        **payload.model_dump(),
    )
    db.add(annotation)
    db.commit()
    db.refresh(annotation)
    return annotation


def delete_annotation(db: Session, mri_id: int, annotation_id: int) -> MRIAnnotation | None:
    annotation = (
        db.query(MRIAnnotation)
        .filter(MRIAnnotation.id == annotation_id, MRIAnnotation.mri_id == mri_id)
        .first()
    )
    if annotation is not None:
        db.delete(annotation)
        db.commit()
    return annotation


def delete_all_annotations(db: Session, mri_id: int) -> int:
    """删除该 MRI 下的全部标注，返回删除条数。"""
    count = (
        db.query(MRIAnnotation)
        .filter(MRIAnnotation.mri_id == mri_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return count
