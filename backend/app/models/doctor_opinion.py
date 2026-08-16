from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text

from app.database import Base


class DoctorOpinion(Base):
    __tablename__ = "doctor_opinions"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, unique=True, index=True)
    author = Column(Text, nullable=True)     # 阅片医生姓名
    content = Column(Text, nullable=False, default="")  # 阅片意见
    created_time = Column(DateTime, default=datetime.utcnow)
    updated_time = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
