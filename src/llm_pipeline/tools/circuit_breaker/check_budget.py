"""check_budget tool."""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from llm_pipeline.agents.models import CircuitBreakerBudget
from llm_pipeline.tools.circuit_breaker.check_budget_exceeded import check_budget_exceeded

logger = logging.getLogger(__name__)


@tool
def check_budget(
    iteration_count: int,
    started_at_timestamp: float,
    max_iterations: int = 5,
    max_seconds: int = 300,
) -> str:
    """Check remaining investigation budget.

    Args:
        iteration_count: Current iteration number.
        started_at_timestamp: Unix timestamp when the cycle started.
        max_iterations: Max allowed iterations.
        max_seconds: Max allowed seconds.
    """
    budget = CircuitBreakerBudget(
        max_iterations=max_iterations,
        max_seconds=max_seconds,
    )
    result = check_budget_exceeded(iteration_count, started_at_timestamp, budget)
    return json.dumps(result, indent=2)
