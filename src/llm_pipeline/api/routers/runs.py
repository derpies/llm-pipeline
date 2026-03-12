"""Pipeline run listing endpoint."""

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from llm_pipeline.agents.storage_models import InvestigationRunRecord
from llm_pipeline.api.dependencies import get_db
from llm_pipeline.email_analytics.models import AnalysisRunRecord

router = APIRouter(tags=["runs"])


def _run_to_dict(row, command: str) -> dict:
    """Map an ORM run record to a unified API dict."""
    source_files = []
    raw = getattr(row, "source_files", "[]")
    if isinstance(raw, str):
        try:
            source_files = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass

    base = {
        "run_id": row.run_id,
        "domain": "email_delivery",
        "command": command,
        "created_at": getattr(row, "created_at", None) or getattr(row, "started_at", None),
        "source_files": source_files,
    }

    if command == "analyze_email":
        base.update(
            {
                "started_at": row.started_at,
                "completed_at": row.completed_at,
                "files_processed": row.files_processed,
                "events_parsed": row.events_parsed,
                "anomaly_count": row.anomaly_count,
                "trend_count": row.trend_count,
            }
        )
    else:
        base.update(
            {
                "started_at": row.started_at,
                "completed_at": row.completed_at,
                "status": getattr(row, "status", "success"),
                "is_dry_run": getattr(row, "is_dry_run", False),
                "label": getattr(row, "label", ""),
                "ml_run_id": getattr(row, "ml_run_id", None),
                "finding_count": row.finding_count,
                "hypothesis_count": row.hypothesis_count,
                "iteration_count": row.iteration_count,
            }
        )

    return base


@router.get("/runs")
def list_runs(
    db: Session = Depends(get_db),
    domain: str | None = Query(None),
    command: str | None = Query(None),
    status: str | None = Query(None),
    source_file: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List all pipeline runs (ML + investigation), unified and sorted."""
    runs = []

    # ML runs
    if command is None or command == "analyze_email":
        # status filter: ML runs don't have a status column, skip if status is set
        if status is None or status in (None, ""):
            ml_stmt = select(AnalysisRunRecord)
            if source_file:
                ml_stmt = ml_stmt.where(AnalysisRunRecord.source_files.contains(source_file))
            if search:
                ml_stmt = ml_stmt.where(AnalysisRunRecord.run_id.contains(search))

            ml_rows = db.execute(ml_stmt).scalars().all()
            for row in ml_rows:
                runs.append(_run_to_dict(row, "analyze_email"))

    # Investigation runs
    if command is None or command == "investigate":
        inv_stmt = select(InvestigationRunRecord)
        if status == "dry_run":
            inv_stmt = inv_stmt.where(InvestigationRunRecord.is_dry_run.is_(True))
        elif status:
            inv_stmt = inv_stmt.where(InvestigationRunRecord.status == status)
        if source_file:
            inv_stmt = inv_stmt.where(InvestigationRunRecord.source_files.contains(source_file))
        if search:
            inv_stmt = inv_stmt.where(
                or_(
                    InvestigationRunRecord.run_id.contains(search),
                    InvestigationRunRecord.label.contains(search),
                )
            )

        inv_rows = db.execute(inv_stmt).scalars().all()
        for row in inv_rows:
            runs.append(_run_to_dict(row, "investigate"))

    # Sort by created_at desc (handle None)
    def _sort_key(r):
        v = r.get("created_at")
        if v is None:
            return ""
        return v.isoformat() if hasattr(v, "isoformat") else str(v)

    runs.sort(key=_sort_key, reverse=True)

    total = len(runs)
    paginated = runs[offset : offset + limit]

    return {"total": total, "runs": paginated}
