"""Datetime utilities available to all agents."""

from llm_pipeline.tools.datetime.get_current_datetime import get_current_datetime

# --- Tool role declarations for auto-discovery ---
TOOL_ROLES = [
    (get_current_datetime, ["*"]),
]

__all__ = ["get_current_datetime", "TOOL_ROLES"]
