"""Shared state schemas for the multi-agent investigation cycle."""

from __future__ import annotations

import operator
from datetime import datetime
from typing import Annotated, Any

from langgraph.graph import MessagesState
from typing_extensions import TypedDict

from llm_pipeline.agents.models import (
    AnalyticalStrategy,
    CircuitBreakerBudget,
    Finding,
    GeneratedDocument,
    Hypothesis,
    InvestigationTopic,
)


class InvestigationCycleState(TypedDict, total=False):
    """Top-level state for the investigation cycle graph."""

    # Input
    ml_report: Any  # AnalysisReport from email_analytics
    run_id: str

    # Planning
    investigation_plan: list[InvestigationTopic]
    completed_topics: Annotated[list[str], operator.add]

    # Findings (fan-in from investigators)
    hypotheses: Annotated[list[Hypothesis], operator.add]
    findings: Annotated[list[Finding], operator.add]
    digest_lines: Annotated[list[str], operator.add]

    # Circuit breaker
    iteration_count: int
    total_tokens: int
    started_at: datetime
    budget: CircuitBreakerBudget

    # Error tracking
    evaluation_error: bool
    topic_errors: Annotated[list[str], operator.add]

    # Iteration context (passed to next round's investigators)
    prior_findings: list[Finding]
    prior_hypotheses: list[Hypothesis]

    # Output
    documents: Annotated[list[GeneratedDocument], operator.add]
    strategies: Annotated[list[AnalyticalStrategy], operator.add]
    checkpoint_digest: str


class InvestigatorState(MessagesState):
    """State for a single investigator subgraph.

    Extends MessagesState (has messages list) with investigation-specific fields.
    The messages list is private to this investigator — it doesn't flow back
    to the parent graph.
    """

    # Input from orchestrator
    topic: InvestigationTopic
    run_id: str
    prior_context: str  # Summary of prior findings for follow-up rounds

    # Output (flows back to parent via fan-in)
    hypotheses: Annotated[list[Hypothesis], operator.add]
    findings: Annotated[list[Finding], operator.add]
    digest_lines: Annotated[list[str], operator.add]
