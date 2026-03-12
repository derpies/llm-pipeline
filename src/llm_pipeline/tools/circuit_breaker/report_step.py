"""log_step tool — progress logging (NOT a reporting tool)."""

from __future__ import annotations

import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def log_step(step_description: str) -> str:
    """Log a single investigation step for the checkpoint digest.

    This is a PROGRESS LOGGING tool, not a reporting tool.
    To report findings, use report_finding instead.

    Args:
        step_description: One-line description of what was done or found.
    """
    logger.info("Investigation step: %s", step_description)
    return f"Logged: {step_description}"
