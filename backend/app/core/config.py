from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (or a local .env)."""

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    environment: Literal["development", "production"] = "development"
    internal_api_key: str = ""  # shared with the frontend proxy; protects the public backend
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    cors_origins: str = Field(default="http://localhost:3000")
    app_password: str = ""
    secret_key: str = ""  # signs session cookies; long random string
    cookie_secure: bool = False  # set true when served over HTTPS
    database_url: str = ""
    search_api_key: str = ""
    search_timeout_s: float = 15.0
    max_tool_iterations: int = Field(default=6, ge=1, le=15)
    llm_timeout_s: float = 60.0
    storage_dir: str = "storage"
    image_model: str = "gpt-image-2"
    image_quality: str = "medium"
    image_size: str = "1024x1024"
    image_timeout_s: float = 120.0
    max_images_per_presentation: int = 6
    image_cost_estimate_usd: float = 0.05  # shown to the user; indicative only
    embedding_model: str = "text-embedding-3-small"
    max_upload_mb: int = 10

    @field_validator("database_url")
    @classmethod
    def _driver(cls, url: str) -> str:
        """Accept the plain URL that Supabase/Render give (postgres:// or postgresql://)."""
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix) :]
        return url

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def production_problems(self) -> list[str]:
        """Settings that must be right before serving real users."""
        problems = []
        if len(self.app_password) < 10:
            problems.append("APP_PASSWORD must be set (at least 10 characters)")
        if len(self.secret_key) < 32:
            problems.append("SECRET_KEY must be set (at least 32 characters)")
        if len(self.internal_api_key) < 32:
            problems.append("INTERNAL_API_KEY must be set (at least 32 characters)")
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE must be true (the app is served over HTTPS)")
        if not self.database_url:
            problems.append("DATABASE_URL must be set")
        return problems

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
