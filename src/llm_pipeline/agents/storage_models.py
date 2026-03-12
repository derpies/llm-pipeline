"""SQLAlchemy ORM models for investigation persistence.

These are generic investigation infrastructure — no domain-specific fields.
Moved from email_analytics/models.py during the domain decoupling refactor.
"""

from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from llm_pipeline.models.db import Base


class InvestigationRunStatus(enum.StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    DRY_RUN = "dry_run"


class InvestigationRunRecord(Base):
    __tablename__ = "investigation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    iteration_count: Mapped[int] = mapped_column(Integer, default=0)
    finding_count: Mapped[int] = mapped_column(Integer, default=0)
    hypothesis_count: Mapped[int] = mapped_column(Integer, default=0)
    checkpoint_digest: Mapped[str] = mapped_column(Text, default="")
    label: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(32), default="success")
    is_dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    ml_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    quality_warnings: Mapped[str] = mapped_column(Text, default="[]")
    source_files: Mapped[str] = mapped_column(Text, default="[]")
    domain_name: Mapped[str] = mapped_column(String(64), default="")
    # Human review state (Phase 4)
    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    reviewed_by: Mapped[str] = mapped_column(String(256), default="")
    review_notes: Mapped[str] = mapped_column(Text, default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class InvestigationFindingRecord(Base):
    __tablename__ = "investigation_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    topic_title: Mapped[str] = mapped_column(String(256))
    statement: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32))
    evidence: Mapped[str] = mapped_column(Text, default="[]")
    metrics_cited: Mapped[str] = mapped_column(Text, default="{}")
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    quality_warnings: Mapped[str] = mapped_column(Text, default="[]")
    domain_name: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class InvestigationHypothesisRecord(Base):
    __tablename__ = "investigation_hypotheses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    topic_title: Mapped[str] = mapped_column(String(256))
    statement: Mapped[str] = mapped_column(Text)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    domain_name: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class InvestigationReportRecord(Base):
    __tablename__ = "investigation_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    report_json: Mapped[str] = mapped_column(Text, default="")
    report_markdown: Mapped[str] = mapped_column(Text, default="")
    domain_name: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
