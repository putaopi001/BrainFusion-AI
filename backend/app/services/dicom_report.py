"""Read-only DICOM reading summary; independent of model reports and AI results."""
import hashlib
from datetime import datetime, timezone

from app.core.time import utc_iso
from app.models.doctor_opinion import DoctorOpinion
from app.services.dicom_measurements import dumps, list_items


def snapshot(db, case_id, context, geometry):
    measurements = list_items(db, case_id, context)
    current = [row for row in measurements['items'] if row['current']]
    opinion = db.query(DoctorOpinion).filter_by(case_id=case_id).first()
    content = dict(format='dicom-reading-summary-v1', case_id=case_id, context=context,
        geometry={key: geometry[key] for key in ('dimensions', 'spacing_xyz_mm', 'origin_lps_mm',
            'image_orientation_patient', 'frame_of_reference_uid')},
        measurements=current,
        excluded_historical_measurements=len(measurements['items'])-len(current),
        doctor_opinion=dict(author=opinion.author or '', content=opinion.content,
            updated_time=utc_iso(opinion.updated_time)) if opinion else None,
        doctor_opinion_scope='case_level_not_series_version_review',
        revision_scope=measurements['revision_scope'],
        ai_analysis_included=False, model_sequence_role='unconfirmed')
    # Observation time changes on every check; the content revision must remain stable.
    return dict(**content, content_sha256=hashlib.sha256(dumps(content).encode()).hexdigest(),
        observed_utc=datetime.now(timezone.utc).isoformat())
