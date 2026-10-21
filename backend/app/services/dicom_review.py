"""Immutable source/content review with local account attribution; no medical credential assertion."""
import hashlib
import json
from typing import Annotated, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.exc import IntegrityError

from app.core.time import utc_iso
from app.models.dicom_review import DICOMReadingReview
from app.services.dicom_measurements import Context, dumps


class Create(BaseModel):
    model_config = ConfigDict(extra='forbid')
    context: Context
    content_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    client_uid: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')
    reviewer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    opinion: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    decision: Literal['checked', 'needs_revision']
    acknowledge_local_record_only: Literal[True]

def scoped(db, case_id, data):
    return db.query(DICOMReadingReview).filter_by(case_id=case_id,
        study_uid=data['context']['study_uid'], series_uid=data['context']['series_uid'])


def serialize(row, data, *, include_snapshot=False):
    saved = json.loads(row.snapshot_json)
    current = saved['context'] == data['context'] and row.content_sha256 == data['content_sha256']
    actor = saved.get('review_actor')
    authenticated = (isinstance(actor, dict) and actor.get('format') == 'local-account-review-v1'
        and actor.get('role') == 'doctor' and actor.get('display_name') == row.reviewer)
    actor = actor if authenticated else None
    result = dict(id=row.id, content_sha256=row.content_sha256, context=saved['context'],
        current=current, reviewer=row.reviewer, opinion=row.opinion, decision=row.decision,
        created_time=utc_iso(row.created_time), reviewer_authenticated=authenticated, identity=actor,
        scope='local_account_authenticated_not_medical_credentials' if authenticated else 'local_self_attributed_reading_record_not_clinical_certification')
    if include_snapshot:
        result['reviewed_snapshot'] = saved
    return result


def attach(db, case_id, data):
    query = scoped(db, case_id, data)
    row = query.order_by(DICOMReadingReview.id.desc()).first()
    review = serialize(row, data) if row else None
    # Review data is outside the reviewed content hash to avoid circular versions.
    export = dict(content_sha256=data['content_sha256'], latest_review=review)
    return dict(**data, latest_review=review, review_history_count=query.count(),
        export_sha256=hashlib.sha256(dumps(export).encode()).hexdigest())


def history(db, case_id, data, limit, offset):
    query = scoped(db, case_id, data)
    total = query.count()
    rows = query.order_by(DICOMReadingReview.id.desc()).offset(offset).limit(limit).all()
    return dict(context=data['context'], content_sha256=data['content_sha256'], total=total,
        items=[serialize(row, data, include_snapshot=True) for row in rows],
        next_offset=offset+limit if offset+len(rows) < total else None)


def save(db, case_id, data, payload, identity):
    if payload.reviewer != identity['display_name']:
        raise HTTPException(403, '复核署名必须与已登录本地账户一致。')
    # The API holds BEGIN IMMEDIATE across local content validation and this write.
    if payload.context.model_dump() != data['context'] or payload.content_sha256 != data['content_sha256']:
        raise HTTPException(409, '来源或阅片记录内容已变化，请重新核对后再记录复核。')
    saved = {k: v for k, v in data.items() if k != 'observed_utc'}
    saved['review_actor'] = identity
    snapshot_json = dumps(saved)
    def existing():
        return db.query(DICOMReadingReview).filter_by(case_id=case_id, client_uid=payload.client_uid).first()
    def duplicate(row):
        if (row.content_sha256 != payload.content_sha256 or row.snapshot_json != snapshot_json
                or row.reviewer != payload.reviewer or row.opinion != payload.opinion or row.decision != payload.decision):
            raise HTTPException(409, '复核请求标识已用于另一条不可变记录。')
        return serialize(row, data)
    row = existing()
    if row is not None:
        result = duplicate(row)
        db.rollback()
        return result
    row = DICOMReadingReview(case_id=case_id, study_uid=data['context']['study_uid'],
        series_uid=data['context']['series_uid'], client_uid=payload.client_uid,
        content_sha256=payload.content_sha256, snapshot_json=snapshot_json,
        reviewer=payload.reviewer, opinion=payload.opinion, decision=payload.decision)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        row = existing()
        if row is None:
            raise
        return duplicate(row)
    return serialize(row, data)
