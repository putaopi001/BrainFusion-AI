from fastapi import APIRouter, Depends
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
    }


@router.get("/prediction/{case_id}")
def get_prediction(case_id: int, db: Session = Depends(get_db)):
    result = (
        db.query(Prediction)
        .filter(Prediction.case_id == case_id)
        .order_by(Prediction.id.desc())
        .first()
    )
    if result is None:
        return {"code": 404, "message": "no prediction", "data": None}
    return {"code": 200, "data": serialize_prediction(result)}


@router.get("/debug/predictions")
def debug_predictions(db: Session = Depends(get_db)):
    items = db.query(Prediction).all()
    return {"code": 200, "data": [serialize_prediction(item) for item in items]}
