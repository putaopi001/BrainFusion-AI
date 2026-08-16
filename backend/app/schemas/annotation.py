from pydantic import BaseModel, Field


# 标注工具类型：rectangle(矩形ROI)/point(标记点)/line(测量线)/text(文字)/freehand(自由绘制)/angle(角度)
# 标注类别：tumor(肿瘤)/edema(水肿)/necrosis(坏死)/blood(出血)/other(其他)
class AnnotationCreate(BaseModel):
    view: str = Field(pattern="^(axial|coronal|sagittal)$")
    slice_index: int = Field(ge=0)
    tool: str = Field(default="rectangle", pattern="^(rectangle|point|line|text|freehand|angle)$")
    annotation_type: str = Field(default="other", pattern="^(tumor|edema|necrosis|blood|other)$")
    color: str = Field(default="#f97316", min_length=4, max_length=20)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(default=0, ge=0, le=1)
    height: float = Field(default=0, ge=0, le=1)
    points: str | None = Field(default=None, max_length=5000)
    voxel_coordinate: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=1000)
    created_by: str | None = Field(default=None, max_length=100)
