import hashlib
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.api.survival_prediction import router as survival_router
from app.core.config import settings
from app.main import app
from app.services.local_auth import require_doctor
from app.services.survival_model import (SurvivalModelError, encode_clinical_inputs,
                                         load_model, predict)


FEATURES = ["age_years", "gender_M", "IDH1_mutated", "IDH1_NOS_NEC",
            "GTR_over90pct_Y", "GTR_unknown"]
FUSION_ID = "upenn-clinical-captk-fusion-cox-research"
CAPTK_FEATURES = ["T1GD_ET_Intensity_Mean", "FLAIR_ED_Intensity_Mean",
                  "T2_ED_Intensity_Mean", "T1_NC_Intensity_Mean"]


def artifact_payload():
    return {
        "artifact_schema_version": 1,
        "model_id": "upenn-clinical-cox-research",
        "model_version": "test-1",
        "model_type": "CoxPH",
        "research_only": True,
        "endpoint": {"status": "RESEARCHER_DEFINED_ENDPOINT_WITH_LIMITATIONS",
                     "official_endpoint_validated": False, "time_unit": "days"},
        "features": {
            "names": FEATURES,
            "means": [60, 0.5, 0.1, 0.1, 0.5, 0.05],
            "scales": [10, 0.5, 0.3, 0.3, 0.5, 0.2],
            "coefficients_standardized": [0.2, 0.1, 0.3, 0.1, -0.1, 0.0],
            "encoding": {"inputs": ["age_years", "gender", "IDH1", "GTR_over90percent"]},
            "training_ranges": {"age_years": [18, 90]},
        },
        "baseline": {"times_days": [100, 200, 400],
                     "cumulative_hazard": [0.1, 0.3, 0.8],
                     "survival": [np.exp(-0.1), np.exp(-0.3), np.exp(-0.8)]},
        "training": {"n": 12, "events": 9, "censored": 3},
        "validation": {"status": "SYNTHETIC_TEST_FIXTURE", "external_validation": False},
        "limitations": ["Synthetic artifact fixture only."],
    }


def write_artifact(directory, model=None):
    directory.mkdir(parents=True, exist_ok=True)
    artifact = directory / "cox-model.json"
    artifact.write_text(json.dumps(model or artifact_payload()), encoding="utf-8")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest = {"artifact_schema_version": 1, "model_type": "CoxPH", "research_only": True,
                "model_id": (model or artifact_payload())["model_id"],
                "model_version": (model or artifact_payload())["model_version"],
                "artifact_file": "cox-model.json", "artifact_sha256": digest}
    (directory / "model-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return artifact


def fusion_artifact_payload():
    model = artifact_payload()
    model["model_id"] = FUSION_ID
    model["features"] = {
        "names": ["age_years", "gender_M", "IDH1_mutated", "IDH1_NOS_NEC",
                  "GTR_over_90pct", *CAPTK_FEATURES],
        "means": [60, 0.5, 0.1, 0.1, 0.5, 1.2, 2.3, 3.4, 4.5],
        "scales": [10, 0.5, 0.3, 0.3, 0.5, 0.4, 0.5, 0.6, 0.7],
        "coefficients_standardized": [0.2, 0.1, 0.3, 0.1, -0.1, 0.01, 0.02, 0.03, 0.04],
        "imputation_medians": [60, 0, 0, 0, 0, 1.2, 2.3, 3.4, 4.5],
        "encoding": {"inputs": ["age_years", "gender", "IDH1", "GTR_over90percent"]},
        "training_ranges": {"age_years": [18, 90]},
        "radiomics": {"required_inputs": CAPTK_FEATURES},
    }
    return model


def test_model_artifact_hash_and_schema_are_enforced(tmp_path):
    artifact = write_artifact(tmp_path)
    loaded = load_model(tmp_path)
    assert loaded["model_version"] == "test-1"
    artifact.write_text(artifact.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(SurvivalModelError, match="SHA-256"):
        load_model(tmp_path)


def test_feature_order_categories_and_missing_inputs_are_strict():
    model = artifact_payload()
    values = encode_clinical_inputs({"age_years": 60, "gender": "M", "IDH1": "NOS/NEC",
                                     "GTR_over90percent": "UNKNOWN"}, model)
    assert model["features"]["names"] == FEATURES
    np.testing.assert_array_equal(values, [60, 1, 0, 1, 0, 1])
    with pytest.raises(SurvivalModelError, match="missing or unexpected"):
        encode_clinical_inputs({"age_years": 60, "gender": "M", "IDH1": "Wildtype"}, model)
    with pytest.raises(SurvivalModelError, match="outside the model training range"):
        encode_clinical_inputs({"age_years": 100, "gender": "F", "IDH1": "Wildtype",
                                "GTR_over90percent": "N"}, model)
    with pytest.raises(SurvivalModelError, match="IDH1 category"):
        encode_clinical_inputs({"age_years": 60, "gender": "M", "IDH1": "UNKNOWN",
                                "GTR_over90percent": "N"}, model)


def test_fusion_requires_exact_captk_features_and_never_accepts_brainfusion_feature_aliases():
    model = fusion_artifact_payload()
    clinical = {"age_years": 63, "gender": "F", "IDH1": "Wildtype", "GTR_over90percent": "UNKNOWN"}
    values = {name: float(index + 1) for index, name in enumerate(CAPTK_FEATURES)}
    encoded = encode_clinical_inputs(clinical, model, values)
    assert model["features"]["names"][-4:] == CAPTK_FEATURES
    assert encoded[-4:].tolist() == [1.0, 2.0, 3.0, 4.0]
    with pytest.raises(SurvivalModelError, match="exactly its registered CaPTk"):
        encode_clinical_inputs(clinical, model, {"brainfusion_feature_01": 1.0})


def test_baseline_survival_probability_is_bounded_monotone_and_deterministic():
    model = artifact_payload()
    inputs = {"age_years": 65, "gender": "F", "IDH1": "Mutated", "GTR_over90percent": "Y"}
    first = predict(model, inputs, [90, 100, 200, 365, 400])
    second = predict(model, inputs, [90, 100, 200, 365, 400])
    probabilities = [row["survival_probability"] for row in first["survival_curve"]]
    assert first == second
    assert all(0 <= value <= 1 for value in probabilities)
    assert probabilities == sorted(probabilities, reverse=True)
    assert first["relative_risk"] > 0
    assert first["individual_prediction_saved"] is False


def test_probability_time_unit_and_order_validation():
    model = artifact_payload()
    inputs = {"age_years": 65, "gender": "F", "IDH1": "Wildtype", "GTR_over90percent": "N"}
    with pytest.raises(SurvivalModelError, match="sorted"):
        predict(model, inputs, [365, 180])
    with pytest.raises(SurvivalModelError, match="positive finite"):
        predict(model, inputs, [0])
    with pytest.raises(SurvivalModelError, match="exceeds observed"):
        predict(model, inputs, [401])


def test_model_loader_rejects_baseline_survival_hazard_mismatch(tmp_path):
    model = artifact_payload()
    model["baseline"]["survival"] = [0.9, 0.7, 0.2]
    write_artifact(tmp_path, model)
    with pytest.raises(SurvivalModelError, match="baseline survival grid"):
        load_model(tmp_path)


def test_api_status_models_predict_and_auth_with_synthetic_request(tmp_path, monkeypatch):
    write_artifact(tmp_path)
    monkeypatch.setattr(settings, "SURVIVAL_MODEL_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "SURVIVAL_RESEARCH_PREDICTION_ENABLED", True)
    app.dependency_overrides[require_doctor] = lambda: {"id": "synthetic-reviewer", "role": "doctor"}
    try:
        with TestClient(app) as client:
            status = client.get("/api/survival/status")
            assert status.status_code == 200
            assert status.json()["data"]["available"] is True
            assert status.json()["data"]["official_endpoint_status"] == "BLOCKED_BY_DATA_DICTIONARY"
            models = client.get("/api/survival/models")
            assert models.status_code == 200
            assert models.json()["data"]["models"][0]["research_only"] is True
            response = client.post("/api/survival/predict", json={
                "declared_use_scope": "SYNTHETIC_TEST",
                "model_id": "upenn-clinical-cox-research",
                "clinical": {"age_years": 63, "gender": "F", "IDH1": "Wildtype",
                             "GTR_over90percent": "Y"},
                "requested_times_days": [180, 365],
            })
            assert response.status_code == 200, response.text
            data = response.json()["data"]
            assert data["research_only"] is True
            assert data["input_scope"] == "SYNTHETIC_TEST"
            assert len(data["survival_curve"]) == 2
            assert "patient_id" not in data and "clinical" not in data
            bad_scope = client.post("/api/survival/predict", json={
                "declared_use_scope": "REAL_PATIENT", "clinical": {}, "requested_times_days": [365]})
            assert bad_scope.status_code == 422
            patient_input = {"declared_use_scope": "SYNTHETIC_TEST",
                             "model_id": "upenn-clinical-cox-research",
                             "patient_id": "must-be-rejected",
                             "clinical": {"age_years": 63, "gender": "F", "IDH1": "Wildtype",
                                          "GTR_over90percent": "Y"},
                             "requested_times_days": [365]}
            assert client.post("/api/survival/predict", json=patient_input).status_code == 422
    finally:
        app.dependency_overrides.pop(require_doctor, None)


def test_fusion_api_is_selectable_and_requires_registered_captk_inputs(tmp_path, monkeypatch):
    clinical_dir = tmp_path / "clinical"
    fusion_dir = tmp_path / "fusion"
    write_artifact(clinical_dir)
    write_artifact(fusion_dir, fusion_artifact_payload())
    monkeypatch.setattr(settings, "SURVIVAL_MODEL_DIR", str(clinical_dir))
    monkeypatch.setattr(settings, "SURVIVAL_FUSION_MODEL_DIR", str(fusion_dir))
    monkeypatch.setattr(settings, "SURVIVAL_RESEARCH_PREDICTION_ENABLED", True)
    app.dependency_overrides[require_doctor] = lambda: {"id": "synthetic-reviewer", "role": "doctor"}
    request_body = {
        "declared_use_scope": "SYNTHETIC_TEST", "model_id": FUSION_ID,
        "clinical": {"age_years": 63, "gender": "F", "IDH1": "Wildtype",
                     "GTR_over90percent": "UNKNOWN"},
        "radiomics": {name: float(index + 1) for index, name in enumerate(CAPTK_FEATURES)},
        "requested_times_days": [100, 200],
    }
    try:
        with TestClient(app) as client:
            models = client.get("/api/survival/models").json()["data"]["models"]
            assert {model["model_id"] for model in models} == {
                "upenn-clinical-cox-research", FUSION_ID}
            response = client.post("/api/survival/predict", json=request_body)
            assert response.status_code == 200, response.text
            assert response.json()["data"]["model_id"] == FUSION_ID
            assert response.json()["data"]["input_scope"] == "SYNTHETIC_TEST"
            assert len(response.json()["data"]["survival_curve"]) == 2
            wrong_features = {**request_body, "radiomics": {"brainfusion_feature_01": 1.0}}
            rejected = client.post("/api/survival/predict", json=wrong_features)
            assert rejected.status_code == 422
    finally:
        app.dependency_overrides.pop(require_doctor, None)


def test_api_is_disabled_by_default_without_artifact(monkeypatch):
    monkeypatch.setattr(settings, "SURVIVAL_MODEL_DIR", "")
    monkeypatch.setattr(settings, "SURVIVAL_RESEARCH_PREDICTION_ENABLED", False)
    app.dependency_overrides[require_doctor] = lambda: {"id": "synthetic-reviewer", "role": "doctor"}
    try:
        with TestClient(app) as client:
            status = client.get("/api/survival/status")
            assert status.status_code == 200
            assert status.json()["data"]["status"] == "NOT_AVAILABLE"
            assert client.get("/api/survival/models").json()["data"]["models"] == []
            disabled = client.post("/api/survival/predict", json={
                "declared_use_scope": "SYNTHETIC_TEST",
                "model_id": "upenn-clinical-cox-research",
                "clinical": {"age_years": 63, "gender": "F", "IDH1": "Wildtype",
                             "GTR_over90percent": "Y"},
                "requested_times_days": [365],
            })
            assert disabled.status_code == 503
    finally:
        app.dependency_overrides.pop(require_doctor, None)
