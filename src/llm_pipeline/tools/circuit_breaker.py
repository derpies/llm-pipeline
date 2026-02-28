"""Circuit breaker tools for controlling investigation cycles."""

from __future__ import annotations

import logging
import time

from langchain_core.tools import tool

from llm_pipeline.agents.models import CircuitBreakerBudget

logger = logging.getLogger(__name__)


def check_budget_exceeded(
    iteration_count: int,
    started_at_ts: float,
    budget: CircuitBreakerBudget,
) -> dict:
    """Check if any circuit breaker limit has been exceeded.

    Returns a dict with exceeded=True/False and details.
    """
    elapsed = time.time() - started_at_ts
    reasons = []

    if iteration_count >= budget.max_iterations:
        reasons.append(f"iterations: {iteration_count}/{budget.max_iterations}")
    if elapsed >= budget.max_seconds:
        reasons.append(f"time: {elapsed:.0f}s/{budget.max_seconds}s")

    return {
        "exceeded": len(reasons) > 0,
        "iteration_count": iteration_count,
        "elapsed_seconds": round(elapsed, 1),
        "budget": {
            "max_iterations": budget.max_iterations,
            "max_seconds": budget.max_seconds,
        },
        "reasons": reasons,
    }


@tool
def report_step(step_description: str) -> str:
    """Log a single investigation step for the checkpoint digest.

    Args:
        step_description: One-line description of what was done or found.
    """
    logger.info("Investigation step: %s", step_description)
    return f"Logged: {step_description}"


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
    import json

    budget = CircuitBreakerBudget(
        max_iterations=max_iterations,
        max_seconds=max_seconds,
    )
    result = check_budget_exceeded(iteration_count, started_at_timestamp, budget)
    return json.dumps(result, indent=2)


# Circuit breaker tools available to agents
CIRCUIT_BREAKER_TOOLS = [report_step, check_budget]
