from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from app.database import Base


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    id = Column(String(36), primary_key=True)
    case_id = Column(Integer, index=True, nullable=False)
    mri_id = Column(Integer, nullable=False)
    state = Column(String(20), default="queued")
    request_json = Column(Text, nullable=False)
    result_json = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_time = Column(DateTime, default=datetime.utcnow)
    finished_time = Column(DateTime, nullable=True)
