"""Opt-in research-only survival model API; never writes patient predictions."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.services.local_auth import require_doctor
from app.services import survival_model
from app.services.survival_model import SurvivalModelError

router = APIRouter(prefix="/api/survival", tags=["research-survival-model"])


class SurvivalPredictionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    declared_use_scope: Literal["SYNTHETIC_TEST", "RESEARCH_CASE"]
    model_id: Literal[survival_model.CLINICAL_MODEL_ID, survival_model.FUSION_MODEL_ID,
                       survival_model.UCSF_MODEL_ID]
    research_cohort: Literal["UCSF-PDGM-v5-IDH-wildtype-GBM"] | None = None
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
    research_case_available = bool(settings.SURVIVAL_RESEARCH_CASE_ENABLED and
                                    any(item["model_id"] == survival_model.UCSF_MODEL_ID for item in models))
    return {"available": bool(models), "status": "RESEARCH_ONLY" if models else "NOT_AVAILABLE",
            "reason": None if models else "No isolated research survival model is enabled.",
            "models": models, "unavailable_models": unavailable,
            "research_only": True, "official_endpoint_validated": False,
            "supported_prediction_scopes": ["SYNTHETIC_TEST"] + (["RESEARCH_CASE"] if research_case_available else [])}


@router.get("/status")
def survival_model_status():
    state = model_status()
    return {"code": 200, "data": {
        **state,
        "prediction_scope": state["supported_prediction_scopes"],
        "official_endpoint_status": "BLOCKED_BY_DATA_DICTIONARY",
    }}


@router.get("/models")
def survival_models():
    models, unavailable = available_models()
    return {"code": 200, "data": {"models": models, "unavailable_models": unavailable,
                                   "research_only": True}}


@router.post("/predict")
def predict_survival(payload: SurvivalPredictionInput,
                     identity: dict = Depends(require_doctor)):
    # The schema deliberately has no patient identifier. Do not log request
    # bodies, scores or clinical/radiomic covariates.
    if not identity.get("user_id") and not identity.get("id"):
        raise HTTPException(401, "A valid local research session is required.")
    if payload.declared_use_scope == "RESEARCH_CASE":
        if not settings.SURVIVAL_RESEARCH_CASE_ENABLED:
            raise HTTPException(403, "RESEARCH_CASE prediction is disabled in this runtime.")
        if payload.model_id != survival_model.UCSF_MODEL_ID:
            raise HTTPException(422, "RESEARCH_CASE is supported only by the UCSF-PDGM v5 model.")
        if payload.research_cohort != "UCSF-PDGM-v5-IDH-wildtype-GBM":
            raise HTTPException(422, "The declared research cohort is not compatible with this UCSF model.")
    elif payload.research_cohort is not None:
        raise HTTPException(422, "research_cohort is accepted only for RESEARCH_CASE requests.")
    if survival_model.model_directory(payload.model_id) is None:
        raise HTTPException(503, "Research survival prediction is disabled or the selected model is unavailable.")
    try:
        model = survival_model.load_model(model_id=payload.model_id)
        result = survival_model.predict(model, payload.clinical,
                                        payload.requested_times_days, payload.radiomics)
    except SurvivalModelError as error:
        raise HTTPException(422, str(error)) from error
    if payload.declared_use_scope == "RESEARCH_CASE":
        added_limitations = [
            "RESEARCH_CASE cohort membership is researcher-attested and is not independently verified by the API.",
            "Do not submit UPENN cases or other out-of-cohort cases; this research-only output is not a clinical decision tool.",
            "The API does not retain inputs, case identifiers, or predictions.",
        ]
        cohort_attestation = "RESEARCHER_ASSERTED_NOT_INDEPENDENTLY_VERIFIED"
    else:
        added_limitations = [
            "Input was explicitly declared SYNTHETIC_TEST; this endpoint must not be used for a real patient or clinical decision."
        ]
        cohort_attestation = None
    return {"code": 200, "data": {
        **result, "limitations": list(result["limitations"]) + added_limitations,
        "input_scope": payload.declared_use_scope, "research_cohort": payload.research_cohort,
        "cohort_attestation": cohort_attestation,
    }}
