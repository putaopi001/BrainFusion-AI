def predict_survival(*_args, **_kwargs) -> dict:
    """Keep individual survival estimates closed until a validated model exists."""
    return {
        "status": "BLOCKED_BY_DATA",
        "individual_prediction_available": False,
        "reason": "No research-authorized, endpoint-consistent survival model is available.",
    }
