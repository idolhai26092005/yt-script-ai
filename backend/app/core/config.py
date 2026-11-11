from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from typing import Optional

# Runtime config guard: deployment flags live in typed settings so Render/Supabase
# behavior stays explicit and cleanup work does not hide feature-state in routers.
class Settings(BaseSettings):
    ENV: str = "production"
    ADMIN_SECRET: str
    DATABASE_URL: str = "sqlite:////home/nhnam200512/Desktop/MyProject/yt_script_ai/backend/sql_app.db"
    GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    ALLOWED_ORIGINS: str = ""
    PROXY_URL: Optional[str] = None
    DEBUG_SNAPSHOTS: bool = False
    ENABLE_SERIES_FLOW: bool = True
    AUTO_RUN_MIGRATIONS: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @model_validator(mode="after")
    def validate_production_admin_secret(self) -> "Settings":
        env_clean = self.ENV.strip('\'"').strip().lower()
        secret_clean = self.ADMIN_SECRET.strip('\'"').strip()
        if env_clean == "production" and (not secret_clean or secret_clean == "admin_secret_key_here"):
            raise ValueError("CRITICAL: ADMIN_SECRET cannot be default or empty in production mode.")
        return self

settings = Settings()
