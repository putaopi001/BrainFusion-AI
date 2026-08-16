from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class MRI(Base):
    __tablename__ = "mris"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"))
    filename = Column(String)                       # 原始文件名
    filepath = Column(String)                       # 磁盘相对路径
    web_path = Column(String, nullable=True)        # 对外访问 URL
    slice_path = Column(String, nullable=True)      # 预览切片首图路径
    processed_path = Column(String, nullable=True)  # 预处理后 MRI 路径
    preview_error = Column(String, nullable=True)   # 预览失败原因
    modality = Column(String, default="MRI")
    status = Column(String, default="uploaded")     # uploaded/processing/preview_ready/analyzed/failed
    doctor_verified = Column(Boolean, default=False, nullable=False)
    created_time = Column(DateTime, default=datetime.utcnow)
    updated_time = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    case = relationship("Case", back_populates="mri")
