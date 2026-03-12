"""Result extraction and adapter for the investigator agent."""

from __future__ import annotations

import json
import logging

from llm_pipeline.agents.contracts import InvestigationOutput
from llm_pipeline.agents.state import InvestigatorState
from llm_pipeline.tools.result import ToolStatus, parse_tool_status

logger = logging.getLogger(__name__)


def _extract_results(state: InvestigatorState) -> dict:
    """Extract findings from reporting tool calls in the message history.

    Scans all messages for report_finding and report_hypothesis tool calls,
    parses their arguments into Finding/Hypothesis objects. Falls back to
    creating an INCONCLUSIVE finding from the final message if no reporting
    tools were called.
    """
    from datetime import UTC, datetime

    from llm_pipeline.agents.models import Finding, FindingStatus, Hypothesis

    topic = state["topic"]
    run_id = state.get("run_id", "")
    now = datetime.now(UTC)

    findings: list[Finding] = []
    hypotheses: list[Hypothesis] = []
    digest_lines: list[str] = []

    # Scan all messages for reporting tool calls
    for msg in state["messages"]:
        if not hasattr(msg, "tool_calls") or not msg.tool_calls:
            continue
        for tc in msg.tool_calls:
            name = tc.get("name", "")
            args = tc.get("args", {})

            if name == "report_finding":
                normalization_count = 0

                # Parse metrics_cited — could be JSON string or dict
                metrics_cited = args.get("metrics_cited", "{}")
                if isinstance(metrics_cited, str):
                    try:
                        metrics_cited = json.loads(metrics_cited)
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(
                            "[normalization] %s: metrics_cited is not valid JSON: %r",
                            topic.title,
                            metrics_cited,
                        )
                        normalization_count += 1
                        metrics_cited = {}
                if not isinstance(metrics_cited, dict):
                    metrics_cited = {}
                # Filter to numeric values only (LLM sometimes passes strings like "7-24")
                clean_metrics: dict[str, float] = {}
                for k, v in metrics_cited.items():
                    try:
                        clean_metrics[k] = float(v)
                    except (ValueError, TypeError):
                        logger.warning(
                            "[normalization] %s: dropping non-numeric metric %s=%r",
                            topic.title,
                            k,
                            v,
                        )
                        normalization_count += 1
                metrics_cited = clean_metrics

                # Parse evidence — could be JSON string or list
                evidence = args.get("evidence", "[]")
                if isinstance(evidence, str):
                    try:
                        evidence = json.loads(evidence)
                    except (json.JSONDecodeError, TypeError):
                        evidence = [evidence] if evidence else []
                if not isinstance(evidence, list):
                    evidence = [str(evidence)]

                # Parse status
                status_str = args.get("status", "inconclusive")
                try:
                    status = FindingStatus(status_str)
                except ValueError:
                    logger.warning(
                        "[normalization] %s: invalid status %r, coercing to INCONCLUSIVE",
                        topic.title,
                        status_str,
                    )
                    normalization_count += 1
                    status = FindingStatus.INCONCLUSIVE

                if normalization_count:
                    digest_lines.append(
                        f"[normalization] {topic.title}: {normalization_count} fields normalized"
                    )

                finding = Finding(
                    topic_title=topic.title,
                    statement=args.get("statement", ""),
                    status=status,
                    evidence=evidence,
                    metrics_cited=metrics_cited,
                    created_at=now,
                    run_id=run_id,
                )
                findings.append(finding)
                digest_lines.append(f"[finding:{status.value}] {finding.statement}")

            elif name == "report_hypothesis":
                hypothesis = Hypothesis(
                    topic_title=topic.title,
                    statement=args.get("statement", ""),
                    reasoning=args.get("reasoning", ""),
                    created_at=now,
                    run_id=run_id,
                )
                hypotheses.append(hypothesis)
                digest_lines.append(f"[hypothesis] {hypothesis.statement}")

    # Fallback: no reporting tools were called — create INCONCLUSIVE from final message
    if not findings:
        logger.warning(
            "[normalization] %s: no reporting tools called — creating fallback finding",
            topic.title,
        )
        last_message = state["messages"][-1]
        raw_content = last_message.content if hasattr(last_message, "content") else str(last_message)
        # content can be a list of blocks (text + tool_use) — extract text parts
        if isinstance(raw_content, list):
            text_parts = [
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in raw_content
                if not (isinstance(block, dict) and block.get("type") == "tool_use")
            ]
            content = " ".join(p for p in text_parts if p).strip() or f"Investigation exhausted budget on: {topic.title}"
        else:
            content = raw_content
        finding = Finding(
            topic_title=topic.title,
            statement=content[:500] if len(content) > 500 else content,
            status=FindingStatus.INCONCLUSIVE,
            evidence=[],
            created_at=now,
            run_id=run_id,
            tool_use_failed=True,
        )
        findings.append(finding)
        digest_lines.append(f"[finding:inconclusive] {topic.title}: no reporting tools called")

    # Surface per-investigator tool health to orchestrator
    from langchain_core.messages import ToolMessage

    error_tool_count = sum(
        1
        for msg in state["messages"]
        if isinstance(msg, ToolMessage)
        and parse_tool_status(msg.content if isinstance(msg.content, str) else "")
        in (ToolStatus.ERROR, ToolStatus.EMPTY)
    )
    if error_tool_count:
        digest_lines.append(
            f"[tool_errors] {topic.title}: {error_tool_count} tool calls returned EMPTY/ERROR"
        )

    # Count total tool calls for diagnostics
    total_tool_calls = sum(
        len(msg.tool_calls)
        for msg in state["messages"]
        if hasattr(msg, "tool_calls") and msg.tool_calls
    )
    is_fallback = any(f.tool_use_failed for f in findings)
    logger.info(
        "extract_results completed run_id=%s topic=%s "
        "findings=%d hypotheses=%d tool_calls=%d is_fallback=%s",
        run_id,
        topic.title,
        len(findings),
        len(hypotheses),
        total_tool_calls,
        is_fallback,
    )

    return {
        "findings": findings,
        "hypotheses": hypotheses,
        "digest_lines": digest_lines,
    }


class InvestigatorResultAdapter:
    """Pass-through adapter — investigator already produces standard output."""

    def adapt(self, raw_output: dict) -> InvestigationOutput:
        return InvestigationOutput(
            findings=raw_output.get("findings", []),
            hypotheses=raw_output.get("hypotheses", []),
            digest_lines=raw_output.get("digest_lines", []),
            completed_topics=raw_output.get("completed_topics", []),
            topic_errors=raw_output.get("topic_errors", []),
        )
