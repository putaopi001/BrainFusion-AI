from pydantic import BaseModel, ConfigDict


class PatientCreate(BaseModel):
    name: str
    age: int | None = None
    gender: str


class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    age: int | None
    gender: str
