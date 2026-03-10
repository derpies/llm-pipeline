"""Specialist investigator role definitions — domain-manifest-driven.

This module dispatches to the active domain's role definitions.
The actual role content (prompt supplements, KB prefixes, grounding queries)
lives in the domain package (e.g. domains/email_delivery/roles.py).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def get_role_prompt_supplement(role_name: str) -> str:
    """Get the prompt supplement for a specialist role from the active domain."""
    from llm_pipeline.agents.domain_registry import get_domain_roles

    roles = get_domain_roles()
    role_def = roles.get(role_name)
    if role_def is None:
        logger.warning("Unknown role '%s', no prompt supplement available", role_name)
        return ""
    return role_def.prompt_supplement


# Backward-compat: dict-like access for code that reads ROLE_PROMPT_SUPPLEMENTS[role]
class _RolePromptSupplementsProxy:
    """Proxy that looks up role prompt supplements from the active domain."""

    def __getitem__(self, key):
        return get_role_prompt_supplement(str(key) if not isinstance(key, str) else key)

    def get(self, key, default=""):
        result = get_role_prompt_supplement(str(key) if not isinstance(key, str) else key)
        return result if result else default


ROLE_PROMPT_SUPPLEMENTS = _RolePromptSupplementsProxy()


def get_role_grounding(role_name: str, top_k: int = 5) -> str:
    """Retrieve grounding context for a specialist role.

    Queries the Grounded tier of the knowledge store with a role-specific
    query from the active domain manifest. Returns a compact formatted string
    for injection into the investigation brief.
    Returns empty string on failure (non-blocking).
    """
    from llm_pipeline.agents.domain_registry import get_domain_roles
    from llm_pipeline.knowledge.models import KnowledgeTier
    from llm_pipeline.knowledge.retrieval import retrieve_knowledge

    roles = get_domain_roles()
    role_def = roles.get(str(role_name) if not isinstance(role_name, str) else role_name)

    if role_def is None or not role_def.grounding_queries:
        logger.debug("No grounding queries for role '%s'", role_name)
        return ""

    query = role_def.grounding_queries[0]

    try:
        results = retrieve_knowledge(
            query=query,
            tiers=[KnowledgeTier.GROUNDED],
            top_k=top_k,
        )
    except Exception as e:
        logger.warning("get_role_grounding failed for role=%s: %s", role_name, e)
        return ""

    if not results:
        return ""

    lines = []
    for r in results:
        # Truncate long statements to keep context bounded
        stmt = r.statement
        if len(stmt) > 300:
            stmt = stmt[:297] + "..."
        lines.append(f"- [{r.topic}] {stmt}")

    return "\n".join(lines)
