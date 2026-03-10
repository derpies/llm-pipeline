"""report_hypothesis tool."""

from __future__ import annotations

import logging

from langchain_core.tools import tool

from llm_pipeline.tools.result import ToolStatus, tool_result

logger = logging.getLogger(__name__)


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
