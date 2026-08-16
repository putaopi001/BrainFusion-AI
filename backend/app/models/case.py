from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"))
    description = Column(String(255))   # 病例描述
    mri_path = Column(String(255), default="")
    status = Column(String(50), default="waiting")  # waiting/created/uploaded/analyzed
    created_time = Column(DateTime, default=datetime.utcnow)
    updated_time = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient = relationship("Patient", back_populates="cases")

    # Case 1:1 MRI
    mri = relationship(
        "MRI",
        back_populates="case",
        uselist=False,
        cascade="all, delete",
    )
