from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from app.database import Base


class DICOMReadingReview(Base):
    """Immutable local, self-attributed review of a specific reading-summary version."""
    __tablename__ = 'dicom_reading_reviews'
    __table_args__ = (UniqueConstraint('case_id', 'client_uid', name='uq_dicom_review_client'),)
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey('cases.id'), nullable=False, index=True)
    study_uid = Column(String(64), nullable=False, index=True)
    series_uid = Column(String(64), nullable=False, index=True)
    client_uid = Column(String(100), nullable=False)
    content_sha256 = Column(String(64), nullable=False)
    snapshot_json = Column(Text, nullable=False)
    reviewer = Column(String(120), nullable=False)
    opinion = Column(Text, nullable=False)
    decision = Column(String(32), nullable=False)
    created_time = Column(DateTime, default=datetime.utcnow, nullable=False)
