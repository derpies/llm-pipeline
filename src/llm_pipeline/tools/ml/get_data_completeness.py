"""get_data_completeness tool."""

from __future__ import annotations

import json
import logging
import time

from langchain_core.tools import tool

from llm_pipeline.tools.result import ToolStatus, tool_result

logger = logging.getLogger(__name__)


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
