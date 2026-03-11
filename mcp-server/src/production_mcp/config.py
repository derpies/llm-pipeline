"""Server configuration — all production credentials loaded from environment."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Redis
    redis_url: str = ""

    # Postgres
    postgres_url: str = ""

    # OpenSearch
    opensearch_url: str = ""
    opensearch_user: str = ""
    opensearch_password: str = ""

    # S3
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""


settings = Settings()
