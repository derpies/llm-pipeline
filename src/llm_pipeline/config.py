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

    # Embeddings
    embedding_provider: str = "huggingface"  # "huggingface" or "openai"
    embedding_model: str = ""  # empty = provider default

    # ChromaDB
    chroma_persist_dir: str = "./chroma_data"

    # Ingestion
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # Email Analytics
    email_json_format: str = "ndjson"  # "ndjson" or "concatenated"
    email_stream_buffer_size: int = 65536
    email_batch_size: int = 10000
    email_time_window_hours: int = 1
    email_lookback_days: int = 30
    email_anomaly_threshold: float = 3.5
    email_trend_min_points: int = 5
    email_trend_r_squared_min: float = 0.5
    email_trend_slope_min: float = 0.01

    # Summarization
    summarization_top_dimensions: int = 10
    summarization_max_narratives: int = 20

    # Logging
    log_level: str = "INFO"
    log_format: str = "dev"  # "dev" for pretty-print, "json" for structured


settings = Settings()
