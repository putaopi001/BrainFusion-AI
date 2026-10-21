from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

Point3 = tuple[FiniteFloat, FiniteFloat, FiniteFloat]


class MeasurementContext(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mri_id: int = Field(ge=1)
    analysis_run_id: str | None = Field(default=None, max_length=64)
    geometry_id: str = Field(pattern=r'^[0-9a-f]{64}$')
    study_revision: str = Field(pattern=r'^[0-9a-f]{64}$')


class WorldMeasurementCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    context: MeasurementContext
    client_uid: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')
    reference_sequence: Literal['t1c', 't1n', 't2w', 't2f'] | None = None
    view: Literal['axial', 'sagittal', 'coronal']
    points_lps: list[Point3] = Field(min_length=2, max_length=2)
    view_plane_normal: Point3
    view_up: Point3


class CameraState(BaseModel):
    model_config = ConfigDict(extra='forbid')
    focal_point: Point3
    position: Point3
    view_plane_normal: Point3
    view_up: Point3
    parallel_scale: FiniteFloat = Field(gt=0, le=100000)


class WindowRange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    lower: FiniteFloat
    upper: FiniteFloat


class ViewStateCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    context: MeasurementContext
    client_uid: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')
    sequence: Literal['t1c', 't1n', 't2w', 't2f'] | None = None
    segmentation_visible: bool
    cameras: dict[Literal['axial', 'sagittal', 'coronal'], CameraState]
    window_ranges: dict[str, list[WindowRange]] = Field(max_length=4)
