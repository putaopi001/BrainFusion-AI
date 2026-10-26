"""Integrity-checked, research-only Cox model artifact loading and scoring.

This module never stores request features, patient identifiers, or predictions.
The endpoint is intentionally opt-in and only accepts explicitly synthetic
engineering requests while the official UPENN endpoint remains unresolved.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from app.core.config import settings

ARTIFACT_SCHEMA_VERSION = 1
EXPECTED_MODEL_TYPE = "CoxPH"
CLINICAL_MODEL_ID = "upenn-clinical-cox-research"
FUSION_MODEL_ID = "upenn-clinical-captk-fusion-cox-research"
UCSF_MODEL_ID = "ucsf-pdgm-clinical-cox-research"


class SurvivalModelError(ValueError):
    """A missing or invalid research model artifact."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path, max_bytes: int = 1_000_000) -> dict:
    try:
        raw = path.read_bytes()
        if len(raw) > max_bytes:
            raise SurvivalModelError("Survival model artifact is oversized.")
        value = json.loads(raw.decode("utf-8"))
    except FileNotFoundError as error:
        raise SurvivalModelError("Research survival model artifact is not installed.") from error
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SurvivalModelError("Research survival model artifact cannot be read.") from error
    if not isinstance(value, dict):
        raise SurvivalModelError("Research survival model artifact has an invalid format.")
    return value


def model_directory(model_id: str = CLINICAL_MODEL_ID) -> Path | None:
    if model_id == CLINICAL_MODEL_ID:
        configured = str(settings.SURVIVAL_MODEL_DIR or "").strip()
    elif model_id == FUSION_MODEL_ID:
        configured = str(settings.SURVIVAL_FUSION_MODEL_DIR or "").strip()
    elif model_id == UCSF_MODEL_ID:
        configured = str(settings.SURVIVAL_UCSF_MODEL_DIR or "").strip()
    else:
        return None
    if not configured or not settings.SURVIVAL_RESEARCH_PREDICTION_ENABLED:
        return None
    return Path(configured).expanduser().resolve()


def load_model(directory: Path | None = None, model_id: str = CLINICAL_MODEL_ID) -> dict:
    directory = directory if directory is not None else model_directory(model_id)
    if directory is None:
        raise SurvivalModelError("Research survival prediction is disabled or no model directory is configured.")
    manifest = _read_json(directory / "model-manifest.json", max_bytes=64_000)
    if manifest.get("artifact_schema_version") != ARTIFACT_SCHEMA_VERSION:
        raise SurvivalModelError("Unsupported survival model artifact schema version.")
    if manifest.get("model_type") != EXPECTED_MODEL_TYPE or manifest.get("research_only") is not True:
        raise SurvivalModelError("Artifact is not an explicitly research-only Cox PH model.")
    filename = manifest.get("artifact_file")
    if filename != "cox-model.json":
        raise SurvivalModelError("Survival model manifest contains an invalid artifact filename.")
    artifact_path = (directory / filename).resolve()
    if artifact_path.parent != directory.resolve():
        raise SurvivalModelError("Survival model artifact path escapes its model directory.")
    expected_hash = manifest.get("artifact_sha256")
    if not isinstance(expected_hash, str) or len(expected_hash) != 64:
        raise SurvivalModelError("Survival model manifest has no valid artifact hash.")
    if not hmac.compare_digest(sha256_file(artifact_path), expected_hash.lower()):
        raise SurvivalModelError("Survival model artifact SHA-256 does not match its manifest.")

    model = _read_json(artifact_path)
    _validate_model(model)
    if (model.get("model_id") != manifest.get("model_id")
            or model.get("model_version") != manifest.get("model_version")):
        raise SurvivalModelError("Model identity does not match its integrity manifest.")
    if model_id and model.get("model_id") != model_id:
        raise SurvivalModelError("Selected model identity does not match its configured model slot.")
    return model


def _validate_model(model: Mapping[str, Any]) -> None:
    if model.get("artifact_schema_version") != ARTIFACT_SCHEMA_VERSION:
        raise SurvivalModelError("Unsupported Cox model schema version.")
    if model.get("model_type") != EXPECTED_MODEL_TYPE or model.get("research_only") is not True:
        raise SurvivalModelError("Model is not explicitly marked RESEARCH_ONLY.")
    endpoint = model.get("endpoint", {})
    if model.get("model_id") == UCSF_MODEL_ID:
        if (endpoint.get("official_endpoint_validated") is not True
                or endpoint.get("status") != "OFFICIAL_DATASET_ENDPOINT_DOCUMENTED"
                or model.get("dataset", {}).get("id") != "UCSF-PDGM"
                or model.get("dataset", {}).get("version") != "TCIA Version 5 (2025-05-30)"):
            raise SurvivalModelError("UCSF model dataset or official endpoint contract is inconsistent.")
    elif endpoint.get("official_endpoint_validated") is not False or endpoint.get("status") != "RESEARCHER_DEFINED_ENDPOINT_WITH_LIMITATIONS":
        raise SurvivalModelError("Researcher-defined endpoint status is missing or inconsistent.")
    if model.get("endpoint", {}).get("time_unit") != "days":
        raise SurvivalModelError("Only the model's audited day-based time unit is supported.")
    if not all(isinstance(model.get(key), str) and model[key].strip()
               for key in ("model_id", "model_version")):
        raise SurvivalModelError("Model identity is missing.")
    features = model.get("features")
    if not isinstance(features, dict):
        raise SurvivalModelError("Model feature contract is missing.")
    names = features.get("names")
    means, scales, coefficients = features.get("means"), features.get("scales"), features.get("coefficients_standardized")
    if not isinstance(names, list) or not names or len(set(names)) != len(names):
        raise SurvivalModelError("Model feature names are invalid.")
    if any(not isinstance(values, list) or len(values) != len(names)
           for values in (means, scales, coefficients)):
        raise SurvivalModelError("Model preprocessing or coefficient order is invalid.")
    try:
        numeric = np.asarray([means, scales, coefficients], dtype=float)
    except (TypeError, ValueError) as error:
        raise SurvivalModelError("Model feature parameters are not numeric.") from error
    if not np.isfinite(numeric).all() or np.any(numeric[1] <= 0):
        raise SurvivalModelError("Model preprocessing parameters are non-finite or degenerate.")
    radiomics = features.get("radiomics")
    if model.get("model_id") == UCSF_MODEL_ID:
        if (names != ["age_at_mri_years", "sex_M"]
                or features.get("input_schema") != {
                    "inputs": ["age_years", "sex"], "sex_categories": ["F", "M"],
                    "encoding": {"sex_M": "1 for M, 0 for F"}}):
            raise SurvivalModelError("UCSF feature schema is incompatible with this runtime.")
        if not isinstance(features.get("training_ranges", {}).get("age_years"), list):
            raise SurvivalModelError("UCSF model age input range is missing.")
        if features.get("radiomics") is not None:
            raise SurvivalModelError("UCSF clinical model cannot accept radiomics features.")
        radiomics = None
        expected_features = {"age_at_mri_years", "sex_M"}
    else:
        expected_clinical = {"age_years", "gender_M", "IDH1_mutated", "IDH1_NOS_NEC",
                         "GTR_over90pct_Y", "GTR_unknown"}
        expected_fusion = {"age_years", "gender_M", "IDH1_mutated", "IDH1_NOS_NEC",
                       "GTR_over_90pct", "T1GD_ET_Intensity_Mean", "FLAIR_ED_Intensity_Mean",
                       "T2_ED_Intensity_Mean", "T1_NC_Intensity_Mean"}
        expected_features = expected_fusion if isinstance(radiomics, dict) else expected_clinical
    if set(names) != expected_features or len(names) != len(expected_features):
        raise SurvivalModelError("Model feature names do not match the registered clinical/fusion schema.")
    if isinstance(radiomics, dict):
        required_inputs = radiomics.get("required_inputs")
        if not isinstance(required_inputs, list) or set(required_inputs) != (expected_fusion - {
                "age_years", "gender_M", "IDH1_mutated", "IDH1_NOS_NEC", "GTR_over_90pct"}):
            raise SurvivalModelError("Fusion model radiomics schema is unsupported.")
        medians = features.get("imputation_medians")
        if not isinstance(medians, list) or len(medians) != len(names):
            raise SurvivalModelError("Fusion model imputation parameters are missing or misordered.")
        try:
            median_values = np.asarray(medians, dtype=float)
        except (TypeError, ValueError) as error:
            raise SurvivalModelError("Fusion model imputation parameters are non-numeric.") from error
        if not np.isfinite(median_values).all():
            raise SurvivalModelError("Fusion model imputation parameters are non-finite.")
    baseline = model.get("baseline")
    if not isinstance(baseline, dict):
        raise SurvivalModelError("Model baseline survival function is missing.")
    times, hazards, survival = (baseline.get("times_days"), baseline.get("cumulative_hazard"),
                                baseline.get("survival"))
    if (not isinstance(times, list) or not isinstance(hazards, list) or not isinstance(survival, list)
            or not times or len(times) != len(hazards) or len(times) != len(survival)):
        raise SurvivalModelError("Model baseline survival grid is invalid.")
    try:
        times, hazards, survival = (np.asarray(times, dtype=float), np.asarray(hazards, dtype=float),
                                    np.asarray(survival, dtype=float))
    except (TypeError, ValueError) as error:
        raise SurvivalModelError("Model baseline survival grid is not numeric.") from error
    if (not np.isfinite(times).all() or not np.isfinite(hazards).all()
            or np.any(times <= 0) or np.any(np.diff(times) <= 0)
            or np.any(hazards < 0) or np.any(np.diff(hazards) < -1e-12)
            or not np.isfinite(survival).all() or np.any((survival < 0) | (survival > 1))
            or np.any(np.diff(survival) > 1e-12)
            or not np.allclose(survival, np.exp(-hazards), rtol=1e-8, atol=1e-10)):
        raise SurvivalModelError("Model baseline survival grid is non-monotone or invalid.")
    training = model.get("training", {})
    if (training.get("n") != training.get("events", 0) + training.get("censored", 0)
            or training.get("n", 0) <= 0 or training.get("events", 0) <= 0):
        raise SurvivalModelError("Model training cohort contract is invalid.")


def encode_clinical_inputs(payload: Mapping[str, Any], model: Mapping[str, Any],
                           radiomics: Mapping[str, Any] | None = None) -> np.ndarray:
    """Encode the fixed clinical categories; no implicit feature-name remap."""
    if model.get("model_id") == UCSF_MODEL_ID:
        schema = model.get("features", {}).get("input_schema", {})
        if set(payload) != set(schema.get("inputs", [])):
            raise SurvivalModelError("UCSF input must contain exactly age_years and sex.")
        try:
            age = float(payload["age_years"])
        except (TypeError, ValueError) as error:
            raise SurvivalModelError("Age must be a finite numeric value in years.") from error
        if not math.isfinite(age):
            raise SurvivalModelError("Age must be finite.")
        age_range = model["features"].get("training_ranges", {}).get("age_years", [])
        if len(age_range) != 2 or not age_range[0] <= age <= age_range[1]:
            raise SurvivalModelError("Age is outside the UCSF model training range.")
        sex = payload.get("sex")
        if sex not in ("F", "M"):
            raise SurvivalModelError("Sex must be one of the UCSF model categories: F or M.")
        if radiomics is not None:
            raise SurvivalModelError("UCSF clinical model does not accept CaPTk or BrainFusion radiomics.")
        encoded = {"age_at_mri_years": age, "sex_M": float(sex == "M")}
        return np.asarray([encoded[name] for name in model["features"]["names"]], dtype=float)
    schema = model.get("features", {}).get("encoding", {})
    required = schema.get("inputs")
    if not isinstance(required, list) or set(required) != {"age_years", "gender", "IDH1", "GTR_over90percent"}:
        raise SurvivalModelError("Clinical input schema is incompatible with this model.")
    if set(payload) != set(required):
        raise SurvivalModelError("Clinical input fields are missing or unexpected.")
    try:
        age = float(payload["age_years"])
    except (TypeError, ValueError) as error:
        raise SurvivalModelError("Age must be a finite numeric value in years.") from error
    if not math.isfinite(age):
        raise SurvivalModelError("Age must be finite.")
    ranges = model["features"].get("training_ranges", {})
    age_range = ranges.get("age_years")
    if not isinstance(age_range, list) or len(age_range) != 2 or not age_range[0] <= age <= age_range[1]:
        raise SurvivalModelError("Age is outside the model training range.")

    gender = payload["gender"]
    idh = payload["IDH1"]
    gtr = payload["GTR_over90percent"]
    if gender not in ("F", "M"):
        raise SurvivalModelError("Gender must be one of the model's supported categories: F or M.")
    if idh not in ("Wildtype", "Mutated", "NOS/NEC"):
        raise SurvivalModelError("IDH1 category is not supported by the model contract.")
    if gtr not in ("N", "Y", "UNKNOWN"):
        raise SurvivalModelError("Resection category is not supported by the model contract.")

    encoded: dict[str, float] = {
        "age_years": age,
        "gender_M": float(gender == "M"),
        "IDH1_mutated": float(idh == "Mutated"),
        "IDH1_NOS_NEC": float(idh == "NOS/NEC"),
        "GTR_over90pct_Y": float(gtr == "Y"),
        "GTR_unknown": float(gtr == "UNKNOWN"),
        "GTR_over_90pct": float(gtr == "Y") if gtr in ("N", "Y") else math.nan,
    }
    names = model["features"]["names"]
    radiomics_schema = model["features"].get("radiomics")
    expected_radiomics = (set(radiomics_schema.get("required_inputs", []))
                          if isinstance(radiomics_schema, dict) else set())
    if expected_radiomics:
        if not isinstance(radiomics, Mapping) or set(radiomics) != expected_radiomics:
            raise SurvivalModelError("Fusion model requires exactly its registered CaPTk radiomics features.")
        for feature in expected_radiomics:
            try:
                value = float(radiomics[feature])
            except (TypeError, ValueError) as error:
                raise SurvivalModelError(f"CaPTk feature {feature} must be numeric.") from error
            if not math.isfinite(value):
                raise SurvivalModelError(f"CaPTk feature {feature} must be finite.")
            encoded[feature] = value
    elif radiomics is not None:
        raise SurvivalModelError("Radiomics input is incompatible with the clinical-only model.")
    if not set(names).issubset(encoded) or len(names) != len(set(names)):
        raise SurvivalModelError("Clinical feature order is incompatible with the registered model.")
    return np.asarray([encoded[name] for name in names], dtype=float)


def predict(model: Mapping[str, Any], payload: Mapping[str, Any], times_days: list[float],
            radiomics: Mapping[str, Any] | None = None) -> dict:
    if not isinstance(times_days, list) or not 1 <= len(times_days) <= 24:
        raise SurvivalModelError("Provide between 1 and 24 requested time points in days.")
    requested = np.asarray(times_days, dtype=float)
    if not np.isfinite(requested).all() or np.any(requested <= 0):
        raise SurvivalModelError("Requested survival times must be positive finite days.")
    if np.any(np.diff(requested) < 0):
        raise SurvivalModelError("Requested times must be sorted in ascending order.")
    if requested[-1] > float(model["baseline"]["times_days"][-1]):
        raise SurvivalModelError("Requested time exceeds observed model event follow-up; extrapolation is disabled.")
    x = encode_clinical_inputs(payload, model, radiomics)
    features = model["features"]
    if not np.isfinite(x).all():
        medians = features.get("imputation_medians")
        if (not isinstance(medians, list) or len(medians) != len(x)
                or not np.isfinite(np.asarray(medians, dtype=float)).all()):
            raise SurvivalModelError("Model has no valid imputation values for missing covariates.")
        x = np.where(np.isfinite(x), x, np.asarray(medians, dtype=float))
    z = (x - np.asarray(features["means"], dtype=float)) / np.asarray(features["scales"], dtype=float)
    linear_predictor = float(z @ np.asarray(features["coefficients_standardized"], dtype=float))
    if not math.isfinite(linear_predictor) or abs(linear_predictor) > 50:
        raise SurvivalModelError("Relative risk is numerically outside the supported range.")
    relative_risk = math.exp(linear_predictor)

    baseline = model["baseline"]
    event_times = np.asarray(baseline["times_days"], dtype=float)
    cumulative_hazard = np.asarray(baseline["cumulative_hazard"], dtype=float)
    points = []
    for time in requested.tolist():
        index = int(np.searchsorted(event_times, time, side="right") - 1)
        h0 = float(cumulative_hazard[index]) if index >= 0 else 0.0
        probability = math.exp(-h0 * relative_risk)
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise SurvivalModelError("Computed survival probability is outside [0, 1].")
        points.append({"time": float(time), "time_unit": "days", "survival_probability": probability})
    return {
        "model_id": model["model_id"],
        "model_version": model["model_version"],
        "research_only": True,
        "endpoint_status": model["endpoint"]["status"],
        "prediction_type": "relative_risk_and_exploratory_survival_probability",
        "relative_risk": relative_risk,
        "survival_curve": points,
        "time_unit": "days",
        "limitations": model["limitations"],
        "individual_prediction_saved": False,
    }


def public_model(model: Mapping[str, Any]) -> dict:
    return {
        "model_id": model["model_id"],
        "model_version": model["model_version"],
        "model_type": model["model_type"],
        "research_only": True,
        "endpoint_status": model["endpoint"]["status"],
        "official_endpoint_validated": model["endpoint"].get("official_endpoint_validated") is True,
        "dataset": model.get("dataset"),
        "time_unit": model["endpoint"]["time_unit"],
        "feature_names": model["features"]["names"],
        "training": model["training"],
        "validation": model["validation"],
        "limitations": model["limitations"],
        "radiomics": model["features"].get("radiomics"),
    }
