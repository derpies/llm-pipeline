"""ML-as-a-tool — read-only wrappers around email_analytics storage queries."""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def get_aggregations(
    run_id: str,
    dimension: str | None = None,
    dimension_value: str | None = None,
    limit: int = 50,
) -> str:
    """Retrieve aggregation data from an ML analysis run.

    Args:
        run_id: The analysis run to query.
        dimension: Filter by dimension (e.g. "listid", "recipient_domain").
        dimension_value: Filter by specific dimension value.
        limit: Max rows to return.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from llm_pipeline.email_analytics.models import AggregationRecord
    from llm_pipeline.email_analytics.storage import get_engine

    engine = get_engine()
    with Session(engine) as session:
        stmt = select(AggregationRecord).where(AggregationRecord.run_id == run_id)
        if dimension:
            stmt = stmt.where(AggregationRecord.dimension == dimension)
        if dimension_value:
            stmt = stmt.where(AggregationRecord.dimension_value == dimension_value)
        stmt = stmt.limit(limit)
        rows = session.execute(stmt).scalars().all()

    if not rows:
        return f"No aggregation data found for run_id={run_id}"

    results = []
    for r in rows:
        results.append({
            "time_window": r.time_window.isoformat(),
            "dimension": r.dimension,
            "dimension_value": r.dimension_value,
            "total": r.total,
            "delivered": r.delivered,
            "bounced": r.bounced,
            "deferred": r.deferred,
            "delivery_rate": round(r.delivery_rate, 4),
            "bounce_rate": round(r.bounce_rate, 4),
            "deferral_rate": round(r.deferral_rate, 4),
        })
    return json.dumps(results, indent=2)


@tool
def get_anomalies(
    run_id: str,
    dimension: str | None = None,
    severity: str | None = None,
    limit: int = 20,
) -> str:
    """Retrieve detected anomalies from an ML analysis run.

    Args:
        run_id: The analysis run to query.
        dimension: Filter by dimension.
        severity: Filter by severity ("high", "medium", "low").
        limit: Max results to return.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from llm_pipeline.email_analytics.models import AnomalyRecord
    from llm_pipeline.email_analytics.storage import get_engine

    engine = get_engine()
    with Session(engine) as session:
        stmt = select(AnomalyRecord).where(AnomalyRecord.run_id == run_id)
        if dimension:
            stmt = stmt.where(AnomalyRecord.dimension == dimension)
        if severity:
            stmt = stmt.where(AnomalyRecord.severity == severity)
        stmt = stmt.limit(limit)
        rows = session.execute(stmt).scalars().all()

    if not rows:
        return f"No anomalies found for run_id={run_id}"

    results = []
    for r in rows:
        results.append({
            "anomaly_type": r.anomaly_type,
            "dimension": r.dimension,
            "dimension_value": r.dimension_value,
            "metric": r.metric,
            "current_value": round(r.current_value, 4),
            "baseline_mean": round(r.baseline_mean, 4),
            "z_score": round(r.z_score, 2),
            "severity": r.severity,
        })
    return json.dumps(results, indent=2)


@tool
def get_trends(
    run_id: str,
    dimension: str | None = None,
    direction: str | None = None,
    limit: int = 20,
) -> str:
    """Retrieve detected trends from an ML analysis run.

    Args:
        run_id: The analysis run to query.
        dimension: Filter by dimension.
        direction: Filter by direction ("improving", "degrading", "stable").
        limit: Max results to return.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from llm_pipeline.email_analytics.models import TrendRecord
    from llm_pipeline.email_analytics.storage import get_engine

    engine = get_engine()
    with Session(engine) as session:
        stmt = select(TrendRecord).where(TrendRecord.run_id == run_id)
        if dimension:
            stmt = stmt.where(TrendRecord.dimension == dimension)
        if direction:
            stmt = stmt.where(TrendRecord.direction == direction)
        stmt = stmt.limit(limit)
        rows = session.execute(stmt).scalars().all()

    if not rows:
        return f"No trends found for run_id={run_id}"

    results = []
    for r in rows:
        results.append({
            "direction": r.direction,
            "dimension": r.dimension,
            "dimension_value": r.dimension_value,
            "metric": r.metric,
            "slope": round(r.slope, 6),
            "r_squared": round(r.r_squared, 3),
            "num_points": r.num_points,
            "start_value": round(r.start_value, 4),
            "end_value": round(r.end_value, 4),
        })
    return json.dumps(results, indent=2)


@tool
def get_ml_report_summary(run_id: str) -> str:
    """Get a high-level summary of an ML analysis run.

    Returns counts and top anomalies/trends — useful for planning investigations.

    Args:
        run_id: The analysis run to summarize.
    """
    from llm_pipeline.email_analytics.storage import load_report

    report = load_report(run_id)
    if not report:
        return f"No report found for run_id={run_id}"

    summary = {
        "run_id": report.run_id,
        "files_processed": report.files_processed,
        "events_parsed": report.events_parsed,
        "aggregation_count": len(report.aggregations),
        "anomaly_count": len(report.anomalies),
        "trend_count": len(report.trends),
        "error_count": len(report.errors),
    }

    if report.anomalies:
        high = [a for a in report.anomalies if a.severity == "high"]
        summary["high_severity_anomalies"] = len(high)
        summary["top_anomalies"] = [
            {
                "type": a.anomaly_type.value,
                "dimension": a.dimension,
                "value": a.dimension_value,
                "metric": a.metric,
                "z_score": round(a.z_score, 2),
                "severity": a.severity,
            }
            for a in sorted(report.anomalies, key=lambda x: abs(x.z_score), reverse=True)[:5]
        ]

    if report.trends:
        degrading = [t for t in report.trends if t.direction.value == "degrading"]
        summary["degrading_trends"] = len(degrading)

    return json.dumps(summary, indent=2)


# Tool registries per agent role
ORCHESTRATOR_ML_TOOLS = [get_ml_report_summary, get_anomalies, get_trends]
INVESTIGATOR_ML_TOOLS = [get_aggregations, get_anomalies, get_trends, get_ml_report_summary]
