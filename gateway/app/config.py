import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./hbk.db"
    JWT_SECRET: str = "hbk-insecure-dev-jwt-secret-replace-in-production-min-32-chars"
    HERMES_API_KEY: str = "hbk-hermes-secret-key-pilot-2026"
    ENROLLMENT_KEY_LENGTH: int = 16

    HEARTBEAT_INTERVAL_SEC: int = 30
    OFFLINE_AFTER_SEC: int = 90
    METRICS_RETENTION_DAYS: int = 90
    FBR_RETENTION_DAYS: int = 30

    # Pakistan Hypermarket Standard Timezone
    EXPECTED_TIMEZONE: str = "Pakistan Standard Time"

    # Defaults include http://localhost:3000 for dashboard
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,*"

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    CHAT_LLM_BASE_URL: str = ""
    CHAT_LLM_API_KEY: str = ""
    CHAT_LLM_MODEL: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def cors_origins_list(self) -> List[str]:
        if not self.CORS_ORIGINS:
            return ["http://localhost:3000", "http://127.0.0.1:3000"]
        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        if "http://localhost:3000" not in origins:
            origins.append("http://localhost:3000")
        return origins

settings = Settings()
