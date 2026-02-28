"""Data models for email delivery analytics.

Pydantic models for event parsing and output schemas.
SQLAlchemy models for Postgres persistence.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, computed_field, model_validator
from sqlalchemy import DateTime, Enum, Float, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DeliveryStatus(enum.StrEnum):
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    DEFERRED = "deferred"
    DROPPED = "dropped"
    COMPLAINT = "complaint"
    UNKNOWN = "unknown"


class SmtpCategory(enum.StrEnum):
    THROTTLING = "throttling"
    BLACKLIST = "blacklist"
    REPUTATION = "reputation"
    AUTH_FAILURE = "auth_failure"
    CONTENT_REJECTION = "content_rejection"
    RECIPIENT_UNKNOWN = "recipient_unknown"
    POLICY = "policy"
    NETWORK = "network"
    SUCCESS = "success"
    OTHER = "other"


class AnomalyType(enum.StrEnum):
    RATE_DROP = "rate_drop"
    RATE_SPIKE = "rate_spike"
    BOUNCE_SPIKE = "bounce_spike"
    DEFERRAL_SPIKE = "deferral_spike"
    COMPLAINT_SPIKE = "complaint_spike"


class TrendDirection(enum.StrEnum):
    IMPROVING = "improving"
    DEGRADING = "degrading"
    STABLE = "stable"


# ---------------------------------------------------------------------------
# Status normalization
# ---------------------------------------------------------------------------

_STATUS_MAP: dict[str, DeliveryStatus] = {
    "delivered": DeliveryStatus.DELIVERED,
    "delivery": DeliveryStatus.DELIVERED,
    "success": DeliveryStatus.DELIVERED,
    "bounced": DeliveryStatus.BOUNCED,
    "bounce": DeliveryStatus.BOUNCED,
    "hard_bounce": DeliveryStatus.BOUNCED,
    "failure": DeliveryStatus.BOUNCED,
    "failure_toolong": DeliveryStatus.BOUNCED,
    "soft_bounce": DeliveryStatus.DEFERRED,
    "deferred": DeliveryStatus.DEFERRED,
    "deferral": DeliveryStatus.DEFERRED,
    "connmaxout": DeliveryStatus.DEFERRED,
    "dropped": DeliveryStatus.DROPPED,
    "drop": DeliveryStatus.DROPPED,
    "complaint": DeliveryStatus.COMPLAINT,
    "spam": DeliveryStatus.COMPLAINT,
    "spamreport": DeliveryStatus.COMPLAINT,
}


def normalize_status(raw: str) -> DeliveryStatus:
    """Map raw status strings to canonical DeliveryStatus values."""
    return _STATUS_MAP.get(raw.lower().strip(), DeliveryStatus.UNKNOWN)


# ---------------------------------------------------------------------------
# Pydantic event model
# ---------------------------------------------------------------------------


class DeliveryEvent(BaseModel, extra="ignore"):
    """A single email delivery event parsed from raw data."""

    model_config = {"arbitrary_types_allowed": True}

    timestamp: float | datetime
    status: str
    message: str = ""
    sender: str = ""
    recipient: str = ""
    subject: str = ""
    outmtaid: str = ""
    outmtaid_ip: str = ""
    sendid: str = ""
    accountid: str = ""
    jobid: str = ""
    rcptmtaid: str = ""

    # Additional fields from real data
    channel: str = ""
    is_retry: int = 0
    msguid: str = ""
    mtaid: str = ""
    listid: str = ""
    injected_time: float | None = None
    outmtaid_hostname: str = ""
    sendsliceid: str = ""
    throttleid: str = ""
    clicktrackingid: str = ""
    mx_hostname: str = ""
    mx_ip: str = ""
    from_address: str = ""
    headers: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def coerce_nulls(cls, data: Any) -> Any:
        """Coerce None values to empty strings for string fields."""
        if isinstance(data, dict):
            for key, val in data.items():
                if val is None:
                    data[key] = ""
        return data

    @computed_field  # type: ignore[prop-decorator]
    @property
    def normalized_status(self) -> DeliveryStatus:
        return normalize_status(self.status)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def recipient_domain(self) -> str:
        if "@" in self.recipient:
            return self.recipient.rsplit("@", 1)[1].lower()
        return ""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def event_time(self) -> datetime:
        if isinstance(self.timestamp, (int, float)):
            return datetime.fromtimestamp(self.timestamp, tz=UTC)
        return self.timestamp


# ---------------------------------------------------------------------------
# Output schemas
# ---------------------------------------------------------------------------


class SmtpClassification(BaseModel):
    """Result of classifying an SMTP response message."""

    category: SmtpCategory
    confidence: float = Field(ge=0.0, le=1.0)
    smtp_code: str = ""
    provider_hint: str = ""
    matched_pattern: str = ""


class AggregationBucket(BaseModel):
    """A single aggregation bucket — counts and rates for a dimension slice."""

    time_window: datetime
    dimension: str
    dimension_value: str
    total: int = 0
    delivered: int = 0
    bounced: int = 0
    deferred: int = 0
    complained: int = 0
    delivery_rate: float = 0.0
    bounce_rate: float = 0.0
    deferral_rate: float = 0.0
    complaint_rate: float = 0.0


class AnomalyFinding(BaseModel):
    """A detected anomaly in a metric."""

    anomaly_type: AnomalyType
    dimension: str
    dimension_value: str
    metric: str
    current_value: float
    baseline_mean: float
    z_score: float
    severity: str = "medium"


class TrendFinding(BaseModel):
    """A detected trend in a metric over time."""

    direction: TrendDirection
    dimension: str
    dimension_value: str
    metric: str
    slope: float
    r_squared: float
    num_points: int
    start_value: float
    end_value: float


class AnalysisReport(BaseModel):
    """Complete output of an email analytics run."""

    run_id: str
    started_at: datetime
    completed_at: datetime | None = None
    files_processed: int = 0
    events_parsed: int = 0
    aggregations: list[AggregationBucket] = Field(default_factory=list)
    anomalies: list[AnomalyFinding] = Field(default_factory=list)
    trends: list[TrendFinding] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# SQLAlchemy models
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


class AggregationRecord(Base):
    __tablename__ = "email_aggregations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    time_window: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    dimension: Mapped[str] = mapped_column(String(64), index=True)
    dimension_value: Mapped[str] = mapped_column(String(256))
    total: Mapped[int] = mapped_column(Integer, default=0)
    delivered: Mapped[int] = mapped_column(Integer, default=0)
    bounced: Mapped[int] = mapped_column(Integer, default=0)
    deferred: Mapped[int] = mapped_column(Integer, default=0)
    complained: Mapped[int] = mapped_column(Integer, default=0)
    delivery_rate: Mapped[float] = mapped_column(Float, default=0.0)
    bounce_rate: Mapped[float] = mapped_column(Float, default=0.0)
    deferral_rate: Mapped[float] = mapped_column(Float, default=0.0)
    complaint_rate: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AnomalyRecord(Base):
    __tablename__ = "email_anomalies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    anomaly_type: Mapped[str] = mapped_column(Enum(AnomalyType))
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


class TrendRecord(Base):
    __tablename__ = "email_trends"

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


class AnalysisRunRecord(Base):
    __tablename__ = "email_analysis_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    files_processed: Mapped[int] = mapped_column(Integer, default=0)
    events_parsed: Mapped[int] = mapped_column(Integer, default=0)
    anomaly_count: Mapped[int] = mapped_column(Integer, default=0)
    trend_count: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[str] = mapped_column(Text, default="")
