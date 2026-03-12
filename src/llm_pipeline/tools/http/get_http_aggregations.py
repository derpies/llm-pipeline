"""get_http_aggregations tool."""

from __future__ import annotations

import json
import logging
import time

from langchain_core.tools import tool

from llm_pipeline.tools.result import ToolStatus, tool_result

logger = logging.getLogger(__name__)


@tool
def get_http_aggregations(
    run_id: str,
    dimension: str | None = None,
    dimension_value: str | None = None,
    limit: int = 50,
) -> str:
    """Retrieve HTTP aggregation data from an ML analysis run.

    Args:
        run_id: The HTTP analysis run to query.
        dimension: Filter by dimension (e.g. "http_host", "request_category", "ua_category").
        dimension_value: Filter by specific dimension value.
        limit: Max rows to return.
    """
    logger.debug("tool get_http_aggregations called run_id=%s dimension=%s", run_id, dimension)
    t0 = time.monotonic()
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from llm_pipeline.http_analytics.models import HttpAggregationRecord
    from llm_pipeline.models.db import get_engine

    engine = get_engine()
    with Session(engine) as session:
        stmt = select(HttpAggregationRecord).where(HttpAggregationRecord.run_id == run_id)
        if dimension:
            stmt = stmt.where(HttpAggregationRecord.dimension == dimension)
        if dimension_value:
            stmt = stmt.where(HttpAggregationRecord.dimension_value == dimension_value)
        stmt = stmt.limit(limit)
        rows = session.execute(stmt).scalars().all()

    if not rows:
        logger.debug(
            "tool get_http_aggregations returned run_id=%s results=0 elapsed_s=%.2f",
            run_id, time.monotonic() - t0,
        )
        return tool_result(ToolStatus.EMPTY, f"No HTTP aggregation data found for run_id={run_id}")

    def _round_or_none(val, digits=4):
        return round(val, digits) if val is not None else None

    results = []
    for r in rows:
        results.append({
            "time_window": r.time_window.isoformat(),
            "dimension": r.dimension,
            "dimension_value": r.dimension_value,
            "total": r.total,
            "status_2xx": r.status_2xx,
            "status_3xx": r.status_3xx,
            "status_4xx": r.status_4xx,
            "status_5xx": r.status_5xx,
            "status_679": r.status_679,
            "status_other": r.status_other,
            "success_rate": round(r.success_rate, 4),
            "client_error_rate": round(r.client_error_rate, 4),
            "server_error_rate": round(r.server_error_rate, 4),
            "known_content_error_rate": round(r.known_content_error_rate, 4),
            "tts_p50": _round_or_none(r.tts_p50),
            "tts_p90": _round_or_none(r.tts_p90),
            "tts_p95": _round_or_none(r.tts_p95),
            "tts_p99": _round_or_none(r.tts_p99),
            "tts_max": _round_or_none(r.tts_max),
            "tts_mean": _round_or_none(r.tts_mean),
            "total_bytes": r.total_bytes,
            "mean_bytes": round(r.mean_bytes, 1),
            "empty_ua_count": r.empty_ua_count,
            "empty_upstream_count": r.empty_upstream_count,
            "empty_referrer_count": r.empty_referrer_count,
        })
    logger.debug(
        "tool get_http_aggregations returned run_id=%s results=%d elapsed_s=%.2f",
        run_id, len(results), time.monotonic() - t0,
    )
    return tool_result(ToolStatus.OK, json.dumps(results, indent=2))
