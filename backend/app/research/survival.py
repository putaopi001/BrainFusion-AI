"""Explicit survival endpoint validation and Kaplan-Meier estimation.

This module accepts already-authorized research rows only. It has no default
endpoint mapping and never guesses a time origin or event coding.
"""
from dataclasses import dataclass
import math
from typing import Mapping, Sequence

import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp
from scipy.stats import spearmanr


@dataclass(frozen=True)
class EndpointContract:
    endpoint: str
    patient_id: str
    duration: str
    event: str
    time_origin: str
    expected_time_origin: str
    time_unit: str
    event_value: str
    censored_value: str
    research_use_authorized: bool


def validate_endpoint(rows: Sequence[Mapping], contract: EndpointContract) -> dict:
    """Validate endpoint rows without inferring missing semantics.

    Event/censor encodings are compared as strings against the caller's
    explicit mapping. Time origin must be declared on every row and match the
    contract. No patient-level values are returned in the audit summary.
    """
    problems = []
    if contract.endpoint not in {"OS", "PFS"}:
        problems.append("unsupported_endpoint")
    if contract.time_unit not in {"days", "months", "years"}:
        problems.append("unsupported_time_unit")
    if not contract.expected_time_origin.strip():
        problems.append("expected_time_origin_missing")
    if contract.event_value == contract.censored_value:
        problems.append("event_mapping_ambiguous")
    if not contract.research_use_authorized:
        problems.append("research_use_not_authorized")

    seen = set()
    valid = []
    counts = {"events": 0, "censored": 0}
    for index, row in enumerate(rows):
        patient = str(row.get(contract.patient_id, "")).strip()
        if not patient:
            problems.append(f"row_{index}:patient_id_missing")
            continue
        if patient in seen:
            problems.append(f"row_{index}:duplicate_patient")
            continue
        seen.add(patient)

        origin = str(row.get(contract.time_origin, "")).strip()
        if not origin or origin != contract.expected_time_origin:
            problems.append(f"row_{index}:time_origin_mismatch")
            continue
        try:
            duration = float(row.get(contract.duration))
        except (TypeError, ValueError):
            problems.append(f"row_{index}:duration_invalid")
            continue
        if not math.isfinite(duration) or duration <= 0:
            problems.append(f"row_{index}:duration_nonpositive_or_nonfinite")
            continue

        event = str(row.get(contract.event, "")).strip()
        if event == contract.event_value:
            observed = 1
            counts["events"] += 1
        elif event == contract.censored_value:
            observed = 0
            counts["censored"] += 1
        else:
            problems.append(f"row_{index}:event_status_invalid")
            continue
        valid.append({"duration": duration, "event": observed})

    if not rows:
        problems.append("dataset_empty")
    if len(valid) != len(rows):
        problems.append("one_or_more_rows_invalid")
    problems = list(dict.fromkeys(problems))
    eligible = not problems and bool(valid)
    return {
        "endpoint": contract.endpoint,
        "status": "eligible_for_analysis" if eligible else "blocked",
        "eligible": eligible,
        "time_unit": contract.time_unit,
        "time_origin": contract.expected_time_origin,
        "sample_count": len(valid),
        "event_count": counts["events"],
        "censored_count": counts["censored"],
        "issues": problems,
        "_validated_rows": valid,
    }


def public_validation(validation: Mapping) -> dict:
    """Return counts and blockers without exposing normalized patient rows."""
    return {key: value for key, value in validation.items() if not key.startswith("_")}


def kaplan_meier(validation: Mapping) -> dict:
    """Return KM step points, risk counts, Greenwood log-log CIs and median."""
    if not validation.get("eligible"):
        raise ValueError("A validated and authorized endpoint is required")
    rows = validation.get("_validated_rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Validated endpoint rows are unavailable")
    z = 1.959963984540054
    survival = 1.0
    greenwood = 0.0
    points = []
    median = None
    observed_times = sorted({float(row["duration"]) for row in rows})
    for time in observed_times:
        at_risk = sum(float(row["duration"]) >= time for row in rows)
        events = sum(float(row["duration"]) == time and row["event"] == 1 for row in rows)
        censored = sum(float(row["duration"]) == time and row["event"] == 0 for row in rows)
        if at_risk <= 0 or events > at_risk:
            raise ValueError("Invalid risk set")
        if events:
            survival *= 1.0 - events / at_risk
        if events and at_risk > events:
            greenwood += events / (at_risk * (at_risk - events))
        if survival >= 1:
            lower, upper = 1.0, 1.0
        elif survival <= 0:
            lower, upper = 0.0, 0.0
        else:
            log_survival = math.log(survival)
            standard_error = math.sqrt(greenwood) / abs(log_survival) if greenwood else 0.0
            eta = math.log(-log_survival)
            lower = math.exp(-math.exp(eta + z * standard_error))
            upper = math.exp(-math.exp(eta - z * standard_error))
        points.append({"time": time, "at_risk": at_risk, "events": events,
                       "censored_at_time": censored, "survival": survival,
                       "ci95_lower": lower, "ci95_upper": upper})
        if median is None and survival <= 0.5:
            median = time
    return {
        "endpoint": validation["endpoint"],
        "time_unit": validation["time_unit"],
        "time_origin": validation["time_origin"],
        "sample_count": validation["sample_count"],
        "event_count": validation["event_count"],
        "censored_count": validation["censored_count"],
        "median_survival": median,
        "points": points,
        "method": "Kaplan-Meier; Greenwood variance; log-log 95% confidence interval",
        "scope": "research summary; not an individual prediction",
    }


def cox_ph(validation: Mapping, features, feature_names: Sequence[str], l2: float = 0.1) -> dict:
    """Fit a ridge-regularized Cox PH model with Breslow ties.

    This software primitive consumes only rows produced by ``validate_endpoint``.
    It returns coefficients and an exploratory Schoenfeld-residual trend check;
    it does not produce individual survival-time predictions or a baseline
    survival function. A proper patient-level validation design remains the
    caller's responsibility.
    """
    if not validation.get("eligible"):
        raise ValueError("A validated and authorized endpoint is required")
    rows = validation.get("_validated_rows")
    matrix = np.asarray(features, dtype=float)
    names = [str(name).strip() for name in feature_names]
    if not isinstance(rows, list) or not rows:
        raise ValueError("Validated endpoint rows are unavailable")
    if matrix.ndim != 2 or matrix.shape != (len(rows), len(names)) or not names:
        raise ValueError("Feature matrix must match validated rows and named columns")
    if len(set(names)) != len(names) or any(not name for name in names):
        raise ValueError("Feature names must be non-empty and unique")
    if not np.isfinite(matrix).all():
        raise ValueError("Cox features must be finite; imputation must be explicit upstream")
    if not math.isfinite(l2) or l2 <= 0:
        raise ValueError("A positive finite L2 penalty is required")

    durations = np.asarray([row["duration"] for row in rows], dtype=float)
    events = np.asarray([row["event"] for row in rows], dtype=int)
    event_times = np.unique(durations[events == 1])
    if len(event_times) < 2 or events.sum() < 3:
        raise ValueError("Cox PH requires at least three events across two event times")
    means = matrix.mean(axis=0)
    scales = matrix.std(axis=0)
    if np.any(scales <= np.finfo(float).eps):
        raise ValueError("Constant features must be removed before Cox fitting")
    standardized = (matrix - means) / scales
    event_sets = [(time, np.flatnonzero((durations == time) & (events == 1)),
                   np.flatnonzero(durations >= time)) for time in event_times]

    def objective(beta):
        log_likelihood = -0.5 * l2 * float(beta @ beta)
        gradient = -l2 * beta.copy()
        for _, deaths, risk_set in event_sets:
            risk_x = standardized[risk_set]
            risk_scores = risk_x @ beta
            log_denominator = logsumexp(risk_scores)
            weights = np.exp(risk_scores - log_denominator)
            count = len(deaths)
            log_likelihood += float(standardized[deaths].sum(axis=0) @ beta) - count * log_denominator
            gradient += standardized[deaths].sum(axis=0) - count * (weights @ risk_x)
        return -log_likelihood, -gradient

    fit = minimize(objective, np.zeros(matrix.shape[1]), jac=True, method="L-BFGS-B")
    if not np.isfinite(fit.x).all():
        raise ValueError("Cox optimization produced non-finite coefficients")

    # Schoenfeld residual trend is a screening diagnostic, not a definitive PH test.
    residuals = []
    residual_times = []
    for time, deaths, risk_set in event_sets:
        scores = standardized[risk_set] @ fit.x
        weights = np.exp(scores - logsumexp(scores))
        residuals.extend(standardized[deaths].mean(axis=0) - weights @ standardized[risk_set])
        residual_times.extend([float(time)] * len(deaths))
    residual_matrix = np.asarray(residuals, dtype=float).reshape(-1, matrix.shape[1])
    log_times = np.log(np.asarray(residual_times, dtype=float))
    checks = {}
    for index, name in enumerate(names):
        if len(np.unique(log_times)) >= 3 and np.std(residual_matrix[:, index]) > 0:
            statistic = spearmanr(log_times, residual_matrix[:, index])
            checks[name] = {"spearman_rho": float(statistic.statistic),
                            "p_value_screening_only": float(statistic.pvalue)}
        else:
            checks[name] = {"spearman_rho": None, "p_value_screening_only": None,
                            "reason": "insufficient variation for screening"}

    return {
        "endpoint": validation["endpoint"],
        "time_unit": validation["time_unit"],
        "time_origin": validation["time_origin"],
        "sample_count": len(rows),
        "event_count": int(events.sum()),
        "feature_names": names,
        "coefficients": {name: float(beta / scale) for name, beta, scale in zip(names, fit.x, scales)},
        "converged": bool(fit.success),
        "optimizer_message": str(fit.message),
        "l2_penalty": float(l2),
        "tie_method": "Breslow",
        "proportional_hazards_screening": {
            "method": "Spearman trend of scaled Schoenfeld residuals against log event time",
            "formal_test": False,
            "multiple_testing_adjusted": False,
            "features": checks,
        },
        "individual_predictions_available": False,
        "scope": "research software fit; requires patient-level validation before interpretation",
    }


def concordance_index(durations, events, risk_scores) -> float:
    """Harrell C-index; larger risk scores mean earlier events."""
    durations = np.asarray(durations, dtype=float)
    events = np.asarray(events, dtype=int)
    risk_scores = np.asarray(risk_scores, dtype=float)
    if durations.ndim != 1 or events.shape != durations.shape or risk_scores.shape != durations.shape:
        raise ValueError("Durations, event indicators, and risk scores must be aligned vectors")
    if not len(durations) or not np.isfinite(durations).all() or not np.isfinite(risk_scores).all():
        raise ValueError("C-index inputs must be non-empty and finite")
    if not np.isin(events, [0, 1]).all() or np.any(durations <= 0):
        raise ValueError("C-index requires positive durations and binary event indicators")
    concordant = 0.0
    comparable = 0
    for i in range(len(durations)):
        if events[i] != 1:
            continue
        for j in range(len(durations)):
            if durations[i] >= durations[j]:
                continue
            comparable += 1
            if risk_scores[i] > risk_scores[j]:
                concordant += 1
            elif risk_scores[i] == risk_scores[j]:
                concordant += 0.5
    if not comparable:
        raise ValueError("C-index has no comparable event pairs")
    return concordant / comparable
