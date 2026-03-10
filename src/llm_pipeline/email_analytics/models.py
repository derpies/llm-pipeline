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
from sqlalchemy.orm import Mapped, mapped_column

from llm_pipeline.models.db import Base

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

    # --- Derived fields (populated by model_validator) ---
    xmrid_account_id: str = ""
    xmrid_contact_id: str = ""
    xmrid_drip_id: str = ""
    last_active_ts: float = 0.0
    contact_added_ts: float = 0.0
    op_queue_time_parsed: float = 0.0
    marketing_flag: int = 0
    is_zero_cohort: bool = False
    listid_type: str = ""
    engagement_segment: str = ""
    compliance_status: str = ""
    pre_edge_latency: float | None = None
    delivery_attempt_time: float | None = None

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
    def populate_derived_fields(self) -> DeliveryEvent:
        """Parse composite fields and populate derived attributes."""
        from llm_pipeline.email_analytics.parsers import (
            classify_listid,
            parse_clicktrackingid,
            parse_compliance_header,
        )

        # Parse clicktrackingid
        parsed = parse_clicktrackingid(self.clicktrackingid)
        if parsed is not None:
            self.xmrid_account_id = parsed.xmrid.account_id
            self.xmrid_contact_id = parsed.xmrid.contact_id
            self.xmrid_drip_id = parsed.xmrid.drip_id
            self.last_active_ts = parsed.last_active_adjusted
            self.contact_added_ts = parsed.contact_added
            self.op_queue_time_parsed = parsed.op_queue_time
            self.marketing_flag = parsed.marketing
            self.is_zero_cohort = parsed.xmrid.is_zero_cohort

        # Classify listid
        lid_type, seg = classify_listid(self.listid)
        self.listid_type = lid_type.value
        self.engagement_segment = seg

        # Parse compliance header (raw data may have list or string)
        header_val = self.headers.get("x-op-mail-domains", "")
        if isinstance(header_val, list):
            header_val = header_val[0] if header_val else ""
        self.compliance_status = parse_compliance_header(header_val).value

        # Compute latencies
        if parsed is not None and parsed.op_queue_time > 0 and self.injected_time:
            self.pre_edge_latency = self.injected_time - parsed.op_queue_time

        ts_float = (
            self.timestamp
            if isinstance(self.timestamp, (int, float))
            else self.timestamp.timestamp()
        )
        if self.injected_time and self.injected_time > 0:
            self.delivery_attempt_time = ts_float - self.injected_time

        return self

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

    # Latency stats (None when no data available)
    pre_edge_latency_mean: float | None = None
    pre_edge_latency_p50: float | None = None
    pre_edge_latency_p95: float | None = None
    pre_edge_latency_p99: float | None = None
    pre_edge_latency_max: float | None = None
    delivery_time_mean: float | None = None
    delivery_time_p50: float | None = None
    delivery_time_p95: float | None = None
    delivery_time_p99: float | None = None
    delivery_time_max: float | None = None


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


class DataCompleteness(BaseModel):
    """Zero-value rates for a field within a dimension slice."""

    time_window: datetime
    dimension: str
    dimension_value: str
    total_records: int
    field_name: str
    zero_count: int
    zero_rate: float


class AnalysisReport(BaseModel):
    """Complete output of an email analytics run."""

    run_id: str
    started_at: datetime
    completed_at: datetime | None = None
    files_processed: int = 0
    events_parsed: int = 0
    source_files: list[str] = Field(default_factory=list)
    aggregations: list[AggregationBucket] = Field(default_factory=list)
    completeness: list[DataCompleteness] = Field(default_factory=list)
    anomalies: list[AnomalyFinding] = Field(default_factory=list)
    trends: list[TrendFinding] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# SQLAlchemy models
# ---------------------------------------------------------------------------


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
    pre_edge_latency_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    pre_edge_latency_p50: Mapped[float | None] = mapped_column(Float, nullable=True)
    pre_edge_latency_p95: Mapped[float | None] = mapped_column(Float, nullable=True)
    pre_edge_latency_p99: Mapped[float | None] = mapped_column(Float, nullable=True)
    pre_edge_latency_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_time_mean: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_time_p50: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_time_p95: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_time_p99: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_time_max: Mapped[float | None] = mapped_column(Float, nullable=True)
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


class DataCompletenessRecord(Base):
    __tablename__ = "email_data_completeness"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    time_window: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    dimension: Mapped[str] = mapped_column(String(64))
    dimension_value: Mapped[str] = mapped_column(String(256))
    total_records: Mapped[int] = mapped_column(Integer, default=0)
    field_name: Mapped[str] = mapped_column(String(64))
    zero_count: Mapped[int] = mapped_column(Integer, default=0)
    zero_rate: Mapped[float] = mapped_column(Float, default=0.0)
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
    source_files: Mapped[str] = mapped_column(Text, default="[]")



# Investigation persistence models moved to llm_pipeline.agents.storage_models
