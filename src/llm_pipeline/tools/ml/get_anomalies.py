"""get_anomalies tool."""

from __future__ import annotations

import json
import logging
import time

from langchain_core.tools import tool

from llm_pipeline.tools.result import ToolStatus, tool_result

logger = logging.getLogger(__name__)


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
