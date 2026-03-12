"""Synthesizer agent — LLM-powered narrative synthesis after investigation loop.

Runs once after assemble_report, before checkpoint. Produces an executive summary
and structured observations from the assembled report and findings.
"""

from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from llm_pipeline.agents.prompts import SYNTHESIZER_SYSTEM_PROMPT
from llm_pipeline.agents.state import InvestigationCycleState
from llm_pipeline.config import settings
from llm_pipeline.models.llm import get_llm
from llm_pipeline.models.rate_limiter import get_rate_limiter
from llm_pipeline.models.token_tracker import get_tracker

logger = logging.getLogger(__name__)


def _get_synthesizer_prompt() -> str:
    """Build the synthesizer system prompt with domain knowledge."""
    from llm_pipeline.agents.domain_registry import get_active_domain

    domain = get_active_domain()
    domain_knowledge = domain.investigator_domain_prompt if domain else ""
    return SYNTHESIZER_SYSTEM_PROMPT.format(domain_knowledge=domain_knowledge)


def _build_synthesis_input(state: InvestigationCycleState) -> str:
    """Format the assembled data for the synthesizer's input message."""
    findings = state.get("findings", [])
    hypotheses = state.get("hypotheses", [])
    review_annotations = state.get("review_annotations", [])
    report = state.get("report")

    lines = []

    # Report summary if available
    if report is not None:
        try:
            structured = report.structured
            issues = getattr(structured, "confirmed_issues", [])
            lines.append(f"Confirmed issues: {len(issues)}")
            ts = getattr(structured, "trend_summary", None)
            if ts is not None:
                lines.append(
                    f"Trends: {ts.improving_count} improving, "
                    f"{ts.degrading_count} degrading, {ts.stable_count} stable"
                )
            lines.append("")
        except AttributeError:
            pass

    # Findings by status
    if findings:
        by_status: dict[str, list] = {}
        for f in findings:
            by_status.setdefault(f.status.value, []).append(f)

        for status_label in ["confirmed", "disproven", "inconclusive"]:
            group = by_status.get(status_label, [])
            if not group:
                continue
            lines.append(f"Findings — {status_label.upper()}:")
            for f in group:
                line = f"  - {f.statement}"
                if f.evidence:
                    line += f" (evidence: {'; '.join(f.evidence[:2])})"
                lines.append(line)
        lines.append("")

    # Reviewer annotations
    if review_annotations:
        lines.append("Reviewer assessments:")
        for ann in review_annotations:
            lines.append(
                f"  [{ann.assessment.value}] {ann.finding_statement[:60]} "
                f"→ {ann.suggested_action.value}"
            )
        lines.append("")

    # Hypotheses
    if hypotheses:
        lines.append("Untested hypotheses:")
        for h in hypotheses:
            lines.append(f"  - {h.statement}")
        lines.append("")

    return "\n".join(lines) or "No findings or data to synthesize."


def _parse_synthesis(content: str) -> tuple[str, str]:
    """Parse synthesizer LLM response into (narrative, executive_summary).

    Returns (full_narrative_text, executive_summary).
    """
    text = content.strip()
    if text.startswith("```"):
        text_lines = text.split("\n")
        text_lines = [line for line in text_lines if not line.strip().startswith("```")]
        text = "\n".join(text_lines)

    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            return text, ""

        executive_summary = data.get("executive_summary", "")
        observations = data.get("observations", [])

        # Build narrative from structured output
        narrative_parts = []
        if executive_summary:
            narrative_parts.append(f"Executive Summary: {executive_summary}")

        # Group observations by section
        sections: dict[str, list[str]] = {}
        for obs in observations:
            if isinstance(obs, dict):
                section = obs.get("section", "other")
                note = obs.get("note", "")
                if note:
                    sections.setdefault(section, []).append(note)

        section_titles = {
            "cross_cutting_patterns": "Cross-Cutting Patterns",
            "data_quality": "Data Quality",
            "contradictions": "Contradictions",
            "next_cycle_focus": "Next Cycle Focus",
        }

        for key, title in section_titles.items():
            notes = sections.get(key, [])
            if notes:
                narrative_parts.append(f"{title}:")
                for note in notes:
                    narrative_parts.append(f"  - {note}")

        return "\n".join(narrative_parts), executive_summary

    except (json.JSONDecodeError, Exception) as e:
        logger.warning("Failed to parse synthesis response: %s", e)
        return text, ""


def synthesize_narrative(state: InvestigationCycleState) -> dict:
    """Produce narrative synthesis from investigation results. Single LLM call."""
    run_id = state.get("run_id", "")
    findings = state.get("findings", [])

    logger.info(
        "synthesize_narrative started run_id=%s findings=%d",
        run_id, len(findings),
    )

    if not findings:
        logger.info("synthesize_narrative: no findings, skipping")
        return {
            "synthesis_narrative": "",
            "digest_lines": ["[synthesis] No findings to synthesize — skipped"],
        }

    synthesis_input = _build_synthesis_input(state)
    system_prompt = _get_synthesizer_prompt()

    llm = get_llm(role="synthesizer")
    get_rate_limiter().acquire()
    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=synthesis_input),
    ])
    get_tracker().record(response, model=settings.model_synthesizer)
    usage = getattr(response, "usage_metadata", None)
    if usage:
        inp = (usage.get("input_tokens", 0) if isinstance(usage, dict)
               else getattr(usage, "input_tokens", 0))
        get_rate_limiter().record(inp)

    narrative, executive_summary = _parse_synthesis(response.content)

    digest_lines = [f"[synthesis] Narrative produced ({len(narrative)} chars)"]
    if executive_summary:
        digest_lines.append(f"[synthesis] Summary: {executive_summary[:120]}")

    logger.info(
        "synthesize_narrative completed run_id=%s narrative_len=%d",
        run_id, len(narrative),
    )

    return {
        "synthesis_narrative": narrative,
        "digest_lines": digest_lines,
    }
