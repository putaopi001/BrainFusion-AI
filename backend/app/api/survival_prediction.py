"""Opt-in research-only survival model API; never writes patient predictions."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.services.local_auth import require_doctor
from app.services import survival_model
from app.services.survival_model import SurvivalModelError

router = APIRouter(prefix="/api/survival", tags=["research-survival-model"])


class SyntheticPredictionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    declared_use_scope: Literal["SYNTHETIC_TEST"]
    model_id: Literal[survival_model.CLINICAL_MODEL_ID, survival_model.FUSION_MODEL_ID,
                       survival_model.UCSF_MODEL_ID]
    clinical: dict[str, float | str]
    radiomics: dict[str, float] | None = None
    requested_times_days: list[float] = Field(min_length=1, max_length=24)


def available_models() -> tuple[list[dict], dict[str, str]]:
    models, unavailable = [], {}
    for model_id in (survival_model.CLINICAL_MODEL_ID, survival_model.FUSION_MODEL_ID,
                     survival_model.UCSF_MODEL_ID):
        if survival_model.model_directory(model_id) is None:
            unavailable[model_id] = "No isolated model is configured, or research prediction is disabled."
            continue
        try:
            models.append(survival_model.public_model(survival_model.load_model(model_id=model_id)))
        except SurvivalModelError as error:
            unavailable[model_id] = str(error)
    return models, unavailable


def model_status() -> dict:
    models, unavailable = available_models()
    return {"available": bool(models), "status": "RESEARCH_ONLY" if models else "NOT_AVAILABLE",
            "reason": None if models else "No isolated research survival model is enabled.",
            "models": models, "unavailable_models": unavailable,
            "research_only": True, "official_endpoint_validated": False}


@router.get("/status")
def survival_model_status():
    state = model_status()
    return {"code": 200, "data": {
        **state,
        "prediction_scope": "synthetic requests only; no patient-level inputs or outputs are persisted",
        "official_endpoint_status": "BLOCKED_BY_DATA_DICTIONARY",
    }}


@router.get("/models")
def survival_models():
    models, unavailable = available_models()
    return {"code": 200, "data": {"models": models, "unavailable_models": unavailable,
                                   "research_only": True}}


@router.post("/predict")
def predict_survival(payload: SyntheticPredictionInput,
                     identity: dict = Depends(require_doctor)):
    # The schema deliberately has no patient identifier. Do not log request
    # bodies, scores or clinical/radiomic covariates.
    if not identity.get("user_id") and not identity.get("id"):
        raise HTTPException(401, "A valid local research session is required.")
    if survival_model.model_directory(payload.model_id) is None:
        raise HTTPException(503, "Research survival prediction is disabled or the selected model is unavailable.")
    try:
        model = survival_model.load_model(model_id=payload.model_id)
        result = survival_model.predict(model, payload.clinical,
                                        payload.requested_times_days, payload.radiomics)
    except SurvivalModelError as error:
        raise HTTPException(422, str(error)) from error
    return {"code": 200, "data": {
        **result,
        "limitations": list(result["limitations"]) + [
            "Input was explicitly declared SYNTHETIC_TEST; this endpoint must not be used for a real patient or clinical decision."
        ],
        "input_scope": payload.declared_use_scope,
    }}
