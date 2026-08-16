from pydantic import BaseModel, ConfigDict


class CaseCreate(BaseModel):
    patient_id: int | None = None
    patient_name: str | None = None
    age: int | None = None
    gender: str | None = None
    description: str


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    description: str
    mri_path: str
    status: str
