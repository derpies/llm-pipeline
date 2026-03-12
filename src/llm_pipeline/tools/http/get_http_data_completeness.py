"""get_http_data_completeness tool."""

from __future__ import annotations

import json
import logging
import time

from langchain_core.tools import tool

from llm_pipeline.tools.result import ToolStatus, tool_result

logger = logging.getLogger(__name__)


@tool
def get_http_data_completeness(
    run_id: str,
    dimension: str | None = None,
    field_name: str | None = None,
    limit: int = 20,
) -> str:
    """Retrieve HTTP data completeness metrics from an ML analysis run.

    Shows empty-value rates for key fields (useragent, upstream, referrer, accountid).

    Args:
        run_id: The HTTP analysis run to query.
        dimension: Filter by dimension.
        field_name: Filter by field name (e.g. "useragent", "upstream").
        limit: Max results to return.
    """
    logger.debug("tool get_http_data_completeness called run_id=%s", run_id)
    t0 = time.monotonic()
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from llm_pipeline.http_analytics.models import HttpDataCompletenessRecord
    from llm_pipeline.models.db import get_engine

    engine = get_engine()
    with Session(engine) as session:
        stmt = select(HttpDataCompletenessRecord).where(
            HttpDataCompletenessRecord.run_id == run_id
        )
        if dimension:
            stmt = stmt.where(HttpDataCompletenessRecord.dimension == dimension)
        if field_name:
            stmt = stmt.where(HttpDataCompletenessRecord.field_name == field_name)
        stmt = stmt.limit(limit)
        rows = session.execute(stmt).scalars().all()

    if not rows:
        logger.debug(
            "tool get_http_data_completeness returned run_id=%s results=0 elapsed_s=%.2f",
            run_id, time.monotonic() - t0,
        )
        return tool_result(
            ToolStatus.EMPTY, f"No HTTP completeness data found for run_id={run_id}"
        )

    results = []
    for r in rows:
        results.append({
            "time_window": r.time_window.isoformat(),
            "dimension": r.dimension,
            "dimension_value": r.dimension_value,
            "field_name": r.field_name,
            "total_records": r.total_records,
            "empty_count": r.empty_count,
            "empty_rate": round(r.empty_rate, 4),
        })
    logger.debug(
        "tool get_http_data_completeness returned run_id=%s results=%d elapsed_s=%.2f",
        run_id, len(results), time.monotonic() - t0,
    )
    return tool_result(ToolStatus.OK, json.dumps(results))
