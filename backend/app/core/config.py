from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str  # postgresql+asyncpg://...
    database_url_sync: str  # postgresql://... for alembic
    # API keys are optional in Phase 1 — unused until Phase 3+ (LLM extraction).
    # Making them required would crash test collection when keys are absent.
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    environment: str = "development"

    class Config:
        env_file = ".env"


settings = Settings()
