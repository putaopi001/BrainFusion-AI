from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.prediction import Prediction


router = APIRouter()


def serialize_prediction(p: Prediction) -> dict:
    return {
        "id": p.id,
        "case_id": p.case_id,
        "tumor_probability": p.tumor_probability,
        "risk_score": p.risk_score,
        "fusion_score": p.fusion_score,
        "risk_level": p.risk_level,
        "model_version": p.model_version,
        "created_time": p.created_time.isoformat() if p.created_time else None,
        "source": "legacy_unverified",
        "current": False,
        "disclaimer": "Historical unvalidated output; not a current model prediction or clinical assessment.",
    }


@router.get("/prediction/{case_id}")
def get_prediction(case_id: int, db: Session = Depends(get_db)):
    raise HTTPException(503, "No validated tumor probability or clinical risk model is available. "
                        "IDH research results are available separately under /research.")


@router.get("/debug/predictions")
def debug_predictions(db: Session = Depends(get_db)):
    items = db.query(Prediction).all()
    return {"code": 200, "available": False, "source": "legacy_unverified",
            "message": "Archive only; these records are excluded from current results and reports.",
            "data": [serialize_prediction(item) for item in items]}
