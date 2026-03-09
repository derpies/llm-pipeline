"""Pydantic models for the structured investigation report.

Document 1 (StructuredReport): Fixed-schema, mechanically diff-able.
Document 2 (InvestigationNotes): Overflow — hypotheses, observations, process notes.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SegmentHealthRow(BaseModel):
    """One row per engagement segment (VH/H/M/L/VL/RO/NM/DS)."""

    segment: str
    total: int = 0
    delivery_rate: float = 0.0
    bounce_rate: float = 0.0
    deferral_rate: float = 0.0
    complaint_rate: float = 0.0
    delivery_time_mean: float | None = None
    delivery_time_p50: float | None = None
    delivery_time_p95: float | None = None
    delivery_time_p99: float | None = None
    delivery_time_max: float | None = None
    pre_edge_latency_mean: float | None = None
    pre_edge_latency_p50: float | None = None
    pre_edge_latency_p95: float | None = None
    pre_edge_latency_p99: float | None = None
    pre_edge_latency_max: float | None = None


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
    """Zero-value rate for a field within a dimension slice."""

    field_name: str
    dimension: str
    dimension_value: str
    zero_rate: float
    total_records: int
    flagged: bool = False


class ComplianceRow(BaseModel):
    """Per-account compliance status."""

    account_id: str
    compliance_status: str
    total: int = 0


class Observation(BaseModel):
    """A contextual note tied to a report section (future — empty in v1)."""

    section: str
    note: str


class StructuredReport(BaseModel):
    """Document 1: Fixed-schema report, mechanically diff-able."""

    run_id: str
    ml_run_id: str
    generated_at: datetime

    segment_health: list[SegmentHealthRow] = Field(default_factory=list)
    confirmed_issues: list[ConfirmedIssue] = Field(default_factory=list)
    trend_summary: TrendSummary = Field(default_factory=TrendSummary)
    data_completeness: list[CompletenessRow] = Field(default_factory=list)
    compliance: list[ComplianceRow] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)


class InvestigationNotes(BaseModel):
    """Document 2: Overflow from the investigation — not fixed-schema."""

    run_id: str
    generated_at: datetime

    hypotheses: list[str] = Field(default_factory=list)
    unexpected_observations: list[str] = Field(default_factory=list)
    process_notes: list[str] = Field(default_factory=list)


class InvestigationReport(BaseModel):
    """Combined output: structured report + investigation notes."""

    structured: StructuredReport
    notes: InvestigationNotes
