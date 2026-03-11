"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_provider: str = "anthropic"  # "anthropic", "openai", or "dry-run"
    llm_model: str = "claude-sonnet-4-20250514"

    # Per-agent model selection
    model_orchestrator: str = "claude-sonnet-4-20250514"
    model_investigator: str = "claude-sonnet-4-20250514"
    model_investigator_deep: str = "claude-opus-4-20250514"
    model_synthesizer: str = "claude-sonnet-4-20250514"
    model_reviewer: str = "claude-sonnet-4-20250514"
    model_curator: str = "claude-haiku-4-5-20251001"

    # Circuit breaker thresholds
    circuit_breaker_max_iterations: int = 5
    circuit_breaker_max_tokens: int = 100_000
    circuit_breaker_max_seconds: int = 300
    circuit_breaker_max_topics: int = 1
    circuit_breaker_max_spend_usd: float = 10.00

    # Postgres
    database_url: str = "postgresql://llm_pipeline:llm_pipeline@postgres:5432/llm_pipeline"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Embeddings
    embedding_provider: str = "huggingface"  # "huggingface" or "openai"
    embedding_model: str = ""  # empty = provider default

    # Weaviate
    weaviate_url: str = "http://weaviate:8080"
    weaviate_grpc_url: str = "weaviate:50051"

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

    # Investigation
    investigator_use_knowledge_store: bool = True
    investigator_max_llm_calls: int = 15
    investigator_max_consecutive_errors: int = 3
    reviewer_max_llm_calls: int = 3

    # Summarization
    summarization_top_dimensions: int = 10
    summarization_max_narratives: int = 20

    # Rate limiting
    rate_limit_tokens_per_minute: int = 25_000  # input tokens/min (Anthropic limit: 30K)

    # Production MCP server
    production_mcp_url: str = "http://production-mcp:8000/mcp"
    production_mcp_enabled: bool = False

    # Logging
    log_level: str = "INFO"
    log_format: str = "dev"  # "dev" for pretty-print, "json" for structured
    log_dir: str = "output/logs"  # directory for persistent log files


settings = Settings()
