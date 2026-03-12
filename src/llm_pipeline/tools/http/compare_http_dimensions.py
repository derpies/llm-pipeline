"""compare_http_dimensions tool."""

from __future__ import annotations

import json
import logging
import time

from langchain_core.tools import tool

from llm_pipeline.tools.result import ToolStatus, tool_result

logger = logging.getLogger(__name__)


@tool
def compare_http_dimensions(
    run_id: str,
    dimension: str,
    values: list[str],
    metric: str = "success_rate",
) -> str:
    """Compare an HTTP metric across multiple dimension values side-by-side.

    Useful for comparing performance between hosts, request categories, upstreams, etc.

    Args:
        run_id: The HTTP analysis run to query.
        dimension: The dimension to compare across (e.g. "http_host", "request_category").
        values: List of dimension values to compare.
        metric: The metric to compare (default "success_rate"). Also supports
                "client_error_rate", "server_error_rate", "known_content_error_rate",
                "tts_p50", "tts_p95", "tts_p99", "tts_mean", "tts_max".
    """
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from llm_pipeline.http_analytics.models import HttpAggregationRecord
    from llm_pipeline.models.db import get_engine

    logger.debug("tool compare_http_dimensions called run_id=%s dimension=%s", run_id, dimension)
    t0 = time.monotonic()
    valid_metrics = {
        "success_rate",
        "client_error_rate",
        "server_error_rate",
        "known_content_error_rate",
        "tts_p50",
        "tts_p90",
        "tts_p95",
        "tts_p99",
        "tts_max",
        "tts_mean",
    }
    if metric not in valid_metrics:
        return tool_result(
            ToolStatus.ERROR,
            f"Invalid metric '{metric}'. Must be one of: {', '.join(sorted(valid_metrics))}",
        )

    engine = get_engine()
    with Session(engine) as session:
        stmt = (
            select(HttpAggregationRecord)
            .where(HttpAggregationRecord.run_id == run_id)
            .where(HttpAggregationRecord.dimension == dimension)
            .where(HttpAggregationRecord.dimension_value.in_(values))
        )
        rows = session.execute(stmt).scalars().all()

    if not rows:
        logger.debug(
            "tool compare_http_dimensions returned run_id=%s results=0 elapsed_s=%.2f",
            run_id, time.monotonic() - t0,
        )
        return tool_result(
            ToolStatus.EMPTY,
            f"No HTTP aggregation data found for run_id={run_id}, dimension={dimension}",
        )

    def _round_or_none(val, digits=4):
        return round(val, digits) if val is not None else None

    result: dict[str, list[dict]] = {}
    for r in rows:
        val = r.dimension_value
        if val not in result:
            result[val] = []
        metric_val = getattr(r, metric, None)
        result[val].append({
            "time_window": r.time_window.isoformat(),
            metric: _round_or_none(metric_val),
            "total": r.total,
        })
    logger.debug(
        "tool compare_http_dimensions returned run_id=%s results=%d elapsed_s=%.2f",
        run_id, len(result), time.monotonic() - t0,
    )
    return tool_result(ToolStatus.OK, json.dumps(result))
