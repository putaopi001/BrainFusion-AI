from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置（可用环境变量 / .env 覆盖）。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    PROJECT_NAME: str = "BrainFusion-AI"
    VERSION: str = "0.1.0"
    DATABASE_URL: str = "sqlite:///./brainfusion.db"
    LOG_LEVEL: str = "INFO"

    # CORS 允许来源（逗号分隔字符串，部署时通过环境变量覆盖）
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
