from pydantic import BaseModel, Field


class DoctorOpinionUpdate(BaseModel):
    author: str | None = Field(default=None, max_length=100)
    content: str = Field(max_length=5000)
