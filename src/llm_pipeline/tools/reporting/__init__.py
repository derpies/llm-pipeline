"""Reporting tools — structured output from investigators."""

from llm_pipeline.tools.reporting.report_finding import report_finding
from llm_pipeline.tools.reporting.report_hypothesis import report_hypothesis

# --- Tool role declarations for auto-discovery ---
TOOL_ROLES = [
    (report_finding, ["investigator"]),
    (report_hypothesis, ["investigator"]),
]

__all__ = ["report_finding", "report_hypothesis", "TOOL_ROLES"]
