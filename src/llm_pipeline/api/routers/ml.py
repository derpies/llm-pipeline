"""ML analysis run detail endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from llm_pipeline.api.dependencies import get_db
from llm_pipeline.email_analytics.models import (
    AggregationRecord,
    AnalysisRunRecord,
    AnomalyRecord,
    DataCompletenessRecord,
    TrendRecord,
)

router = APIRouter(tags=["ml"])


@router.get("/ml/{run_id}")
def get_ml_run(run_id: str, db: Session = Depends(get_db)):
    """Get ML analysis run summary with related counts."""
    run = db.execute(
        select(AnalysisRunRecord).where(AnalysisRunRecord.run_id == run_id)
    ).scalar_one_or_none()

    if run is None:
        raise HTTPException(status_code=404, detail=f"ML run {run_id} not found")

    agg_count = db.execute(
        select(func.count()).where(AggregationRecord.run_id == run_id)
    ).scalar_one()
    anomaly_count = db.execute(
        select(func.count()).where(AnomalyRecord.run_id == run_id)
    ).scalar_one()
    trend_count = db.execute(
        select(func.count()).where(TrendRecord.run_id == run_id)
    ).scalar_one()
    completeness_count = db.execute(
        select(func.count()).where(DataCompletenessRecord.run_id == run_id)
    ).scalar_one()

    return {
        "run_id": run.run_id,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "files_processed": run.files_processed,
        "events_parsed": run.events_parsed,
        "counts": {
            "aggregations": agg_count,
            "anomalies": anomaly_count,
            "trends": trend_count,
            "completeness": completeness_count,
        },
    }


@router.get("/ml/{run_id}/aggregations")
def get_aggregations(
    run_id: str,
    dimension: str | None = Query(None),
    dimension_value: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Get aggregation buckets for an ML run."""
    stmt = select(AggregationRecord).where(AggregationRecord.run_id == run_id)
    if dimension:
        stmt = stmt.where(AggregationRecord.dimension == dimension)
    if dimension_value:
        stmt = stmt.where(AggregationRecord.dimension_value == dimension_value)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.offset(offset).limit(limit)).scalars().all()

    return {
        "total": total,
        "aggregations": [
            {
                "time_window": r.time_window,
                "dimension": r.dimension,
                "dimension_value": r.dimension_value,
                "total": r.total,
                "delivered": r.delivered,
                "bounced": r.bounced,
                "deferred": r.deferred,
                "complained": r.complained,
                "delivery_rate": r.delivery_rate,
                "bounce_rate": r.bounce_rate,
                "deferral_rate": r.deferral_rate,
                "complaint_rate": r.complaint_rate,
                "pre_edge_latency_mean": r.pre_edge_latency_mean,
                "pre_edge_latency_p50": r.pre_edge_latency_p50,
                "pre_edge_latency_p95": r.pre_edge_latency_p95,
                "delivery_time_mean": r.delivery_time_mean,
                "delivery_time_p50": r.delivery_time_p50,
                "delivery_time_p95": r.delivery_time_p95,
            }
            for r in rows
        ],
    }


@router.get("/ml/{run_id}/anomalies")
def get_anomalies(run_id: str, db: Session = Depends(get_db)):
    """Get anomalies for an ML run."""
    rows = (
        db.execute(select(AnomalyRecord).where(AnomalyRecord.run_id == run_id)).scalars().all()
    )

    return [
        {
            "anomaly_type": r.anomaly_type,
            "dimension": r.dimension,
            "dimension_value": r.dimension_value,
            "metric": r.metric,
            "current_value": r.current_value,
            "baseline_mean": r.baseline_mean,
            "z_score": r.z_score,
            "severity": r.severity,
        }
        for r in rows
    ]


@router.get("/ml/{run_id}/trends")
def get_trends(run_id: str, db: Session = Depends(get_db)):
    """Get trends for an ML run."""
    rows = db.execute(select(TrendRecord).where(TrendRecord.run_id == run_id)).scalars().all()

    return [
        {
            "direction": r.direction,
            "dimension": r.dimension,
            "dimension_value": r.dimension_value,
            "metric": r.metric,
            "slope": r.slope,
            "r_squared": r.r_squared,
            "num_points": r.num_points,
            "start_value": r.start_value,
            "end_value": r.end_value,
        }
        for r in rows
    ]


@router.get("/ml/{run_id}/completeness")
def get_completeness(
    run_id: str,
    dimension: str | None = Query(None),
    field_name: str | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Get data completeness metrics for an ML run."""
    stmt = select(DataCompletenessRecord).where(DataCompletenessRecord.run_id == run_id)
    if dimension:
        stmt = stmt.where(DataCompletenessRecord.dimension == dimension)
    if field_name:
        stmt = stmt.where(DataCompletenessRecord.field_name == field_name)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(stmt.offset(offset).limit(limit)).scalars().all()

    return {
        "total": total,
        "completeness": [
            {
                "time_window": r.time_window,
                "dimension": r.dimension,
                "dimension_value": r.dimension_value,
                "total_records": r.total_records,
                "field_name": r.field_name,
                "zero_count": r.zero_count,
                "zero_rate": r.zero_rate,
            }
            for r in rows
        ],
    }
