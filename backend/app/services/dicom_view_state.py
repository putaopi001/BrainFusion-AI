"""Version-bound DICOM patient-space cameras and presentation windows."""
import json
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError

from app.core.time import utc_iso
from app.models.dicom_view_state import DICOMViewState
from app.schemas.world_measurement import CameraState, WindowRange
from app.services.dicom_measurements import Context, check_context, dumps
from app.services.view_state_service import validate_cameras


class Create(BaseModel):
    model_config = ConfigDict(extra='forbid')
    context: Context
    client_uid: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')
    cameras: dict[Literal['axial', 'sagittal', 'coronal'], CameraState]
    window_ranges: list[WindowRange] = Field(min_length=3, max_length=3)


def serialize(item, context):
    stored = json.loads(item.context_json)
    return dict(id=item.id, context=stored, current=stored == context,
        state=json.loads(item.state_json), created_time=utc_iso(item.created_time))


def latest(db, case_id, context):
    item = db.query(DICOMViewState).filter_by(case_id=case_id, study_uid=context['study_uid'],
        series_uid=context['series_uid']).order_by(DICOMViewState.id.desc()).first()
    return dict(context=context, saved=serialize(item, context) if item else None,
        revision_scope='linked_archive_identity_and_series_metadata_not_full_pixel_hash')


def save(db, case_id, context, payload):
    check_context(payload, context)
    validate_cameras(payload.cameras)
    if any(r.upper <= r.lower for r in payload.window_ranges):
        raise HTTPException(422, 'Three positive window ranges are required')
    state_json = dumps(payload.model_dump(exclude={'context', 'client_uid'}))
    context_json = dumps(context)
    def existing():
        return db.query(DICOMViewState).filter_by(case_id=case_id, client_uid=payload.client_uid).first()
    def duplicate(item):
        if (item.context_json != context_json or item.state_json != state_json
                or item.study_uid != context['study_uid'] or item.series_uid != context['series_uid']):
            raise HTTPException(409, 'View UID belongs to a different immutable DICOM view version')
        return serialize(item, context)
    item = existing()
    if item is not None:
        return duplicate(item)
    item = DICOMViewState(case_id=case_id, study_uid=context['study_uid'], series_uid=context['series_uid'],
        client_uid=payload.client_uid, context_json=context_json, state_json=state_json)
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        item = existing()
        if item is None:
            raise
        return duplicate(item)
    return serialize(item, context)
