from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from app.database import Base


class PACSStudyLink(Base):
    __tablename__ = 'pacs_study_links'
    __table_args__ = (UniqueConstraint('archive_id', 'study_uid', name='uq_pacs_archive_study'),)
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey('cases.id'), nullable=False, index=True)
    archive_id = Column(String(64), nullable=False)
    endpoint_fingerprint = Column(String(64), nullable=False)
    study_uid = Column(String(64), nullable=False)
    metadata_sha256 = Column(String(64), nullable=False)
    metadata_json = Column(Text, nullable=False)
    confirmation_method = Column(String(64), nullable=False, default='explicit-local-selection-v1')
    created_time = Column(DateTime, nullable=False, default=datetime.utcnow)
