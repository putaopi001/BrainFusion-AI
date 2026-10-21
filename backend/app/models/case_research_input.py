from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.database import Base


class CaseResearchInput(Base):
    """Case-scoped research overrides, separate from the patient's medical record."""
    __tablename__ = 'case_research_inputs'
    case_id = Column(Integer, ForeignKey('cases.id'), primary_key=True)
    age = Column(Integer, nullable=False)
    gender = Column(String(20), nullable=False)
    version = Column(String(36), nullable=False)
    updated_time = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
