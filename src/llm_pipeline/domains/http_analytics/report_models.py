"""Pydantic models for the HTTP structured investigation report.

Document 1 (HttpStructuredReport): Fixed-schema, mechanically diff-able.
Document 2 (HttpInvestigationNotes): Overflow — hypotheses, observations, process notes.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class HostHealthRow(BaseModel):
    """One row per host category — success rates + latency."""

    host_category: str
    total: int = 0
    success_rate: float = 0.0
    client_error_rate: float = 0.0
    server_error_rate: float = 0.0
    known_content_error_rate: float = 0.0
    tts_mean: float | None = None
    tts_p50: float | None = None
    tts_p95: float | None = None
    tts_p99: float | None = None
    tts_max: float | None = None


class CategoryBreakdownRow(BaseModel):
    """Per-request-category traffic distribution."""

    category: str
    total: int = 0
    percentage: float = 0.0
    success_rate: float = 0.0
    client_error_rate: float = 0.0


class Status679Summary(BaseModel):
    """Summary of 679 (known-content-missing) errors."""

    total_679: int = 0
    affected_hosts: list[str] = Field(default_factory=list)
    rate_overall: float = 0.0


class BotTrafficSummary(BaseModel):
    """Summary of bot and scanner traffic."""

    empty_ua_rate: float = 0.0
    scanner_count: int = 0
    bot_crawler_count: int = 0
    php_probe_count: int = 0
    real_browser_count: int = 0


class ConfirmedIssue(BaseModel):
    """A confirmed finding from the investigation."""

    dimension: str
    dimension_value: str
    metric: str
    magnitude: str
    evidence_summary: str


class TrendRow(BaseModel):
    """A single trend entry."""

    dimension: str
    dimension_value: str
    metric: str
    direction: str
    slope: float
    start_value: float
    end_value: float


class TrendSummary(BaseModel):
    """Aggregate trend counts plus top movers."""

    degrading_count: int = 0
    improving_count: int = 0
    stable_count: int = 0
    top_movers: list[TrendRow] = Field(default_factory=list)


class CompletenessRow(BaseModel):
    """Empty-value rate for a field within a dimension slice."""

    field_name: str
    dimension: str
    dimension_value: str
    empty_rate: float
    total_records: int
    flagged: bool = False


class Observation(BaseModel):
    """A contextual note tied to a report section."""

    section: str
    note: str


class HttpStructuredReport(BaseModel):
    """Document 1: Fixed-schema HTTP report, mechanically diff-able."""

    run_id: str
    ml_run_id: str
    generated_at: datetime

    host_health: list[HostHealthRow] = Field(default_factory=list)
    category_breakdown: list[CategoryBreakdownRow] = Field(default_factory=list)
    status_679: Status679Summary = Field(default_factory=Status679Summary)
    bot_traffic: BotTrafficSummary = Field(default_factory=BotTrafficSummary)
    confirmed_issues: list[ConfirmedIssue] = Field(default_factory=list)
    trend_summary: TrendSummary = Field(default_factory=TrendSummary)
    data_completeness: list[CompletenessRow] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)


class HttpInvestigationNotes(BaseModel):
    """Document 2: Overflow from the investigation — not fixed-schema."""

    run_id: str
    generated_at: datetime

    hypotheses: list[str] = Field(default_factory=list)
    unexpected_observations: list[str] = Field(default_factory=list)
    process_notes: list[str] = Field(default_factory=list)


class HttpInvestigationReport(BaseModel):
    """Combined output: structured report + investigation notes."""

    structured: HttpStructuredReport
    notes: HttpInvestigationNotes
