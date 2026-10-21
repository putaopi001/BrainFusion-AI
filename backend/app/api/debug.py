from fastapi import APIRouter
from pathlib import Path

from app.core.config import settings
from app.core.response import success


router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/system")
def system_info():
    return success(
        data={
            "version": f"BrainFusion-AI v{settings.VERSION}",
            "models": [
                {"name": "MONAI BraTS SegResNet", "status": "ready" if (Path(settings.MODEL_DIR) / "models/model.pt").is_file() else "weights_missing"},
            ],
            "planned_models": ["IDH classifier", "TOPSIS fusion", "simulated federated model"],
        }
    )
