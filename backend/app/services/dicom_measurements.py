"""Physical distances bound to the linked archive and observed series metadata.

No NIfTI, model role inference, pixel modification or segmentation writes.
The revision is a metadata revision, not a claim of full pixel attestation.
"""
import json
from typing import Literal

import numpy as np
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError

from app.core.time import utc_iso
from app.models.dicom_measurement import DICOMWorldMeasurement
from app.schemas.world_measurement import Point3


class Context(BaseModel):
    model_config = ConfigDict(extra='forbid')
    case_link_id: int = Field(ge=1)
    archive_id: str = Field(min_length=1, max_length=64)
    archive_fingerprint: str = Field(pattern=r'^[0-9a-f]{64}$')
    study_uid: str = Field(min_length=1, max_length=64)
    series_uid: str = Field(min_length=1, max_length=64)
    frame_of_reference_uid: str = Field(min_length=1, max_length=64)
    metadata_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


class Delete(BaseModel):
    model_config = ConfigDict(extra='forbid')
    context: Context


class Create(Delete):
    client_uid: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')
    view: Literal['axial', 'sagittal', 'coronal']
    points_lps: list[Point3] = Field(min_length=2, max_length=2)
    view_plane_normal: Point3
    view_up: Point3


def dumps(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def context_for(manifest, link):
    return dict(case_link_id=link.id, archive_id=manifest['archive_id'],
        archive_fingerprint=manifest['archive_fingerprint'], study_uid=manifest['study_uid'],
        series_uid=manifest['series_uid'], metadata_sha256=manifest['metadata_sha256'],
        frame_of_reference_uid=manifest['geometry']['frame_of_reference_uid'])


def serialize(item, context):
    stored = json.loads(item.context_json)
    return dict(id=item.id, context=stored, client_uid=item.client_uid, tool='Length',
        coordinate_contract='LPS_MM_V1', reference_sequence='dicom', view=item.view,
        points_lps=json.loads(item.points_lps), view_plane_normal=json.loads(item.view_plane_normal),
        view_up=json.loads(item.view_up), length_mm=item.length_mm, current=stored == context,
        created_time=utc_iso(item.created_time))


def list_items(db, case_id, context):
    rows = db.query(DICOMWorldMeasurement).filter_by(case_id=case_id,
        study_uid=context['study_uid'], series_uid=context['series_uid']).order_by(DICOMWorldMeasurement.id).all()
    return dict(context=context, items=[serialize(r, context) for r in rows],
        revision_scope='linked_archive_identity_and_series_metadata_not_full_pixel_hash')


def check_context(payload, context):
    if payload.context.model_dump() != context:
        raise HTTPException(409, 'DICOM archive, case link or series metadata changed; reopen the workstation')


def save(db, case_id, context, geometry, payload):
    check_context(payload, context)
    points = np.asarray(payload.points_lps)
    normal, up = np.asarray(payload.view_plane_normal), np.asarray(payload.view_up)
    if (not np.isclose(np.linalg.norm(normal), 1, atol=1e-4)
            or not np.isclose(np.linalg.norm(up), 1, atol=1e-4) or abs(np.dot(normal, up)) > 1e-4
            or abs(np.dot(points[1] - points[0], normal)) > 1e-3):
        raise HTTPException(422, 'Measurement must lie in one physical plane with orthonormal directions')
    # These are orthographic patient-axis MPR views, not the acquisition IOP.
    axis = {'axial': 2, 'sagittal': 0, 'coronal': 1}[payload.view]
    if not np.isclose(abs(normal[axis]), 1, atol=1e-4):
        raise HTTPException(422, 'Measurement plane differs from the named patient-axis view')
    iop = geometry['image_orientation_patient']
    basis = np.column_stack([iop[:3], iop[3:], geometry['unit_normal_for_sorting']])
    basis = basis @ np.diag(geometry['spacing_xyz_mm'])
    indices = np.linalg.solve(basis, (points - np.asarray(geometry['origin_lps_mm'])).T).T
    if np.any(indices < -.5001) or np.any(indices > np.asarray(geometry['dimensions']) - .4999):
        raise HTTPException(422, 'Measurement endpoints are outside the original DICOM volume')
    length = float(np.linalg.norm(points[1] - points[0]))
    if length <= 1e-6:
        raise HTTPException(422, 'Measurement length must be positive')
    values = dict(case_id=case_id, study_uid=context['study_uid'], series_uid=context['series_uid'],
        client_uid=payload.client_uid, context_json=dumps(context), view=payload.view,
        points_lps=dumps(payload.points_lps), view_plane_normal=dumps(payload.view_plane_normal),
        view_up=dumps(payload.view_up), length_mm=length)
    def existing():
        return db.query(DICOMWorldMeasurement).filter_by(case_id=case_id, client_uid=payload.client_uid).first()
    def same(item):
        if any(getattr(item, key) != value for key, value in values.items()):
            raise HTTPException(409, 'Measurement UID belongs to another immutable DICOM measurement')
        return serialize(item, context)
    item = existing()
    if item is not None:
        return same(item)
    item = DICOMWorldMeasurement(**values)
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        item = existing()
        if item is None:
            raise
        return same(item)
    return serialize(item, context)


def remove(db, case_id, item_id, context, payload):
    check_context(payload, context)
    item = db.query(DICOMWorldMeasurement).filter_by(id=item_id, case_id=case_id,
        study_uid=context['study_uid'], series_uid=context['series_uid']).first()
    if item is None:
        raise HTTPException(404, 'DICOM measurement not found in this case/series')
    if json.loads(item.context_json) != context:
        raise HTTPException(409, 'Historical measurement is not a current-series overlay')
    db.delete(item)
    db.commit()
    return dict(deleted=True, id=item_id)
