from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    """应用配置（可用环境变量 / .env 覆盖）。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    PROJECT_NAME: str = "BrainFusion-AI"
    VERSION: str = "0.1.0"
    DATABASE_URL: str = "sqlite:///./brainfusion.db"
    UPLOAD_DIR: str = str(Path(__file__).resolve().parents[2] / 'uploads')
    LOG_LEVEL: str = "INFO"
    MODEL_DIR: str = "E:/BrainFusion-Runtime/models/monai-brats"
    GPU_BUDGET_MB: int = 6000
    RESEARCH_DIR: str = "E:/BrainFusion-Runtime/results/research"
    DATASET_DIR: str = "E:/BrainFusion-Data/WAW-GliomAI-v3"
    RADIOMICS_PYTHON: str = "E:/BrainFusion-Runtime/envs/radiomics39/python.exe"
    RADIOMICS_COMPATIBILITY: str = "E:/BrainFusion-Runtime/results/stage6/compatibility.json"
    FEATURE_JOBS_DIR: str = "E:/BrainFusion-Runtime/results/feature_jobs"
    PACS_CONFIG_FILE: str = "E:/BrainFusion-Runtime/local/pacs-config.json"
    PACS_ALLOW_DOCKER_HOST: bool = False
    PACS_RESEARCH_DEMO_PIXEL_READ: bool = False
    PACS_IMPORT_REGISTRY_FILE: str = "E:/BrainFusion-Runtime/local/pacs-import-candidates.json"
    PACS_IMPORT_JOBS_DIR: str = "E:/BrainFusion-Runtime/local/pacs-imports"
    PACS_DERIVED_DIR: str = "E:/BrainFusion-Data/PACS-derived"
    DICOM_QUARANTINE_DIR: str = "E:/BrainFusion-Runtime/dicom-quarantine"
    LOCAL_AUTH_FILE: str = "E:/BrainFusion-Runtime/local/local-users.json"
    DICOM_CONVERSION_INDEX_FILE: str = "E:/BrainFusion-Runtime/local/dicom-conversions.json"
    # Research survival inference is opt-in and disabled in every deployment
    # unless a separately reviewed model artifact and explicit research-only
    # runtime configuration are supplied.
    SURVIVAL_MODEL_DIR: str = ""
    SURVIVAL_FUSION_MODEL_DIR: str = ""
    SURVIVAL_UCSF_MODEL_DIR: str = ""
    SURVIVAL_RESEARCH_PREDICTION_ENABLED: bool = False

    # CORS 允许来源（逗号分隔字符串，部署时通过环境变量覆盖）
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
