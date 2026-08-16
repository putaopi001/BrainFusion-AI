from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, index=True)
    risk_level = Column(String)          # 综合风险等级
    summary = Column(Text)               # AI 总结（JSON 列表字符串）
    recommendation = Column(Text)        # 推荐措施（JSON 列表字符串）
    created_time = Column(DateTime, default=datetime.utcnow)
    updated_time = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
