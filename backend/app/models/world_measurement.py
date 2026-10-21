from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from app.database import Base


class MRIWorldMeasurement(Base):
    """Immutable LPS-mm measurements, separate from legacy Canvas annotations."""
    __tablename__ = 'mri_world_measurements'
    __table_args__ = (UniqueConstraint('mri_id', 'client_uid', name='uq_world_measurement_uid'),)
    id = Column(Integer, primary_key=True)
    mri_id = Column(Integer, ForeignKey('mris.id'), nullable=False, index=True)
    case_id = Column(Integer, nullable=False, index=True)
    client_uid = Column(String(100), nullable=False)
    analysis_run_id = Column(String(64), nullable=True)
    geometry_id = Column(String(64), nullable=False)
    study_revision = Column(String(64), nullable=False)
    reference_sequence = Column(String(8), nullable=True)
    view = Column(String(12), nullable=False)
    points_lps = Column(Text, nullable=False)
    view_plane_normal = Column(Text, nullable=False)
    view_up = Column(Text, nullable=False)
    length_mm = Column(Float, nullable=False)
    created_time = Column(DateTime, default=datetime.utcnow, nullable=False)


class MRIViewState(Base):
    """Explicitly saved, versioned Cornerstone view state."""
    __tablename__ = 'mri_view_states'
    __table_args__ = (UniqueConstraint('mri_id', 'client_uid', name='uq_mri_view_state_uid'),)
    id = Column(Integer, primary_key=True)
    mri_id = Column(Integer, ForeignKey('mris.id'), nullable=False, index=True)
    case_id = Column(Integer, nullable=False, index=True)
    client_uid = Column(String(100), nullable=False)
    analysis_run_id = Column(String(64), nullable=True)
    geometry_id = Column(String(64), nullable=False)
    study_revision = Column(String(64), nullable=False)
    state_json = Column(Text, nullable=False)
    created_time = Column(DateTime, default=datetime.utcnow, nullable=False)
