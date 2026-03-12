"""compare_dimensions tool."""

from __future__ import annotations

import json
import logging
import time

from langchain_core.tools import tool

from llm_pipeline.tools.result import ToolStatus, tool_result

logger = logging.getLogger(__name__)


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
    return tool_result(ToolStatus.OK, json.dumps(result))
