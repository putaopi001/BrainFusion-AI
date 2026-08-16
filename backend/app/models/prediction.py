from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String

from app.database import Base


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, index=True)
    tumor_probability = Column(Float)   # MRI 肿瘤概率 (0-1)
    risk_score = Column(Float)          # 临床风险评分 (0-1)
    fusion_score = Column(Float)        # 融合评分 (0-1)
    risk_level = Column(String)         # high/medium/low
    model_version = Column(String)      # 模型版本
    created_time = Column(DateTime, default=datetime.utcnow)
    updated_time = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
