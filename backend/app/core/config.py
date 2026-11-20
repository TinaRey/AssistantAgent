from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (or a local .env)."""

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    cors_origins: str = Field(default="http://localhost:3000")
    app_password: str = ""
    secret_key: str = ""  # signs session cookies; long random string
    cookie_secure: bool = False  # set true when served over HTTPS
    database_url: str = ""
    search_api_key: str = ""
    max_tool_iterations: int = Field(default=6, ge=1, le=15)
    llm_timeout_s: float = 60.0
    storage_dir: str = "storage"
    embedding_model: str = "text-embedding-3-small"
    max_upload_mb: int = 10

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
