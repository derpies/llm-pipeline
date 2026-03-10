"""Dry-run LLM that simulates API calls without hitting any provider.

Returns canned responses appropriate to each agent role. Tracks token
estimates so the full pipeline can be exercised — circuit breaker, token
tracker, checkpoint digest — without spending money or hitting rate limits.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable

logger = logging.getLogger(__name__)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(1, len(text) // 4)


def _estimate_messages_tokens(messages: list[BaseMessage]) -> int:
    total = 0
    for m in messages:
        if isinstance(m.content, str):
            total += _estimate_tokens(m.content)
        if hasattr(m, "tool_calls") and m.tool_calls:
            total += 50 * len(m.tool_calls)
    return total


_ORCHESTRATOR_PLAN_RESPONSE = json.dumps([{
    "title": "DRY_RUN: Engagement segment delivery analysis",
    "dimension": "engagement_segment",
    "dimension_value": "VH",
    "metrics": ["delivery_rate", "bounce_rate"],
    "question": "What is driving delivery rate changes in the VH segment?",
    "priority": "high",
    "context": "Dry-run placeholder topic for pipeline validation",
}])

_ORCHESTRATOR_EVAL_RESPONSE = json.dumps([])


class DryRunChatModel(BaseChatModel):
    """Fake LLM that returns canned responses and tracks token estimates."""

    model_name: str = "dry-run"
    role: str = ""

    class Config:
        arbitrary_types_allowed = True

    @property
    def _llm_type(self) -> str:
        return "dry-run"

    def bind_tools(self, tools: list, **kwargs: Any) -> Runnable:
        """Accept tools binding (no-op — we generate our own tool calls)."""
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        input_tokens = _estimate_messages_tokens(messages)
        content, tool_calls = self._pick_response(messages)
        output_tokens = _estimate_tokens(content) + 50 * len(tool_calls)

        msg = AIMessage(
            content=content,
            tool_calls=tool_calls,
            usage_metadata={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        )

        logger.info(
            "[dry-run] role=%s in=%d out=%d tools=%d",
            self.role, input_tokens, output_tokens, len(tool_calls),
        )

        return ChatResult(generations=[ChatGeneration(message=msg)])

    def _pick_response(self, messages: list[BaseMessage]) -> tuple[str, list[dict]]:
        if self.role == "orchestrator":
            return self._orchestrator_response(messages)
        elif self.role == "investigator":
            return self._investigator_response(messages)
        else:
            return "Dry-run response — no real LLM call made.", []

    def _orchestrator_response(self, messages: list[BaseMessage]) -> tuple[str, list[dict]]:
        last_content = ""
        for m in reversed(messages):
            if isinstance(m.content, str) and m.content:
                last_content = m.content
                break
        if "follow-up" in last_content.lower() or "evaluate" in last_content.lower():
            return _ORCHESTRATOR_EVAL_RESPONSE, []
        return _ORCHESTRATOR_PLAN_RESPONSE, []

    def _investigator_response(self, messages: list[BaseMessage]) -> tuple[str, list[dict]]:
        # Count how many tool round-trips have happened by counting ToolMessages
        tool_rounds = sum(1 for m in messages if isinstance(m, ToolMessage))

        if tool_rounds < 2:
            return "", [{
                "name": "get_aggregations",
                "args": {
                    "run_id": "dry-run",
                    "dimension": "engagement_segment",
                    "dimension_value": "VH",
                    "limit": 5,
                },
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "type": "tool_call",
            }]
        elif tool_rounds == 2:
            return "", [{
                "name": "report_finding",
                "args": {
                    "statement": "DRY_RUN: VH segment delivery rate within normal parameters",
                    "status": "inconclusive",
                    "evidence": '["dry-run placeholder"]',
                    "metrics_cited": '{"delivery_rate": 0.95}',
                },
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "type": "tool_call",
            }]
        else:
            return "Investigation complete (dry-run).", []
