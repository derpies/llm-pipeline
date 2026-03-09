"""ML-as-a-tool — read-only wrappers around email_analytics storage queries."""

from __future__ import annotations

import json
import logging
import time

from langchain_core.tools import tool

from llm_pipeline.tools.result import ToolStatus, tool_result

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
    logger.debug("tool get_aggregations called run_id=%s dimension=%s", run_id, dimension)
    t0 = time.monotonic()
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
        logger.debug(
            "tool get_aggregations returned run_id=%s results=0 elapsed_s=%.2f",
            run_id,
            time.monotonic() - t0,
        )
        return tool_result(ToolStatus.EMPTY, f"No aggregation data found for run_id={run_id}")

    def _round_or_none(val, digits=4):
        return round(val, digits) if val is not None else None

    results = []
    for r in rows:
        results.append(
            {
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
                "pre_edge_latency_mean": _round_or_none(getattr(r, "pre_edge_latency_mean", None)),
                "pre_edge_latency_p50": _round_or_none(getattr(r, "pre_edge_latency_p50", None)),
                "pre_edge_latency_p95": _round_or_none(getattr(r, "pre_edge_latency_p95", None)),
                "pre_edge_latency_p99": _round_or_none(getattr(r, "pre_edge_latency_p99", None)),
                "pre_edge_latency_max": _round_or_none(getattr(r, "pre_edge_latency_max", None)),
                "delivery_time_mean": _round_or_none(getattr(r, "delivery_time_mean", None)),
                "delivery_time_p50": _round_or_none(getattr(r, "delivery_time_p50", None)),
                "delivery_time_p95": _round_or_none(getattr(r, "delivery_time_p95", None)),
                "delivery_time_p99": _round_or_none(getattr(r, "delivery_time_p99", None)),
                "delivery_time_max": _round_or_none(getattr(r, "delivery_time_max", None)),
            }
        )
    logger.debug(
        "tool get_aggregations returned run_id=%s results=%d elapsed_s=%.2f",
        run_id,
        len(results),
        time.monotonic() - t0,
    )
    return tool_result(ToolStatus.OK, json.dumps(results, indent=2))


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
    logger.debug("tool get_anomalies called run_id=%s dimension=%s", run_id, dimension)
    t0 = time.monotonic()
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
        logger.debug(
            "tool get_anomalies returned run_id=%s results=0 elapsed_s=%.2f",
            run_id,
            time.monotonic() - t0,
        )
        return tool_result(ToolStatus.EMPTY, f"No anomalies found for run_id={run_id}")

    results = []
    for r in rows:
        results.append(
            {
                "anomaly_type": r.anomaly_type,
                "dimension": r.dimension,
                "dimension_value": r.dimension_value,
                "metric": r.metric,
                "current_value": round(r.current_value, 4),
                "baseline_mean": round(r.baseline_mean, 4),
                "z_score": round(r.z_score, 2),
                "severity": r.severity,
            }
        )
    logger.debug(
        "tool get_anomalies returned run_id=%s results=%d elapsed_s=%.2f",
        run_id,
        len(results),
        time.monotonic() - t0,
    )
    return tool_result(ToolStatus.OK, json.dumps(results, indent=2))


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
    logger.debug("tool get_trends called run_id=%s dimension=%s", run_id, dimension)
    t0 = time.monotonic()
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
        logger.debug(
            "tool get_trends returned run_id=%s results=0 elapsed_s=%.2f",
            run_id,
            time.monotonic() - t0,
        )
        return tool_result(ToolStatus.EMPTY, f"No trends found for run_id={run_id}")

    results = []
    for r in rows:
        results.append(
            {
                "direction": r.direction,
                "dimension": r.dimension,
                "dimension_value": r.dimension_value,
                "metric": r.metric,
                "slope": round(r.slope, 6),
                "r_squared": round(r.r_squared, 3),
                "num_points": r.num_points,
                "start_value": round(r.start_value, 4),
                "end_value": round(r.end_value, 4),
            }
        )
    logger.debug(
        "tool get_trends returned run_id=%s results=%d elapsed_s=%.2f",
        run_id,
        len(results),
        time.monotonic() - t0,
    )
    return tool_result(ToolStatus.OK, json.dumps(results, indent=2))


@tool
def get_ml_report_summary(run_id: str) -> str:
    """Get a high-level summary of an ML analysis run.

    Returns counts and top anomalies/trends — useful for planning investigations.

    Args:
        run_id: The analysis run to summarize.
    """
    logger.debug("tool get_ml_report_summary called run_id=%s", run_id)
    t0 = time.monotonic()
    from llm_pipeline.email_analytics.storage import load_report

    report = load_report(run_id)
    if not report:
        logger.debug(
            "tool get_ml_report_summary returned run_id=%s results=0 elapsed_s=%.2f",
            run_id,
            time.monotonic() - t0,
        )
        return tool_result(ToolStatus.EMPTY, f"No report found for run_id={run_id}")

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

    logger.debug(
        "tool get_ml_report_summary returned run_id=%s results=1 elapsed_s=%.2f",
        run_id,
        time.monotonic() - t0,
    )
    return tool_result(ToolStatus.OK, json.dumps(summary, indent=2))


@tool
def get_data_completeness(
    run_id: str,
    dimension: str | None = None,
    dimension_value: str | None = None,
    field_name: str | None = None,
    limit: int = 50,
) -> str:
    """Retrieve data completeness metrics from an ML analysis run.

    Shows zero-value rates per field — use this to check if a metric is
    trustworthy before drawing conclusions from it.

    Args:
        run_id: The analysis run to query.
        dimension: Filter by dimension (e.g. "listid", "recipient_domain").
        dimension_value: Filter by specific dimension value.
        field_name: Filter by field name (e.g. "clicktrackingid", "injected_time").
        limit: Max rows to return.
    """
    logger.debug("tool get_data_completeness called run_id=%s dimension=%s", run_id, dimension)
    t0 = time.monotonic()
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from llm_pipeline.email_analytics.models import DataCompletenessRecord
    from llm_pipeline.email_analytics.storage import get_engine

    engine = get_engine()
    with Session(engine) as session:
        stmt = select(DataCompletenessRecord).where(DataCompletenessRecord.run_id == run_id)
        if dimension:
            stmt = stmt.where(DataCompletenessRecord.dimension == dimension)
        if dimension_value:
            stmt = stmt.where(DataCompletenessRecord.dimension_value == dimension_value)
        if field_name:
            stmt = stmt.where(DataCompletenessRecord.field_name == field_name)
        stmt = stmt.limit(limit)
        rows = session.execute(stmt).scalars().all()

    if not rows:
        logger.debug(
            "tool get_data_completeness returned run_id=%s results=0 elapsed_s=%.2f",
            run_id,
            time.monotonic() - t0,
        )
        return tool_result(
            ToolStatus.EMPTY, f"No data completeness records found for run_id={run_id}"
        )

    results = []
    for r in rows:
        results.append(
            {
                "time_window": r.time_window.isoformat(),
                "dimension": r.dimension,
                "dimension_value": r.dimension_value,
                "field_name": r.field_name,
                "total_records": r.total_records,
                "zero_count": r.zero_count,
                "zero_rate": round(r.zero_rate, 4),
            }
        )
    logger.debug(
        "tool get_data_completeness returned run_id=%s results=%d elapsed_s=%.2f",
        run_id,
        len(results),
        time.monotonic() - t0,
    )
    return tool_result(ToolStatus.OK, json.dumps(results, indent=2))


@tool
def compare_dimensions(
    run_id: str,
    dimension: str,
    values: list[str],
    metric: str = "delivery_rate",
) -> str:
    """Compare a metric across multiple dimension values side-by-side.

    Useful for comparing performance between segments, domains, etc.

    Args:
        run_id: The analysis run to query.
        dimension: The dimension to compare across (e.g. "listid").
        values: List of dimension values to compare (e.g. ["VH", "H", "M"]).
        metric: The metric to compare (default "delivery_rate"). Also supports
                "bounce_rate", "deferral_rate", "complaint_rate".
    """
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from llm_pipeline.email_analytics.models import AggregationRecord
    from llm_pipeline.email_analytics.storage import get_engine

    logger.debug("tool compare_dimensions called run_id=%s dimension=%s", run_id, dimension)
    t0 = time.monotonic()
    valid_metrics = {
        "delivery_rate",
        "bounce_rate",
        "deferral_rate",
        "complaint_rate",
        "pre_edge_latency_mean",
        "pre_edge_latency_p50",
        "pre_edge_latency_p95",
        "pre_edge_latency_p99",
        "pre_edge_latency_max",
        "delivery_time_mean",
        "delivery_time_p50",
        "delivery_time_p95",
        "delivery_time_p99",
        "delivery_time_max",
    }
    if metric not in valid_metrics:
        return tool_result(
            ToolStatus.ERROR,
            f"Invalid metric '{metric}'. Must be one of: {', '.join(sorted(valid_metrics))}",
        )

    engine = get_engine()
    with Session(engine) as session:
        stmt = (
            select(AggregationRecord)
            .where(AggregationRecord.run_id == run_id)
            .where(AggregationRecord.dimension == dimension)
            .where(AggregationRecord.dimension_value.in_(values))
        )
        rows = session.execute(stmt).scalars().all()

    if not rows:
        logger.debug(
            "tool compare_dimensions returned run_id=%s results=0 elapsed_s=%.2f",
            run_id,
            time.monotonic() - t0,
        )
        return tool_result(
            ToolStatus.EMPTY,
            f"No aggregation data found for run_id={run_id}, dimension={dimension}",
        )

    result: dict[str, list[dict]] = {}
    for r in rows:
        val = r.dimension_value
        if val not in result:
            result[val] = []
        result[val].append(
            {
                "time_window": r.time_window.isoformat(),
                metric: round(getattr(r, metric), 4),
                "total": r.total,
            }
        )
    logger.debug(
        "tool compare_dimensions returned run_id=%s results=%d elapsed_s=%.2f",
        run_id,
        len(result),
        time.monotonic() - t0,
    )
    return tool_result(ToolStatus.OK, json.dumps(result, indent=2))


# Tool registries per agent role
ORCHESTRATOR_ML_TOOLS = [get_ml_report_summary, get_anomalies, get_trends]
INVESTIGATOR_ML_TOOLS = [
    get_aggregations,
    get_anomalies,
    get_trends,
    get_ml_report_summary,
    get_data_completeness,
    compare_dimensions,
]
