from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./growthos.db"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://127.0.0.1:8000/calendar/callback"
    frontend_url: str = "http://localhost:3000"  # OAuth callbacks redirect back here
    ai_provider: str = "none"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    scheduler_enabled: bool = True  # weekly source refresh + refresh on startup
    # Sources (V1). Empty credentials = the adapter reports "not configured" and is skipped.
    sources_enabled: str = "curated,devpost,kaggle"
    kaggle_username: str = ""
    kaggle_key: str = ""
    # OpenAI-compatible LLM gateway (OmniRoute) — extraction only, never scoring (ADR 0003, 0006).
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "auto/fast"

    @property
    def enabled_sources(self) -> set[str]:
        return {s.strip() for s in self.sources_enabled.split(",") if s.strip()}

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
