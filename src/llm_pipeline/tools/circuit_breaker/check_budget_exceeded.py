"""check_budget_exceeded — non-tool helper for programmatic budget checks."""

from __future__ import annotations

import time

from llm_pipeline.agents.models import CircuitBreakerBudget
from llm_pipeline.models.token_tracker import get_tracker


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

    tracker = get_tracker()
    if tracker.total_tokens >= budget.max_tokens:
        reasons.append(f"tokens: {tracker.total_tokens}/{budget.max_tokens}")
    if tracker.total_cost_usd >= budget.max_spend_usd:
        reasons.append(f"spend: ${tracker.total_cost_usd:.2f}/${budget.max_spend_usd:.2f}")

    return {
        "exceeded": len(reasons) > 0,
        "iteration_count": iteration_count,
        "elapsed_seconds": round(elapsed, 1),
        "spend_usd": tracker.total_cost_usd,
        "total_tokens": tracker.total_tokens,
        "budget": {
            "max_iterations": budget.max_iterations,
            "max_seconds": budget.max_seconds,
            "max_tokens": budget.max_tokens,
            "max_spend_usd": budget.max_spend_usd,
        },
        "reasons": reasons,
    }
