"""Reporting tools — structured output from investigators."""

from __future__ import annotations

import logging

from langchain_core.tools import tool

from llm_pipeline.tools.result import ToolStatus, tool_result

logger = logging.getLogger(__name__)


@tool
def report_finding(
    statement: str,
    status: str,
    evidence: str = "[]",
    metrics_cited: str = "{}",
) -> str:
    """Report a finding from your investigation with its status and supporting evidence.

    You MUST call this tool at least once before finishing your investigation.

    Args:
        statement: A clear, one-sentence description of what you found.
        status: One of "confirmed", "disproven", or "inconclusive".
        evidence: JSON array of evidence strings (e.g. '["bounce rate 12% vs baseline 3%"]').
        metrics_cited: JSON object of metric name to value (e.g. '{"delivery_rate": 0.88}').
    """
    logger.info("Finding reported: [%s] %s", status, statement)
    return tool_result(
        ToolStatus.OK,
        f"Finding recorded: [{status}] {statement} "
        f"(evidence={evidence}, metrics={metrics_cited})",
    )


@tool
def report_hypothesis(
    statement: str,
    reasoning: str,
) -> str:
    """Report an untested hypothesis for future investigation.

    Call this for ideas you formed but could not test within this investigation.

    Args:
        statement: The hypothesis — what you think might be true.
        reasoning: Why you think this — what evidence or pattern led you here.
    """
    logger.info("Hypothesis reported: %s", statement)
    return tool_result(ToolStatus.OK, f"Hypothesis recorded: {statement} (reasoning: {reasoning})")


# --- Tool role declarations for auto-discovery ---
TOOL_ROLES = [
    (report_finding,    ["investigator"]),
    (report_hypothesis, ["investigator"]),
]

# Legacy alias
REPORTING_TOOLS = [report_finding, report_hypothesis]
