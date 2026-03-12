"""Pydantic + SQLAlchemy models for the four-tier knowledge hierarchy.

Knowledge entries are created *from* investigation output (Finding/Hypothesis in
agents/models.py). Those raw models stay unchanged — knowledge entries wrap them
with tier, scope, confidence, temporal tracking, and audit trail.

Tiers:  hypothesis < finding < truth < grounded
Scopes: community (aggregate) | account (per-account isolation)
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from llm_pipeline.models.db import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class KnowledgeTier(enum.StrEnum):
    HYPOTHESIS = "hypothesis"
    FINDING = "finding"
    TRUTH = "truth"
    GROUNDED = "grounded"


class KnowledgeScope(enum.StrEnum):
    COMMUNITY = "community"
    ACCOUNT = "account"


class DeprecationStatus(enum.StrEnum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


# ---------------------------------------------------------------------------
# Confidence computation
# ---------------------------------------------------------------------------


def compute_confidence(
    tier: KnowledgeTier,
    finding_status: str | None = None,
    observation_count: int = 1,
    temporal_span_days: int = 0,
) -> float:
    """Compute confidence score based on tier and evidence strength."""
    if tier == KnowledgeTier.GROUNDED:
        return 1.0

    if tier == KnowledgeTier.TRUTH:
        # 0.7 base + bonus for temporal span (cap 0.9)
        bonus = min(temporal_span_days / 365.0, 1.0) * 0.2
        return min(0.7 + bonus, 0.9)

    if tier == KnowledgeTier.FINDING:
        if finding_status == "disproven":
            return 0.0
        # 0.3 base + bonus for observation count (cap 0.6)
        bonus = min(observation_count / 20.0, 1.0) * 0.3
        return min(0.3 + bonus, 0.6)

    # Hypothesis
    return 0.1


# ---------------------------------------------------------------------------
# Pydantic knowledge entry models
# ---------------------------------------------------------------------------


class KnowledgeEntry(BaseModel):
    """Base model for all knowledge tier entries."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tier: KnowledgeTier
    scope: KnowledgeScope = KnowledgeScope.COMMUNITY
    account_id: str = ""

    # Domain isolation
    domain_name: str = ""

    # Embedded text
    statement: str
    topic: str = ""
    dimension: str = ""
    dimension_value: str = ""

    # Temporal confidence
    observation_count: int = 1
    first_observed: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_observed: datetime = Field(default_factory=lambda: datetime.now(UTC))
    temporal_span_days: int = 0

    # Provenance
    source_run_ids: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    metrics_cited: dict[str, float] = Field(default_factory=dict)

    # Lifecycle
    status: DeprecationStatus = DeprecationStatus.ACTIVE
    confidence: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def recompute_confidence(self) -> None:
        """Recalculate confidence from current state."""
        finding_status = getattr(self, "finding_status", None)
        self.confidence = compute_confidence(
            self.tier,
            finding_status=finding_status,
            observation_count=self.observation_count,
            temporal_span_days=self.temporal_span_days,
        )

    @property
    def embedding_text(self) -> str:
        """Text to embed for vector similarity search."""
        if self.topic:
            return f"{self.topic}: {self.statement}"
        return self.statement

    @property
    def tenant_name(self) -> str:
        """Weaviate tenant name — account_id for account scope, 'community' for community."""
        if self.scope == KnowledgeScope.ACCOUNT and self.account_id:
            return self.account_id
        return "community"


class HypothesisEntry(KnowledgeEntry):
    """An untested hypothesis in the knowledge store."""

    tier: KnowledgeTier = KnowledgeTier.HYPOTHESIS
    reasoning: str = ""

    @classmethod
    def from_investigation_hypothesis(
        cls,
        h: Any,
        scope: KnowledgeScope = KnowledgeScope.COMMUNITY,
        account_id: str = "",
        domain_name: str = "",
    ) -> HypothesisEntry:
        """Create from an agents.models.Hypothesis."""
        entry = cls(
            scope=scope,
            account_id=account_id,
            domain_name=domain_name,
            statement=h.statement,
            topic=h.topic_title,
            reasoning=h.reasoning,
            source_run_ids=[h.run_id] if h.run_id else [],
            first_observed=h.created_at,
            last_observed=h.created_at,
        )
        entry.recompute_confidence()
        return entry


class FindingEntry(KnowledgeEntry):
    """An ML-tested finding in the knowledge store."""

    tier: KnowledgeTier = KnowledgeTier.FINDING
    finding_status: str = ""  # confirmed/disproven/inconclusive
    promoted_from: str = ""  # hypothesis entry_id if promoted

    @classmethod
    def from_investigation_finding(
        cls,
        f: Any,
        scope: KnowledgeScope = KnowledgeScope.COMMUNITY,
        account_id: str = "",
        domain_name: str = "",
    ) -> FindingEntry:
        """Create from an agents.models.Finding."""
        entry = cls(
            scope=scope,
            account_id=account_id,
            domain_name=domain_name,
            statement=f.statement,
            topic=f.topic_title,
            finding_status=f.status.value if hasattr(f.status, "value") else str(f.status),
            evidence=list(f.evidence),
            metrics_cited=dict(f.metrics_cited),
            source_run_ids=[f.run_id] if f.run_id else [],
            first_observed=f.created_at,
            last_observed=f.created_at,
        )
        entry.recompute_confidence()
        return entry


class TruthEntry(KnowledgeEntry):
    """A confirmed truth — ML + LLM + human validated."""

    tier: KnowledgeTier = KnowledgeTier.TRUTH
    promoted_from: str = ""  # finding entry_id
    human_reviewer: str = ""
    review_notes: str = ""


class GroundedEntry(KnowledgeEntry):
    """Authoritative domain knowledge from the grounding corpus. Read-only."""

    tier: KnowledgeTier = KnowledgeTier.GROUNDED
    source_document: str = ""
    source_section: str = ""


# ---------------------------------------------------------------------------
# SQLAlchemy audit trail
# ---------------------------------------------------------------------------


class KnowledgeAnnotationRecord(Base):
    """Human annotations attached to knowledge entries."""

    __tablename__ = "knowledge_annotations"
    __table_args__ = {"schema": "knowledge"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id: Mapped[str] = mapped_column(String(64), index=True)
    actor: Mapped[str] = mapped_column(String(256))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class KnowledgeAuditRecord(Base):
    """Audit trail for knowledge tier promotions, demotions, and lifecycle events."""

    __tablename__ = "knowledge_audit"
    __table_args__ = {"schema": "knowledge"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(32))  # created/promoted/deprecated/superseded/updated/merged
    from_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    actor: Mapped[str] = mapped_column(String(256), default="system")
    reason: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
