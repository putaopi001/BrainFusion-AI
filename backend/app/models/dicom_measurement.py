from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from app.database import Base


class DICOMWorldMeasurement(Base):
    """Immutable LPS-mm distances, independent of NIfTI/model inputs."""
    __tablename__ = 'dicom_world_measurements'
    __table_args__ = (UniqueConstraint('case_id', 'client_uid', name='uq_dicom_measurement_client'),)
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey('cases.id'), nullable=False, index=True)
    study_uid = Column(String(64), nullable=False, index=True)
    series_uid = Column(String(64), nullable=False, index=True)
    client_uid = Column(String(100), nullable=False)
    context_json = Column(Text, nullable=False)
    view = Column(String(12), nullable=False)
    points_lps = Column(Text, nullable=False)
    view_plane_normal = Column(Text, nullable=False)
    view_up = Column(Text, nullable=False)
    length_mm = Column(Float, nullable=False)
    created_time = Column(DateTime, default=datetime.utcnow, nullable=False)
