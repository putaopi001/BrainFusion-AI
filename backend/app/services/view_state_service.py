import json
import numpy as np
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from app.core.time import utc_iso
from app.models.analysis_run import AnalysisRun
from app.models.world_measurement import MRIViewState
from app.services.artifact_integrity import analysis_problem
from app.services.world_measurement_service import context_for


def serialize(item, context):
    return {'id': item.id, 'context': {k: getattr(item, k) for k in context},
            'current': all(getattr(item, k) == v for k, v in context.items()),
            'state': json.loads(item.state_json), 'created_time': utc_iso(item.created_time)}


def latest_view(mri, db):
    context, _, _, _ = context_for(mri, db)
    item = db.query(MRIViewState).filter_by(mri_id=mri.id, case_id=mri.case_id).order_by(MRIViewState.id.desc()).first()
    return {'context': context, 'saved': serialize(item, context) if item else None}


def validate_cameras(cameras):
    if set(cameras) != {'axial', 'sagittal', 'coronal'}:
        raise HTTPException(422, 'Exactly three physical cameras are required')
    for camera in cameras.values():
        normal, up = np.asarray(camera.view_plane_normal), np.asarray(camera.view_up)
        delta = np.asarray(camera.position) - camera.focal_point
        if (not np.isclose(np.linalg.norm(normal), 1, atol=1e-4) or not np.isclose(np.linalg.norm(up), 1, atol=1e-4)
                or abs(np.dot(normal, up)) > 1e-4 or np.linalg.norm(delta) < 1e-6
                or not np.allclose(delta / np.linalg.norm(delta), normal, atol=1e-4)
                or np.max(np.abs([camera.position, camera.focal_point])) > 1e6):
            raise HTTPException(422, 'Invalid physical camera directions or position')


def save_view(mri, db, payload):
    context, _, available, _ = context_for(mri, db)
    if payload.context.model_dump() != context:
        raise HTTPException(409, 'MRI, study file or analysis version changed; reopen the workstation')
    if mri.analysis_run_id:
        problem = analysis_problem(mri, db.get(AnalysisRun, mri.analysis_run_id))
        if problem:
            raise HTTPException(409, 'Current analysis is unavailable: ' + problem)
    if (available and payload.sequence not in available) or (not available and payload.sequence is not None):
        raise HTTPException(422, 'Selected sequence does not match this MRI')
    validate_cameras(payload.cameras)
    allowed = set(available) if available else {'legacy'}
    if not payload.window_ranges or not set(payload.window_ranges) <= allowed or (payload.sequence or 'legacy') not in payload.window_ranges:
        raise HTTPException(422, 'Window ranges must identify the selected sequence')
    for ranges in payload.window_ranges.values():
        if len(ranges) != 3 or any(r.upper <= r.lower for r in ranges):
            raise HTTPException(422, 'Each sequence requires three positive window ranges')
    state = payload.model_dump(exclude={'context', 'client_uid'})
    state_json = json.dumps(state, sort_keys=True, separators=(',', ':'), allow_nan=False)
    def existing():
        return db.query(MRIViewState).filter_by(mri_id=mri.id, client_uid=payload.client_uid).first()
    def duplicate(item):
        if item.state_json != state_json or any(getattr(item, k) != v for k, v in context.items()):
            raise HTTPException(409, 'View UID already belongs to a different immutable version')
        return serialize(item, context)
    item = existing()
    if item:
        return duplicate(item)
    item = MRIViewState(**context, case_id=mri.case_id, client_uid=payload.client_uid, state_json=state_json)
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        item = existing()
        if item is None:
            raise
        return duplicate(item)
    db.refresh(item)
    return serialize(item, context)
