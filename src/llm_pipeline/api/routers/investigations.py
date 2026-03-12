"""Investigation detail and report endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from llm_pipeline.api.dependencies import get_db

router = APIRouter(tags=["investigations"])


@router.get("/investigations/{run_id}")
def get_investigation(run_id: str, db: Session = Depends(get_db)):
    """Load a complete investigation by run_id."""
    from llm_pipeline.agents.storage_models import (
        InvestigationFindingRecord,
        InvestigationHypothesisRecord,
        InvestigationReportRecord,
        InvestigationRunRecord,
    )

    # Get the run record
    stmt = (
        select(InvestigationRunRecord)
        .where(InvestigationRunRecord.run_id == run_id)
        .order_by(InvestigationRunRecord.id.desc())
        .limit(1)
    )
    run = db.execute(stmt).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail=f"Investigation {run_id} not found")

    # Findings
    finding_rows = (
        db.execute(
            select(InvestigationFindingRecord).where(
                InvestigationFindingRecord.run_id == run_id,
                InvestigationFindingRecord.created_at == run.created_at,
            )
        )
        .scalars()
        .all()
    )

    findings = [
        {
            "topic_title": f.topic_title,
            "statement": f.statement,
            "status": f.status,
            "evidence": _safe_json(f.evidence, []),
            "metrics_cited": _safe_json(f.metrics_cited, {}),
            "is_fallback": f.is_fallback,
            "quality_warnings": _safe_json(f.quality_warnings, []),
        }
        for f in finding_rows
    ]

    # Hypotheses
    hypothesis_rows = (
        db.execute(
            select(InvestigationHypothesisRecord).where(
                InvestigationHypothesisRecord.run_id == run_id,
                InvestigationHypothesisRecord.created_at == run.created_at,
            )
        )
        .scalars()
        .all()
    )

    hypotheses = [
        {
            "topic_title": h.topic_title,
            "statement": h.statement,
            "reasoning": h.reasoning,
        }
        for h in hypothesis_rows
    ]

    # Synthesis narrative (from report if available)
    synthesis_narrative = None
    report_row = db.execute(
        select(InvestigationReportRecord)
        .where(InvestigationReportRecord.run_id == run_id)
        .order_by(InvestigationReportRecord.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if report_row and report_row.report_json:
        try:
            report_data = json.loads(report_row.report_json)
            synthesis_narrative = report_data.get("synthesis_narrative")
        except (json.JSONDecodeError, TypeError):
            pass

    # Duration
    duration_seconds = None
    if run.started_at and run.completed_at:
        duration_seconds = (run.completed_at - run.started_at).total_seconds()

    return {
        "run_id": run.run_id,
        "domain": "email_delivery",
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "duration_seconds": duration_seconds,
        "status": getattr(run, "status", "success"),
        "is_dry_run": getattr(run, "is_dry_run", False),
        "label": getattr(run, "label", ""),
        "ml_run_id": getattr(run, "ml_run_id", None),
        "iteration_count": run.iteration_count,
        "finding_count": run.finding_count,
        "hypothesis_count": run.hypothesis_count,
        "checkpoint_digest": run.checkpoint_digest,
        "quality_warnings": _safe_json(getattr(run, "quality_warnings", "[]"), []),
        "source_files": _safe_json(getattr(run, "source_files", "[]"), []),
        "findings": findings,
        "hypotheses": hypotheses,
        "synthesis_narrative": synthesis_narrative,
    }


@router.get("/investigations/{run_id}/report")
def get_investigation_report(
    run_id: str,
    format: str = Query("json", pattern="^(json|markdown)$"),
    db: Session = Depends(get_db),
):
    """Get the rendered investigation report."""
    from llm_pipeline.agents.storage_models import InvestigationReportRecord

    row = db.execute(
        select(InvestigationReportRecord)
        .where(InvestigationReportRecord.run_id == run_id)
        .order_by(InvestigationReportRecord.id.desc())
        .limit(1)
    ).scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Report for {run_id} not found")

    if format == "markdown":
        return {"run_id": run_id, "markdown": row.report_markdown}

    return {"run_id": run_id, "report": _safe_json(row.report_json, {})}


def _safe_json(value, default):
    """Parse a JSON string, returning default for invalid values."""
    if not isinstance(value, str):
        return value if value is not None else default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default
