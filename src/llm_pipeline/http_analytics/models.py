"""Data models for HTTP access log analytics.

Pydantic models for event parsing and output schemas.
SQLAlchemy models for Postgres persistence.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, computed_field, model_validator
from sqlalchemy import DateTime, Enum, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from llm_pipeline.models.db import Base

# Reuse TrendDirection from email analytics — same semantics
from llm_pipeline.email_analytics.models import TrendDirection  # noqa: F401

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RequestCategory(enum.StrEnum):
    PHP_PROBE = "php_probe"
    TRACKING_PIXEL = "tracking_pixel"
    CLICK_TRACKING = "click_tracking"
    PAGE_LOAD = "page_load"
    STATIC_ASSET = "static_asset"
    API_CALL = "api_call"
    WEBSOCKET = "websocket"
    OTHER = "other"


class HostCategory(enum.StrEnum):
    ONTRAPORT_COM = "ontraport.com"
    ONTRALINK_COM = "ontralink.com"
    ONTRAPORT_NET = "ontraport.net"
    CUSTOM_DOMAIN = "custom_domain"


class UaCategory(enum.StrEnum):
    REAL_BROWSER = "real_browser"
    BOT_CRAWLER = "bot_crawler"
    SCANNER = "scanner"
    EMPTY = "empty"
    CURL = "curl"
    EMAIL_CLIENT = "email_client"
    APPLE_MPP = "apple_mpp"
    OTHER = "other"


class StatusClass(enum.StrEnum):
    S2XX = "2xx"
    S3XX = "3xx"
    S4XX = "4xx"
    S5XX = "5xx"
    S679 = "679"
    OTHER = "other"


class HttpAnomalyType(enum.StrEnum):
    ERROR_RATE_SPIKE = "error_rate_spike"
    LATENCY_SPIKE = "latency_spike"
    TRAFFIC_SPIKE = "traffic_spike"
    TRAFFIC_DROP = "traffic_drop"
    STATUS_679_SPIKE = "status_679_spike"
    BOT_TRAFFIC_SPIKE = "bot_traffic_spike"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def classify_status(code: int) -> StatusClass:
    """Map an HTTP status code to its class."""
    if code == 679:
        return StatusClass.S679
    if 200 <= code < 300:
        return StatusClass.S2XX
    if 300 <= code < 400:
        return StatusClass.S3XX
    if 400 <= code < 500:
        return StatusClass.S4XX
    if 500 <= code < 600:
        return StatusClass.S5XX
    return StatusClass.OTHER


# ---------------------------------------------------------------------------
# Pydantic event model
# ---------------------------------------------------------------------------


class HttpAccessEvent(BaseModel, extra="ignore"):
    """A single HTTP access log event parsed from NDJSON."""

    model_config = {"arbitrary_types_allowed": True}

    # Raw fields (names match JSON keys, with hyphens converted)
    isotime: str = ""
    server: str = ""
    remoteaddr: str = ""
    http_host: str = Field("", alias="http-host")
    request: str = ""
    http_status: str = Field("0", alias="http-status")
    sizesent: str = "0"
    tts: str = "0"
    upstream: str = ""
    http_referrer: str = Field("", alias="http-referrer")
    useragent: str = ""
    applempp: str = "FALSE"
    xff: str = ""
    trueip: str = ""
    accountid: str = ""
    session: str = ""
    uuid: str = ""
    log_type: str = ""
    remoteuser: str = ""
    time: str = ""
    http_orig_schema: str = Field("", alias="http-orig-schema")

    # Derived fields (populated by model_validator)
    http_method: str = ""
    request_path: str = ""
    request_category: RequestCategory = RequestCategory.OTHER
    host_category: HostCategory = HostCategory.CUSTOM_DOMAIN
    ua_category: UaCategory = UaCategory.OTHER
    status_class: StatusClass = StatusClass.OTHER
    status_code: int = 0
    is_apple_mpp: bool = False
    tts_seconds: float = 0.0
    size_bytes: int = 0

    @model_validator(mode="before")
    @classmethod
    def coerce_nulls(cls, data: Any) -> Any:
        """Coerce None values to empty strings for string fields."""
        if isinstance(data, dict):
            for key, val in data.items():
                if val is None:
                    data[key] = ""
        return data

    @model_validator(mode="after")
    def populate_derived_fields(self) -> HttpAccessEvent:
        """Parse request line and classify dimensions."""
        from llm_pipeline.http_analytics.classifier import (
            classify_host,
            classify_request,
            classify_useragent,
        )

        # Parse status code
        try:
            self.status_code = int(self.http_status)
        except (ValueError, TypeError):
            self.status_code = 0
        self.status_class = classify_status(self.status_code)

        # Parse request line → method + path + category
        self.http_method, self.request_path, self.request_category = classify_request(
            self.request
        )

        # Classify host
        self.host_category = classify_host(self.http_host)

        # Apple MPP
        self.is_apple_mpp = self.applempp.upper() == "TRUE"

        # Classify user agent
        self.ua_category = classify_useragent(self.useragent, self.is_apple_mpp)

        # Parse numeric fields
        try:
            self.tts_seconds = float(self.tts)
        except (ValueError, TypeError):
            self.tts_seconds = 0.0

        try:
            self.size_bytes = int(self.sizesent)
        except (ValueError, TypeError):
            self.size_bytes = 0

        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def event_time(self) -> datetime:
        """Parse isotime into a datetime object."""
        if self.isotime:
            try:
                return datetime.fromisoformat(self.isotime)
            except (ValueError, TypeError):
                pass
        return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Output schemas
# ---------------------------------------------------------------------------


class HttpAggregationBucket(BaseModel):
    """A single aggregation bucket — counts, rates, and latency for a dimension slice."""

    time_window: datetime
    dimension: str
    dimension_value: str

    # Counts
    total: int = 0
    status_2xx: int = 0
    status_3xx: int = 0
    status_4xx: int = 0
    status_5xx: int = 0
    status_679: int = 0
    status_other: int = 0

    # Rates
    success_rate: float = 0.0
    client_error_rate: float = 0.0
    server_error_rate: float = 0.0
    known_content_error_rate: float = 0.0

    # TTS latency percentiles (seconds)
    tts_p50: float | None = None
    tts_p90: float | None = None
    tts_p95: float | None = None
    tts_p99: float | None = None
    tts_max: float | None = None
    tts_mean: float | None = None

    # Size stats
    total_bytes: int = 0
    mean_bytes: float = 0.0

    # Completeness indicators
    empty_ua_count: int = 0
    empty_upstream_count: int = 0
    empty_referrer_count: int = 0


class HttpAnomalyFinding(BaseModel):
    """A detected anomaly in an HTTP metric."""

    anomaly_type: HttpAnomalyType
    dimension: str
    dimension_value: str
    metric: str
    current_value: float
    baseline_mean: float
    z_score: float
    severity: str = "medium"


class HttpTrendFinding(BaseModel):
    """A detected trend in an HTTP metric over time."""

    direction: TrendDirection
    dimension: str
    dimension_value: str
    metric: str
    slope: float
    r_squared: float
    num_points: int
    start_value: float
    end_value: float


class HttpDataCompleteness(BaseModel):
    """Empty/missing rates for a field within a dimension slice."""

    time_window: datetime
    dimension: str
    dimension_value: str
    total_records: int
    field_name: str
    empty_count: int
    empty_rate: float


class HttpAnalysisReport(BaseModel):
    """Complete output of an HTTP analytics run."""

    run_id: str
    started_at: datetime
    completed_at: datetime | None = None
    files_processed: int = 0
    events_parsed: int = 0
    source_files: list[str] = Field(default_factory=list)
    aggregations: list[HttpAggregationBucket] = Field(default_factory=list)
    completeness: list[HttpDataCompleteness] = Field(default_factory=list)
    anomalies: list[HttpAnomalyFinding] = Field(default_factory=list)
    trends: list[HttpTrendFinding] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# SQLAlchemy models
# ---------------------------------------------------------------------------


class HttpAggregationRecord(Base):
    __tablename__ = "http_aggregations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    time_window: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    dimension: Mapped[str] = mapped_column(String(64), index=True)
    dimension_value: Mapped[str] = mapped_column(String(256))
    total: Mapped[int] = mapped_column(Integer, default=0)
    status_2xx: Mapped[int] = mapped_column(Integer, default=0)
    status_3xx: Mapped[int] = mapped_column(Integer, default=0)
    status_4xx: Mapped[int] = mapped_column(Integer, default=0)
    status_5xx: Mapped[int] = mapped_column(Integer, default=0)
    status_679: Mapped[int] = mapped_column(Integer, default=0)
    status_other: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    client_error_rate: Mapped[float] = mapped_column(Float, default=0.0)
    server_error_rate: Mapped[float] = mapped_column(Float, default=0.0)
    known_content_error_rate: Mapped[float] = mapped_column(Float, default=0.0)
    tts_p50: Mapped[float | None] = mapped_column(Float, nullable=True)
    tts_p90: Mapped[float | None] = mapped_column(Float, nullable=True)
    tts_p95: Mapped[float | None] = mapped_column(Float, nullable=True)
    tts_p99: Mapped[float | None] = mapped_column(Float, nullable=True)
    tts_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    tts_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_bytes: Mapped[int] = mapped_column(Integer, default=0)
    mean_bytes: Mapped[float] = mapped_column(Float, default=0.0)
    empty_ua_count: Mapped[int] = mapped_column(Integer, default=0)
    empty_upstream_count: Mapped[int] = mapped_column(Integer, default=0)
    empty_referrer_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class HttpAnomalyRecord(Base):
    __tablename__ = "http_anomalies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    anomaly_type: Mapped[str] = mapped_column(Enum(HttpAnomalyType))
    dimension: Mapped[str] = mapped_column(String(64))
    dimension_value: Mapped[str] = mapped_column(String(256))
    metric: Mapped[str] = mapped_column(String(64))
    current_value: Mapped[float] = mapped_column(Float)
    baseline_mean: Mapped[float] = mapped_column(Float)
    z_score: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class HttpTrendRecord(Base):
    __tablename__ = "http_trends"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    direction: Mapped[str] = mapped_column(Enum(TrendDirection))
    dimension: Mapped[str] = mapped_column(String(64))
    dimension_value: Mapped[str] = mapped_column(String(256))
    metric: Mapped[str] = mapped_column(String(64))
    slope: Mapped[float] = mapped_column(Float)
    r_squared: Mapped[float] = mapped_column(Float)
    num_points: Mapped[int] = mapped_column(Integer)
    start_value: Mapped[float] = mapped_column(Float)
    end_value: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class HttpDataCompletenessRecord(Base):
    __tablename__ = "http_data_completeness"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    time_window: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    dimension: Mapped[str] = mapped_column(String(64))
    dimension_value: Mapped[str] = mapped_column(String(256))
    total_records: Mapped[int] = mapped_column(Integer, default=0)
    field_name: Mapped[str] = mapped_column(String(64))
    empty_count: Mapped[int] = mapped_column(Integer, default=0)
    empty_rate: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class HttpAnalysisRunRecord(Base):
    __tablename__ = "http_analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    files_processed: Mapped[int] = mapped_column(Integer, default=0)
    events_parsed: Mapped[int] = mapped_column(Integer, default=0)
    anomaly_count: Mapped[int] = mapped_column(Integer, default=0)
    trend_count: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[str] = mapped_column(Text, default="")
    source_files: Mapped[str] = mapped_column(Text, default="[]")
