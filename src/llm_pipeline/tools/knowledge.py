"""Agent tool for querying the knowledge store."""

import logging
import time

from langchain_core.tools import tool

from llm_pipeline.config import settings
from llm_pipeline.knowledge.models import KnowledgeScope
from llm_pipeline.tools.result import ToolStatus, tool_result

logger = logging.getLogger(__name__)


@tool
def retrieve_knowledge(
    query: str,
    scope: str = "community",
    account_id: str = "",
) -> str:
    """Search the knowledge store for relevant findings, hypotheses, and truths.

    Use this tool to check what the system already knows about a topic before
    investigating further. Results are weighted by tier (grounded > truth >
    finding > hypothesis) and confidence.

    Args:
        query: Natural language query describing what to search for.
        scope: "community" for aggregate knowledge, "account" for per-account.
        account_id: Required when scope is "account".
    """
    logger.debug("tool retrieve_knowledge called query=%.80s scope=%s", query, scope)
    t0 = time.monotonic()
    from llm_pipeline.knowledge.retrieval import retrieve_knowledge as _retrieve

    scope_enum = KnowledgeScope.ACCOUNT if scope == "account" else KnowledgeScope.COMMUNITY
    results = _retrieve(query=query, scope=scope_enum, account_id=account_id, top_k=5)

    if not results:
        logger.debug(
            "tool retrieve_knowledge returned results=0 elapsed_s=%.2f", time.monotonic() - t0
        )
        return tool_result(ToolStatus.EMPTY, "No relevant knowledge found in the knowledge store.")

    lines = []
    for i, r in enumerate(results, 1):
        tier_label = r.tier.value.upper()
        conf = f"{r.confidence:.0%}"
        status = f" [{r.finding_status}]" if r.finding_status else ""
        topic = f" ({r.topic})" if r.topic else ""
        lines.append(
            f"[{i}] {tier_label}{status} confidence={conf}{topic}\n"
            f"    {r.statement}\n"
            f"    score={r.weighted_score:.3f} observations={r.observation_count}"
        )

    logger.debug(
        "tool retrieve_knowledge returned results=%d elapsed_s=%.2f",
        len(results),
        time.monotonic() - t0,
    )
    return tool_result(ToolStatus.OK, "\n\n".join(lines))


# --- Tool role declarations for auto-discovery ---
# Conditional: only available to investigators when knowledge store is enabled
TOOL_ROLES = [
    (retrieve_knowledge, ["investigator"] if settings.investigator_use_knowledge_store else []),
]
