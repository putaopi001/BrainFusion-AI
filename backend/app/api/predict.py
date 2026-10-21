from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.analysis import start_analysis
router = APIRouter(prefix="/predict", tags=["predict"])

@router.post("/{case_id}", status_code=202)
def predict(case_id: int, db: Session = Depends(get_db)):
    """Compatibility route: submit a real analysis job."""
    return start_analysis(case_id, db)
