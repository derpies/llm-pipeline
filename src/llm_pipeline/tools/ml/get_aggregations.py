"""get_aggregations tool."""

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
