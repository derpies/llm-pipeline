"""Datetime utilities available to all agents."""

from llm_pipeline.tools.datetime.manipulate_datetime import manipulate_datetime

# --- Tool role declarations for auto-discovery ---
TOOL_ROLES = [
    (manipulate_datetime, ["*"]),
]

__all__ = ["manipulate_datetime", "TOOL_ROLES"]
