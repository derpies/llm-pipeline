"""Circuit breaker tools for controlling investigation cycles."""

from llm_pipeline.tools.circuit_breaker.check_budget import check_budget
from llm_pipeline.tools.circuit_breaker.check_budget_exceeded import check_budget_exceeded
from llm_pipeline.tools.circuit_breaker.report_step import log_step

# --- Tool role declarations for auto-discovery ---
TOOL_ROLES = [
    (log_step, ["investigator"]),
    (check_budget, ["investigator"]),
]

__all__ = ["check_budget_exceeded", "check_budget", "log_step", "TOOL_ROLES"]
