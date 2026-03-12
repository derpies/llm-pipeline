"""get_http_report_summary tool."""

from __future__ import annotations

import json
import logging
import time

from langchain_core.tools import tool

from llm_pipeline.tools.result import ToolStatus, tool_result

logger = logging.getLogger(__name__)


@tool
def get_http_report_summary(run_id: str) -> str:
    """Get a high-level summary of an HTTP ML analysis run.

    Returns counts and top anomalies/trends — useful for planning investigations.

    Args:
        run_id: The HTTP analysis run to summarize.
    """
    logger.debug("tool get_http_report_summary called run_id=%s", run_id)
    t0 = time.monotonic()
    from llm_pipeline.http_analytics.storage import load_report

    report = load_report(run_id)
    if not report:
        logger.debug(
            "tool get_http_report_summary returned run_id=%s results=0 elapsed_s=%.2f",
            run_id, time.monotonic() - t0,
        )
        return tool_result(ToolStatus.EMPTY, f"No HTTP report found for run_id={run_id}")

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
        high = [a for a in report.anomalies if a.severity in ("high", "critical")]
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
        "tool get_http_report_summary returned run_id=%s results=1 elapsed_s=%.2f",
        run_id, time.monotonic() - t0,
    )
    return tool_result(ToolStatus.OK, json.dumps(summary))
