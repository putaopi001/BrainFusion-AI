from fastapi import APIRouter

from app.core.config import settings
from app.core.response import success


router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/system")
def system_info():
    return success(
        data={
            "version": f"BrainFusion-AI v{settings.VERSION}",
            "models": [
                {"name": "MRI Baseline Model", "status": "active"},
                {"name": "TabICL-v2", "status": "active"},
                {"name": "Fusion Model", "status": "active"},
                {"name": "Clinical Agent", "status": "active"},
            ],
        }
    )
