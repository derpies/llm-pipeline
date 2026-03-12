"""Investigator agent — examines a specific topic using ML tools."""

from __future__ import annotations

import logging
import time

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from llm_pipeline.agents.prompts import INVESTIGATOR_SYSTEM_PROMPT
from llm_pipeline.agents.roles import get_role_prompt_supplement
from llm_pipeline.agents.state import InvestigatorState
from llm_pipeline.config import settings
from llm_pipeline.models.llm import get_llm
from llm_pipeline.models.rate_limiter import get_rate_limiter
from llm_pipeline.models.token_tracker import get_tracker
from llm_pipeline.tools.registry import get_tools
from llm_pipeline.tools.result import ToolStatus, parse_tool_status

logger = logging.getLogger(__name__)

# Tools that are NOT ML query tools (used to build dynamic tool name list in brief)
_NON_ML_TOOL_NAMES = {
    "report_finding", "report_hypothesis", "retrieve_knowledge",
    "log_step", "check_budget",
}


def _build_investigator_prompt(role_name: str, domain_name: str | None = None) -> str:
    """Build the investigator system prompt with domain knowledge and role supplement."""
    from llm_pipeline.agents.domain_registry import get_active_domain

    domain = get_active_domain(domain_name)
    domain_knowledge = domain.investigator_domain_prompt if domain else ""

    base_prompt = INVESTIGATOR_SYSTEM_PROMPT.format(domain_knowledge=domain_knowledge)

    role_supplement = get_role_prompt_supplement(role_name, domain_name=domain_name)
    if role_supplement:
        base_prompt = f"{base_prompt}\n\n{role_supplement}"
    return base_prompt


def _count_consecutive_non_ok(messages: list) -> int:
    """Count consecutive non-OK ToolMessages from the tail of the history.

    Uses the structured ``[OK]``/``[EMPTY]``/``[ERROR]`` prefix convention.
    Unprefixed messages (backward compat) are treated as OK and stop the count.
    """
    from langchain_core.messages import ToolMessage

    count = 0
    for msg in reversed(messages):
        if not isinstance(msg, ToolMessage):
            break
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        status = parse_tool_status(content)
        if status is None or status == ToolStatus.OK:
            break
        count += 1
    return count


def _should_continue(state: InvestigatorState) -> str:
    """Route: continue tool loop or finish.

    Checks three signals before allowing another LLM call:
    1. Max LLM round-trips (hard cap)
    2. Consecutive tool errors (catches fabricated parameters)
    3. Global spend budget (stop early rather than waiting for orchestrator)
    """
    from langchain_core.messages import AIMessage

    last = state["messages"][-1]
    if not (hasattr(last, "tool_calls") and last.tool_calls):
        return END

    messages = state["messages"]
    topic_title = state["topic"].title if state.get("topic") else "unknown"

    # 1. Max LLM calls
    llm_calls = sum(1 for m in messages if isinstance(m, AIMessage))
    if llm_calls >= settings.investigator_max_llm_calls:
        logger.warning(
            "investigator circuit breaker: max_llm_calls reached "
            "topic=%s calls=%d limit=%d",
            topic_title,
            llm_calls,
            settings.investigator_max_llm_calls,
        )
        return END

    # 2. Consecutive tool errors
    consec_errors = _count_consecutive_non_ok(messages)
    if consec_errors >= settings.investigator_max_consecutive_errors:
        logger.warning(
            "investigator circuit breaker: consecutive_errors reached "
            "topic=%s errors=%d limit=%d",
            topic_title,
            consec_errors,
            settings.investigator_max_consecutive_errors,
        )
        return END

    # 3. Global spend check
    tracker = get_tracker()
    if tracker.total_cost_usd >= settings.circuit_breaker_max_spend_usd:
        logger.warning(
            "investigator circuit breaker: global spend exceeded "
            "topic=%s spent=%.2f limit=%.2f",
            topic_title,
            tracker.total_cost_usd,
            settings.circuit_breaker_max_spend_usd,
        )
        return END

    return "tools"


def _call_investigator(state: InvestigatorState) -> dict:
    """Invoke the investigator LLM with the current state."""
    tools = get_tools("investigator")
    llm = get_llm(role="investigator").bind_tools(tools)

    topic = state["topic"]
    run_id = state.get("run_id", "")
    ml_run_id = state.get("ml_run_id", "") or run_id

    # On first call, inject the investigation brief
    if len(state["messages"]) == 0 or (
        len(state["messages"]) == 1 and isinstance(state["messages"][0], HumanMessage)
    ):
        brief_parts = [
            f"Investigate: {topic.title}",
            f"Dimension: {topic.dimension}={topic.dimension_value}",
            f"Metrics of interest: {', '.join(topic.metrics)}",
            f"Question: {topic.question}",
            f"Context: {topic.context}",
            f"\n*** IMPORTANT — YOUR RUN_ID IS: {ml_run_id} ***",
            f"Pass run_id=\"{ml_run_id}\" to EVERY ML tool call below:",
            f'{", ".join(sorted(t.name for t in tools if t.name not in _NON_ML_TOOL_NAMES))}',
        ]

        # Inject prior context for follow-up rounds
        prior_context = state.get("prior_context", "")
        if prior_context:
            brief_parts.append(f"\n--- Prior findings from earlier rounds ---\n{prior_context}")

        # Inject pre-fetched grounding context for this role
        grounding_context = state.get("grounding_context", "")
        if grounding_context:
            brief_parts.append(f"\n--- Domain Knowledge ---\n{grounding_context}")

        brief_parts.append(
            "\nUse the ML tools to examine the data. Form a hypothesis, test it, "
            "and report your findings using report_finding and report_hypothesis tools. "
            "You MUST call report_finding at least once before finishing."
        )
        brief_parts.append(
            f"\nBUDGET: You have {settings.investigator_max_llm_calls} tool-call rounds. "
            f"Reserve the last {settings.investigator_report_reserve} for "
            f"report_finding/report_hypothesis. "
            f"If you exhaust your budget without reporting, your work is lost."
        )
        brief = "\n".join(brief_parts)
        logger.info(
            "investigator brief sent run_id=%s topic=%s dimension=%s=%s "
            "role=%s has_prior_context=%s has_grounding=%s",
            run_id,
            topic.title,
            topic.dimension,
            topic.dimension_value,
            topic.role,
            bool(prior_context),
            bool(grounding_context),
        )

        # Build system prompt with role-specific supplement
        domain_name = state.get("domain_name")
        system_prompt = _build_investigator_prompt(topic.role, domain_name=domain_name)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=brief),
        ]
    else:
        # Build system prompt with role-specific supplement for subsequent calls
        domain_name = state.get("domain_name")
        system_prompt = _build_investigator_prompt(topic.role, domain_name=domain_name)

        messages = [SystemMessage(content=system_prompt)] + list(state["messages"])

        # Mid-loop budget nudge: when remaining calls <= reserve, inject
        # a forcing message to stop exploring and report findings.
        from langchain_core.messages import AIMessage

        calls_used = sum(1 for m in messages if isinstance(m, AIMessage))
        remaining = settings.investigator_max_llm_calls - calls_used
        if remaining <= settings.investigator_report_reserve:
            nudge = (
                f"BUDGET WARNING: You have used {calls_used} of "
                f"{settings.investigator_max_llm_calls} rounds. "
                f"Only {remaining} remain. STOP exploring data. "
                f"Call report_finding NOW with what you have learned so far. "
                f"If you do not call report_finding, all your work is lost."
            )
            messages.append(HumanMessage(content=nudge))
            logger.info(
                "investigator budget nudge injected run_id=%s topic=%s "
                "calls_used=%d remaining=%d",
                run_id, topic.title, calls_used, remaining,
            )

    get_rate_limiter().acquire()
    t0 = time.monotonic()
    try:
        response = llm.invoke(messages)
    except Exception as exc:
        elapsed = time.monotonic() - t0
        logger.warning(
            "investigator llm_call failed run_id=%s topic=%s messages=%d "
            "elapsed_s=%.2f error=%s",
            run_id, topic.title, len(messages), elapsed, exc,
        )
        # Return a text-only AIMessage so _should_continue routes to END
        # and extract_results can salvage any findings from prior messages.
        from langchain_core.messages import AIMessage

        return {"messages": [AIMessage(
            content=f"[LLM call failed: {type(exc).__name__}. "
            f"Ending investigation with findings collected so far.]"
        )]}
    elapsed = time.monotonic() - t0
    get_tracker().record(response, model=settings.model_investigator)
    usage = getattr(response, "usage_metadata", None)
    if usage:
        inp = (usage.get("input_tokens", 0) if isinstance(usage, dict)
               else getattr(usage, "input_tokens", 0))
        get_rate_limiter().record(inp)
    logger.debug(
        "investigator llm_call run_id=%s topic=%s messages=%d elapsed_s=%.2f",
        run_id,
        topic.title,
        len(messages),
        elapsed,
    )

    # Early bail protection: if the LLM returns text-only (no tool calls) and
    # has never used ML tools, retry once with a forcing nudge. This catches
    # cases where the LLM asks for run_id despite it being in the brief.
    if not (hasattr(response, "tool_calls") and response.tool_calls):
        from langchain_core.messages import ToolMessage

        has_queried_data = any(
            isinstance(m, ToolMessage)
            and getattr(m, "name", None) not in _NON_ML_TOOL_NAMES
            for m in state["messages"]
        )
        if not has_queried_data:
            logger.warning(
                "investigator early bail detected — retrying with nudge "
                "run_id=%s topic=%s",
                run_id, topic.title,
            )
            nudge = (
                f"You have NOT used any tools yet. The run_id is: {ml_run_id}\n"
                f"Call an ML tool NOW. For example:\n"
                f'get_http_anomalies(run_id="{ml_run_id}") or '
                f'get_http_aggregations(run_id="{ml_run_id}", '
                f'dimension="{topic.dimension}", '
                f'dimension_value="{topic.dimension_value}")'
            )
            messages.append(response)
            messages.append(HumanMessage(content=nudge))
            get_rate_limiter().acquire()
            try:
                response = llm.invoke(messages)
            except Exception:
                pass  # Fall through with the original text response
            else:
                get_tracker().record(response, model=settings.model_investigator)

    return {"messages": [response]}


# Names of ML tools whose run_id must match the ML analysis run
_ML_TOOL_NAMES = {
    "get_aggregations", "get_anomalies", "get_trends",
    "get_ml_report_summary", "get_data_completeness", "compare_dimensions",
    "get_http_aggregations", "get_http_anomalies", "get_http_trends",
    "get_http_report_summary", "get_http_data_completeness", "compare_http_dimensions",
}


def _patch_ml_run_id(state: InvestigatorState) -> dict:
    """Override run_id in ML tool calls with the correct ml_run_id from state.

    LLMs sometimes hallucinate run_ids. This node mutates tool_call args
    in-place on the AIMessage already in state, so the downstream ToolNode
    executes with the correct value. Returns no state updates.
    """
    ml_run_id = state.get("ml_run_id", "")
    if not ml_run_id:
        return {}

    last_msg = state["messages"][-1]
    if not hasattr(last_msg, "tool_calls") or not last_msg.tool_calls:
        return {}

    for tc in last_msg.tool_calls:
        if tc.get("name") in _ML_TOOL_NAMES and "run_id" in tc.get("args", {}):
            if tc["args"]["run_id"] != ml_run_id:
                logger.warning(
                    "Patched hallucinated run_id in %s: %r → %s",
                    tc["name"],
                    tc["args"]["run_id"],
                    ml_run_id,
                )
                tc["args"]["run_id"] = ml_run_id

    return {}


def build_investigator_graph():
    """Build the investigator subgraph with its own tool loop."""
    tools = get_tools("investigator")
    graph = StateGraph(InvestigatorState)

    graph.add_node("investigator", _call_investigator)
    graph.add_node("patch_ml_run_id", _patch_ml_run_id)
    graph.add_node("tools", ToolNode(tools))
    graph.add_node("extract_results", _extract_results)

    graph.add_edge(START, "investigator")
    graph.add_conditional_edges(
        "investigator",
        _should_continue,
        {"tools": "patch_ml_run_id", END: "extract_results"},
    )
    graph.add_edge("patch_ml_run_id", "tools")
    graph.add_edge("tools", "investigator")
    graph.add_edge("extract_results", END)

    return graph.compile()


# Import here to avoid circular — extract uses models from agents.models
from llm_pipeline.agents.plugins.investigator.extract import _extract_results  # noqa: E402
