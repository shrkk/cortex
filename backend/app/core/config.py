from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str  # postgresql+asyncpg://...
    database_url_sync: str  # postgresql://... for alembic
    openai_api_key: str
    anthropic_api_key: str
    environment: str = "development"

    class Config:
        env_file = ".env"


settings = Settings()
