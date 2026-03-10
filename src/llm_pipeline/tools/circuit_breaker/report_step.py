"""report_step tool."""

from __future__ import annotations

import logging

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def report_step(step_description: str) -> str:
    """Log a single investigation step for the checkpoint digest.

    Args:
        step_description: One-line description of what was done or found.
    """
    logger.info("Investigation step: %s", step_description)
    return f"Logged: {step_description}"
