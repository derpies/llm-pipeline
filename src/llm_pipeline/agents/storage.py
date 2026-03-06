"""Postgres persistence for investigation cycle results."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from llm_pipeline.agents.models import Finding, FindingStatus, Hypothesis
from llm_pipeline.email_analytics.models import (
    InvestigationFindingRecord,
    InvestigationHypothesisRecord,
    InvestigationRunRecord,
)
from llm_pipeline.email_analytics.storage import get_engine

logger = logging.getLogger(__name__)


def store_investigation_results(
    run_id: str,
    findings: list[Finding],
    hypotheses: list[Hypothesis],
    checkpoint_digest: str,
    iteration_count: int,
    started_at: datetime,
    completed_at: datetime | None = None,
) -> None:
    """Persist investigation results to Postgres (atomic commit)."""
    engine = get_engine()

    with Session(engine) as session:
        run = InvestigationRunRecord(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at or datetime.now(UTC),
            iteration_count=iteration_count,
            finding_count=len(findings),
            hypothesis_count=len(hypotheses),
            checkpoint_digest=checkpoint_digest,
        )
        session.add(run)

        for f in findings:
            session.add(
                InvestigationFindingRecord(
                    run_id=run_id,
                    topic_title=f.topic_title,
                    statement=f.statement,
                    status=f.status.value,
                    evidence=json.dumps(f.evidence),
                    metrics_cited=json.dumps(f.metrics_cited),
                )
            )

        for h in hypotheses:
            session.add(
                InvestigationHypothesisRecord(
                    run_id=run_id,
                    topic_title=h.topic_title,
                    statement=h.statement,
                    reasoning=h.reasoning,
                )
            )

        session.commit()
        logger.info(
            "Stored investigation %s: %d findings, %d hypotheses",
            run_id,
            len(findings),
            len(hypotheses),
        )


def load_investigation(run_id: str) -> dict | None:
    """Load a complete investigation result from Postgres by run_id.

    Returns dict with run metadata, Finding/Hypothesis objects, and digest,
    or None if no investigation found for this run_id.
    """
    engine = get_engine()

    with Session(engine) as session:
        run = session.execute(
            select(InvestigationRunRecord).where(
                InvestigationRunRecord.run_id == run_id
            )
        ).scalar_one_or_none()
        if run is None:
            return None

        finding_rows = (
            session.execute(
                select(InvestigationFindingRecord).where(
                    InvestigationFindingRecord.run_id == run_id
                )
            )
            .scalars()
            .all()
        )

        hypothesis_rows = (
            session.execute(
                select(InvestigationHypothesisRecord).where(
                    InvestigationHypothesisRecord.run_id == run_id
                )
            )
            .scalars()
            .all()
        )

        findings = [
            Finding(
                topic_title=r.topic_title,
                statement=r.statement,
                status=FindingStatus(r.status),
                evidence=json.loads(r.evidence),
                metrics_cited=json.loads(r.metrics_cited),
                created_at=r.created_at,
                run_id=run_id,
            )
            for r in finding_rows
        ]

        hypotheses = [
            Hypothesis(
                topic_title=r.topic_title,
                statement=r.statement,
                reasoning=r.reasoning,
                created_at=r.created_at,
                run_id=run_id,
            )
            for r in hypothesis_rows
        ]

        return {
            "run_id": run.run_id,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "iteration_count": run.iteration_count,
            "findings": findings,
            "hypotheses": hypotheses,
            "checkpoint_digest": run.checkpoint_digest,
        }
