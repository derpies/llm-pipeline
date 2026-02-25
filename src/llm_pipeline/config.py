"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-20250514"

    # Postgres
    database_url: str = "postgresql://llm_pipeline:llm_pipeline@postgres:5432/llm_pipeline"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # ChromaDB
    chroma_persist_dir: str = "./chroma_data"

    # Ingestion
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # Logging
    log_level: str = "INFO"
    log_format: str = "dev"  # "dev" for pretty-print, "json" for structured


settings = Settings()
