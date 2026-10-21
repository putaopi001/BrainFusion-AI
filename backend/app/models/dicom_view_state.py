from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from app.database import Base


class DICOMViewState(Base):
    """Explicit immutable camera/window versions, separate from AI/MRI state."""
    __tablename__ = 'dicom_view_states'
    __table_args__ = (UniqueConstraint('case_id', 'client_uid', name='uq_dicom_view_client'),)
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey('cases.id'), nullable=False, index=True)
    study_uid = Column(String(64), nullable=False, index=True)
    series_uid = Column(String(64), nullable=False, index=True)
    client_uid = Column(String(100), nullable=False)
    context_json = Column(Text, nullable=False)
    state_json = Column(Text, nullable=False)
    created_time = Column(DateTime, default=datetime.utcnow, nullable=False)
