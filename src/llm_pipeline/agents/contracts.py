"""Contracts for pluggable agents and investigation output."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from typing_extensions import TypedDict


class InvestigationOutput(TypedDict, total=False):
    """Standard output contract for investigation-cycle agents.

    Agents can produce additional fields, but these are required
    for fan-in to the orchestrator evaluate node.
    """

    findings: list
    hypotheses: list
    digest_lines: list  # list[str] for checkpoint digest
    completed_topics: list  # list[str] — topic titles completed
    topic_errors: list  # list[str] — error messages


class ResultAdapter(Protocol):
    """Converts agent-specific output into standard InvestigationOutput."""

    def adapt(self, raw_output: dict) -> InvestigationOutput: ...


@dataclass
class AgentManifest:
    """Contract for a pluggable agent.

    Attributes:
        name: Unique identifier (e.g. "investigator", "compliance_auditor").
        agent_type: "investigation" (fan-out peer) or "pipeline" (standalone).
        tool_role: Role name for ToolRegistry query.
        build_graph: Callable that returns a compiled LangGraph.
        state_class: TypedDict for the agent's state.
        result_adapter: investigation agents only — converts output to InvestigationOutput.
        system_prompt: System prompt for the agent's LLM calls.
        description: Human-readable, used in orchestrator prompts + CLI help.
        cli_command: pipeline agents: CLI command name.
        cli_handler: pipeline agents: Typer command function.
    """

    name: str
    agent_type: str  # "investigation" | "pipeline"
    tool_role: str
    build_graph: Callable[..., Any]
    state_class: type
    result_adapter: ResultAdapter | None = None
    system_prompt: str = ""
    description: str = ""
    cli_command: str | None = None
    cli_handler: Callable[..., Any] | None = None
