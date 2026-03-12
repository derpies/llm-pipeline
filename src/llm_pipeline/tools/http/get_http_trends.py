"""get_http_trends tool."""

from __future__ import annotations

import json
import logging
import time

from langchain_core.tools import tool

from llm_pipeline.tools.result import ToolStatus, tool_result

logger = logging.getLogger(__name__)


@tool
def get_http_trends(
    run_id: str,
    dimension: str | None = None,
    direction: str | None = None,
    limit: int = 20,
) -> str:
    """Retrieve detected HTTP trends from an ML analysis run.

    Args:
        run_id: The HTTP analysis run to query.
        dimension: Filter by dimension.
        direction: Filter by direction ("improving", "degrading", "stable").
        limit: Max results to return.
    """
    logger.debug("tool get_http_trends called run_id=%s dimension=%s", run_id, dimension)
    t0 = time.monotonic()
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from llm_pipeline.http_analytics.models import HttpTrendRecord
    from llm_pipeline.models.db import get_engine

    engine = get_engine()
    with Session(engine) as session:
        stmt = select(HttpTrendRecord).where(HttpTrendRecord.run_id == run_id)
        if dimension:
            stmt = stmt.where(HttpTrendRecord.dimension == dimension)
        if direction:
            stmt = stmt.where(HttpTrendRecord.direction == direction)
        stmt = stmt.limit(limit)
        rows = session.execute(stmt).scalars().all()

    if not rows:
        logger.debug(
            "tool get_http_trends returned run_id=%s results=0 elapsed_s=%.2f",
            run_id, time.monotonic() - t0,
        )
        return tool_result(ToolStatus.EMPTY, f"No HTTP trends found for run_id={run_id}")

    results = []
    for r in rows:
        results.append({
            "direction": r.direction,
            "dimension": r.dimension,
            "dimension_value": r.dimension_value,
            "metric": r.metric,
            "slope": round(r.slope, 6),
            "r_squared": round(r.r_squared, 4),
            "num_points": r.num_points,
            "start_value": round(r.start_value, 4),
            "end_value": round(r.end_value, 4),
        })
    logger.debug(
        "tool get_http_trends returned run_id=%s results=%d elapsed_s=%.2f",
        run_id, len(results), time.monotonic() - t0,
    )
    return tool_result(ToolStatus.OK, json.dumps(results))
