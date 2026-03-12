"""get_http_anomalies tool."""

from __future__ import annotations

import json
import logging
import time

from langchain_core.tools import tool

from llm_pipeline.tools.result import ToolStatus, tool_result

logger = logging.getLogger(__name__)


@tool
def get_http_anomalies(
    run_id: str,
    dimension: str | None = None,
    anomaly_type: str | None = None,
    severity: str | None = None,
    limit: int = 20,
) -> str:
    """Retrieve detected HTTP anomalies from an ML analysis run.

    Args:
        run_id: The HTTP analysis run to query.
        dimension: Filter by dimension.
        anomaly_type: Filter by anomaly type (e.g. "error_rate_spike", "latency_spike").
        severity: Filter by severity ("critical", "high", "medium", "low").
        limit: Max results to return.
    """
    logger.debug("tool get_http_anomalies called run_id=%s dimension=%s", run_id, dimension)
    t0 = time.monotonic()
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from llm_pipeline.http_analytics.models import HttpAnomalyRecord
    from llm_pipeline.models.db import get_engine

    engine = get_engine()
    with Session(engine) as session:
        stmt = select(HttpAnomalyRecord).where(HttpAnomalyRecord.run_id == run_id)
        if dimension:
            stmt = stmt.where(HttpAnomalyRecord.dimension == dimension)
        if anomaly_type:
            stmt = stmt.where(HttpAnomalyRecord.anomaly_type == anomaly_type)
        if severity:
            stmt = stmt.where(HttpAnomalyRecord.severity == severity)
        stmt = stmt.limit(limit)
        rows = session.execute(stmt).scalars().all()

    if not rows:
        logger.debug(
            "tool get_http_anomalies returned run_id=%s results=0 elapsed_s=%.2f",
            run_id, time.monotonic() - t0,
        )
        return tool_result(ToolStatus.EMPTY, f"No HTTP anomalies found for run_id={run_id}")

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
    logger.debug(
        "tool get_http_anomalies returned run_id=%s results=%d elapsed_s=%.2f",
        run_id, len(results), time.monotonic() - t0,
    )
    return tool_result(ToolStatus.OK, json.dumps(results))
