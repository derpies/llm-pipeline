"""Investigation review endpoints — human approval/rejection of runs."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from llm_pipeline.agents.storage_models import InvestigationRunRecord
from llm_pipeline.api.dependencies import get_db

router = APIRouter(tags=["reviews"])

VALID_REVIEW_STATUSES = {"approved", "rejected", "flagged"}


class ReviewRequest(BaseModel):
    status: str
    reviewer: str
    notes: str = ""


class ReviewResponse(BaseModel):
    run_id: str
    review_status: str
    reviewed_by: str
    review_notes: str
    reviewed_at: datetime | None


@router.post("/investigations/{run_id}/review")
def submit_review(
    run_id: str,
    body: ReviewRequest,
    db: Session = Depends(get_db),
) -> ReviewResponse:
    """Submit a human review for an investigation run."""
    if body.status not in VALID_REVIEW_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid review status '{body.status}'. Must be one of: {', '.join(sorted(VALID_REVIEW_STATUSES))}",
        )

    stmt = (
        select(InvestigationRunRecord)
        .where(InvestigationRunRecord.run_id == run_id)
        .order_by(InvestigationRunRecord.id.desc())
        .limit(1)
    )
    run = db.execute(stmt).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail=f"Investigation {run_id} not found")

    now = datetime.now(UTC)
    run.review_status = body.status
    run.reviewed_by = body.reviewer
    run.review_notes = body.notes
    run.reviewed_at = now
    db.commit()

    return ReviewResponse(
        run_id=run.run_id,
        review_status=run.review_status,
        reviewed_by=run.reviewed_by,
        review_notes=run.review_notes,
        reviewed_at=run.reviewed_at,
    )


@router.get("/investigations/{run_id}/review")
def get_review(
    run_id: str,
    db: Session = Depends(get_db),
) -> ReviewResponse:
    """Get the current review state of an investigation run."""
    stmt = (
        select(InvestigationRunRecord)
        .where(InvestigationRunRecord.run_id == run_id)
        .order_by(InvestigationRunRecord.id.desc())
        .limit(1)
    )
    run = db.execute(stmt).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail=f"Investigation {run_id} not found")

    return ReviewResponse(
        run_id=run.run_id,
        review_status=run.review_status,
        reviewed_by=run.reviewed_by,
        review_notes=run.review_notes,
        reviewed_at=run.reviewed_at,
    )
