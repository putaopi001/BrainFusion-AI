"""Focused contract tests for the opt-in UCSF RESEARCH_CASE scope."""
import hashlib
import json
import math

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.local_auth import require_doctor
from app.services.survival_model import UCSF_MODEL_ID, load_model, predict


COHORT = "UCSF-PDGM-v5-IDH-wildtype-GBM"


def write_v2_artifact(directory):
    directory.mkdir(parents=True, exist_ok=True)
    hazards = [0.02, 0.10, 0.20, 0.40]
    model = {
        "artifact_schema_version": 1,
        "model_id": UCSF_MODEL_ID,
        "model_version": "2.0.0-test",
        "model_type": "CoxPH",
        "research_only": True,
        "dataset": {"id": "UCSF-PDGM", "version": "TCIA Version 5 (2025-05-30)"},
        "endpoint": {"status": "OFFICIAL_DATASET_ENDPOINT_DOCUMENTED",
                     "official_endpoint_validated": True, "time_unit": "days"},
        "features": {
            "names": ["age_at_mri_years", "sex_M"],
            "means": [60.0, 0.5], "scales": [10.0, 0.5],
            "coefficients_standardized": [0.3, 0.1],
            "training_ranges": {"age_years": [21.0, 94.0]},
            "input_schema": {"inputs": ["age_years", "sex"],
                             "sex_categories": ["F", "M"],
                             "encoding": {"sex_M": "1 for M, 0 for F"},
                             "feature_timepoint": "Preoperative diagnostic MRI"},
        },
        "training": {"n": 100, "events": 60, "censored": 40},
        "baseline": {"times_days": [100.0, 365.0, 730.0, 1095.0],
                     "cumulative_hazard": hazards,
                     "survival": [math.exp(-value) for value in hazards]},
        "validation": {"mean_fold_harrell_c_index": 0.63,
                       "pooled_oof_harrell_c_index": 0.62,
                       "external_validation": False},
        "limitations": ["Synthetic fixture; research-only."],
    }
    artifact_path = directory / "cox-model.json"
    artifact_path.write_text(json.dumps(model, separators=(",", ":")) + "\n", encoding="utf-8")
    digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    manifest = {"artifact_schema_version": 1, "model_id": UCSF_MODEL_ID,
                "model_version": model["model_version"], "model_type": "CoxPH",
                "research_only": True, "artifact_file": artifact_path.name,
                "artifact_sha256": digest}
    (directory / "model-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return model


def test_v2_schema_loader_prediction_and_curve_contract(tmp_path):
    model = write_v2_artifact(tmp_path / "ucsf-v2")
    loaded = load_model(tmp_path / "ucsf-v2", model_id=UCSF_MODEL_ID)
    result = predict(loaded, {"age_years": 63, "sex": "F"}, [365, 730, 1095])
    probs = [point["survival_probability"] for point in result["survival_curve"]]
    assert result["model_version"] == model["model_version"]
    assert all(np.isfinite(p) and 0 <= p <= 1 for p in probs)
    assert probs == sorted(probs, reverse=True)
    with pytest.raises(ValueError, match="exactly match"):
        predict(loaded, {"age_years": 63, "sex": "F", "IDH1": "Wildtype"}, [365])


def test_research_case_requires_enabled_scope_and_returns_no_input_or_identity(tmp_path, monkeypatch):
    model_dir = tmp_path / "ucsf-v2"
    write_v2_artifact(model_dir)
    monkeypatch.setattr(settings, "SURVIVAL_UCSF_MODEL_DIR", str(model_dir))
    monkeypatch.setattr(settings, "SURVIVAL_RESEARCH_PREDICTION_ENABLED", True)
    monkeypatch.setattr(settings, "SURVIVAL_RESEARCH_CASE_ENABLED", True)
    app.dependency_overrides[require_doctor] = lambda: {"id": "synthetic-reviewer", "role": "doctor"}
    request_body = {
        "declared_use_scope": "RESEARCH_CASE", "research_cohort": COHORT,
        "model_id": UCSF_MODEL_ID,
        "clinical": {"age_years": 63, "sex": "F"},
        "requested_times_days": [365, 730, 1095],
    }
    try:
        with TestClient(app) as client:
            status = client.get("/api/survival/status").json()["data"]
            assert "RESEARCH_CASE" in status["supported_prediction_scopes"]
            listed = client.get("/api/survival/models").json()["data"]["models"]
            ucsf = next(item for item in listed if item["model_id"] == UCSF_MODEL_ID)
            assert ucsf["model_version"] == "2.0.0-test"
            assert ucsf["input_schema"]["inputs"] == ["age_years", "sex"]
            response = client.post("/api/survival/predict", json=request_body)
            assert response.status_code == 200, response.text
            data = response.json()["data"]
            assert data["input_scope"] == "RESEARCH_CASE"
            assert data["cohort_attestation"] == "RESEARCHER_ASSERTED_NOT_INDEPENDENTLY_VERIFIED"
            assert data["individual_prediction_saved"] is False
            assert "clinical" not in data and "patient_id" not in data
            assert len(data["survival_curve"]) == 3
            mismatch = {**request_body, "research_cohort": "UPENN-GBM"}
            assert client.post("/api/survival/predict", json=mismatch).status_code == 422
            wrong_model = {**request_body, "model_id": "upenn-clinical-cox-research"}
            assert client.post("/api/survival/predict", json=wrong_model).status_code == 422
    finally:
        app.dependency_overrides.pop(require_doctor, None)


def test_research_case_disabled_by_default_is_forbidden(tmp_path, monkeypatch):
    model_dir = tmp_path / "ucsf-v2"
    write_v2_artifact(model_dir)
    monkeypatch.setattr(settings, "SURVIVAL_UCSF_MODEL_DIR", str(model_dir))
    monkeypatch.setattr(settings, "SURVIVAL_RESEARCH_PREDICTION_ENABLED", True)
    monkeypatch.setattr(settings, "SURVIVAL_RESEARCH_CASE_ENABLED", False)
    app.dependency_overrides[require_doctor] = lambda: {"id": "synthetic-reviewer", "role": "doctor"}
    try:
        with TestClient(app) as client:
            response = client.post("/api/survival/predict", json={
                "declared_use_scope": "RESEARCH_CASE", "research_cohort": COHORT,
                "model_id": UCSF_MODEL_ID, "clinical": {"age_years": 63, "sex": "F"},
                "requested_times_days": [365],
            })
            assert response.status_code == 403
            assert "disabled" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(require_doctor, None)
