from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text

from app.database import Base


class MRIAnnotation(Base):
    __tablename__ = "mri_annotations"

    id = Column(Integer, primary_key=True, index=True)
    mri_id = Column(Integer, ForeignKey("mris.id"), nullable=False, index=True)
    case_id = Column(Integer, index=True)
    view = Column(String(20), nullable=False)                       # axial/coronal/sagittal
    slice_index = Column(Integer, nullable=False)                   # 该视图切片索引
    tool = Column(String(20), nullable=False, default="rectangle")  # rectangle/point/line/text/freehand/angle
    annotation_type = Column(String(20), nullable=False, default="other")  # tumor/edema/necrosis/blood/other
    color = Column(String(20), nullable=False, default="#f97316")
    x = Column(Float, nullable=False)          # 归一化坐标
    y = Column(Float, nullable=False)
    width = Column(Float, nullable=False, default=0)
    height = Column(Float, nullable=False, default=0)
    points = Column(Text, nullable=True)       # freehand/angle 的 JSON 点集
    voxel_coordinate = Column(Text, nullable=True)  # {x,y,z} 体素坐标 JSON
    note = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)
    created_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_time = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
