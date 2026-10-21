import hashlib
import json

import nibabel as nib
import numpy as np
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.core.storage import resolve_stored_path
from app.core.time import utc_iso
from app.models.analysis_run import AnalysisRun
from app.models.world_measurement import MRIWorldMeasurement
from app.services import mri_service
from app.services.artifact_integrity import analysis_problem


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def context_for(mri, db):
    try:
        path, _, available = mri_service.resolve_view_sequence(mri)
        if path is None:
            raise ValueError('MRI file is missing')
        image = nib.load(path)
        if len(image.shape) != 3 or image.header.get_xyzt_units()[0] != 'mm':
            raise ValueError('Measurements require a 3D MRI with explicit millimeter units')
        if not np.isfinite(image.affine).all():
            raise ValueError('Invalid MRI affine')
        paths = {key: resolve_stored_path(value) for key, value in json.loads(mri.sequences_json).items()} if available else {'legacy': path}
        revisions = {}
        for key, source in paths.items():
            stat = source.stat()
            revisions[key] = f'{stat.st_size}-{stat.st_mtime_ns}'
        context = {'mri_id': mri.id, 'analysis_run_id': mri.analysis_run_id,
                   'geometry_id': _hash({'shape': list(image.shape), 'affine_ras_mm': image.affine.tolist()}),
                   'study_revision': _hash(revisions)}
        return context, image, available, revisions
    except (ValueError, OSError, json.JSONDecodeError) as error:
        raise HTTPException(422, str(error))


def serialize(item, context):
    current = all(getattr(item, key) == value for key, value in context.items())
    return {'id': item.id, 'context': {key: getattr(item, key) for key in context},
            'client_uid': item.client_uid, 'tool': 'Length', 'coordinate_contract': 'LPS_MM_V1',
            'reference_sequence': item.reference_sequence, 'view': item.view,
            'points_lps': json.loads(item.points_lps), 'view_plane_normal': json.loads(item.view_plane_normal),
            'view_up': json.loads(item.view_up), 'length_mm': item.length_mm,
            'current': current, 'created_time': utc_iso(item.created_time)}


def list_measurements(mri, db):
    context, _, _, revisions = context_for(mri, db)
    items = db.query(MRIWorldMeasurement).filter_by(mri_id=mri.id, case_id=mri.case_id).order_by(MRIWorldMeasurement.id).all()
    return {'context': context, 'source_revisions': revisions, 'items': [serialize(item, context) for item in items]}


def save_measurement(mri, db, payload):
    context, image, available, _ = context_for(mri, db)
    if payload.context.model_dump() != context:
        raise HTTPException(409, 'MRI, study file or analysis version changed; reopen the workstation')
    if mri.analysis_run_id:
        problem = analysis_problem(mri, db.get(AnalysisRun, mri.analysis_run_id))
        if problem:
            raise HTTPException(409, 'Current analysis is unavailable: ' + problem)
    if (available and payload.reference_sequence not in available) or (not available and payload.reference_sequence is not None):
        raise HTTPException(422, 'Reference sequence identity does not match this MRI')
    points = np.asarray(payload.points_lps, dtype=float)
    normal, up = np.asarray(payload.view_plane_normal), np.asarray(payload.view_up)
    if not np.isclose(np.linalg.norm(normal), 1, atol=1e-4) or not np.isclose(np.linalg.norm(up), 1, atol=1e-4) or abs(np.dot(normal, up)) > 1e-4:
        raise HTTPException(422, 'Measurement plane must have orthonormal directions')
    if abs(np.dot(points[1] - points[0], normal)) > 1e-3:
        raise HTTPException(422, 'Measurement endpoints must lie in the same physical plane')
    ras_points = points * [-1, -1, 1]
    voxel_points = nib.affines.apply_affine(np.linalg.inv(image.affine), ras_points)
    if np.any(voxel_points < -.5001) or np.any(voxel_points > np.asarray(image.shape) - .4999):
        raise HTTPException(422, 'Measurement endpoints are outside the MRI volume')
    length = float(np.linalg.norm(points[1] - points[0]))
    if length <= 1e-6:
        raise HTTPException(422, 'Measurement length must be positive')
    values = {**context, 'case_id': mri.case_id, 'client_uid': payload.client_uid,
              'reference_sequence': payload.reference_sequence, 'view': payload.view,
              'points_lps': json.dumps(payload.points_lps), 'view_plane_normal': json.dumps(payload.view_plane_normal),
              'view_up': json.dumps(payload.view_up), 'length_mm': length}
    def existing():
        return db.query(MRIWorldMeasurement).filter_by(mri_id=mri.id, client_uid=payload.client_uid).first()
    def check_duplicate(item):
        if any(getattr(item, key) != value for key, value in values.items()):
            raise HTTPException(409, 'Measurement UID already belongs to another immutable measurement')
        return serialize(item, context)
    item = existing()
    if item is not None:
        return check_duplicate(item)
    item = MRIWorldMeasurement(**values)
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        item = existing()
        if item is None:
            raise
        return check_duplicate(item)
    db.refresh(item)
    return serialize(item, context)
