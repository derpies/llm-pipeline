"""Specialist investigator role definitions — prompt supplements and grounding retrieval."""

from __future__ import annotations

import logging

from llm_pipeline.agents.models import InvestigatorRole

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-role prompt supplements (appended to INVESTIGATOR_SYSTEM_PROMPT)
# ---------------------------------------------------------------------------

ROLE_PROMPT_SUPPLEMENTS: dict[InvestigatorRole, str] = {
    InvestigatorRole.REPUTATION: """\
You are a reputation specialist. Focus on:
- IP and domain reputation signals (sender score, blocklist presence)
- Warming schedules and volume ramp compliance
- Feedback loop complaint rates by IP pool
- Throttling and deferral patterns that indicate reputation damage
- Shared vs dedicated IP risk factors
Compare metrics across segments sharing the same IP pool.""",
    InvestigatorRole.COMPLIANCE: """\
You are an authentication/compliance specialist. Focus on:
- SPF, DKIM, DMARC pass/fail rates and alignment
- ARC chain validity for forwarded mail
- Per-account compliance breakdowns (accountid from XMRID)
- Policy misconfigurations (p=none vs p=reject implications)
- Non-compliant senders on shared pools as a risk vector
Cross-reference compliance failures with bounce codes (550 5.7.x).""",
    InvestigatorRole.ENGAGEMENT: """\
You are an engagement/list quality specialist. Focus on:
- Segment behavior differences (VH/H/M/L/VL/RO/NM/DS)
- List hygiene indicators: spam trap hits, complaint spikes, bounce patterns
- Sunset policy effectiveness (engagement recency vs deliverability)
- Zero-value field rates as data quality signals
- Cohort analysis: new subscribers vs long-dormant contacts
Compare engagement segment metrics against expected baselines.""",
    InvestigatorRole.ISP: """\
You are an ISP/mailbox provider specialist. Focus on:
- Provider-specific filtering behaviors (Gmail, Microsoft, Yahoo/AOL, Apple)
- MX-based provider identification patterns
- Provider-specific bounce code interpretation
- Inbox vs spam placement signals per provider
- Rate limiting and throttling policies unique to each provider
Group findings by provider and compare delivery patterns across them.""",
    InvestigatorRole.DIAGNOSTICS: """\
You are a general diagnostics investigator. Focus on:
- Sudden deliverability drops: isolate timing, affected segments, and trigger events
- Gradual declines: identify trend inflection points and contributing factors
- Bounce log analysis: classify by SMTP response code categories
- Data completeness: zero-value fields, missing tracking data, pipeline gaps
- Cross-cutting issues that span multiple domains
Start broad, then narrow to the most impactful signal.""",
}

# ---------------------------------------------------------------------------
# Per-role KB prefix mapping (for grounding retrieval filtering)
# ---------------------------------------------------------------------------

ROLE_KB_PREFIXES: dict[InvestigatorRole, list[str]] = {
    InvestigatorRole.REPUTATION: [
        "KB-03", "KB-09-37", "KB-09-38", "KB-09-42", "KB-11-53",
    ],
    InvestigatorRole.COMPLIANCE: [
        "KB-02", "KB-09-39",
    ],
    InvestigatorRole.ENGAGEMENT: [
        "KB-05", "KB-07-30", "KB-11-51", "KB-09-43", "KB-09-44",
    ],
    InvestigatorRole.ISP: [
        "KB-06", "KB-10", "KB-07-28", "KB-07-29", "KB-12-54",
    ],
    InvestigatorRole.DIAGNOSTICS: [
        "KB-01", "KB-04", "KB-07-31", "KB-08", "KB-09-41",
        "KB-09-45", "KB-11-50", "KB-11-52",
    ],
}

# ---------------------------------------------------------------------------
# Per-role natural language queries (used for vector search)
# ---------------------------------------------------------------------------

_ROLE_QUERIES: dict[InvestigatorRole, str] = {
    InvestigatorRole.REPUTATION: (
        "IP reputation, sender score, blocklists, throttling, "
        "warming, feedback loops, deferral patterns, shared IP risk"
    ),
    InvestigatorRole.COMPLIANCE: (
        "SPF DKIM DMARC authentication, ARC, BIMI, "
        "compliance failures, policy alignment, email authentication"
    ),
    InvestigatorRole.ENGAGEMENT: (
        "engagement segments, list quality, spam traps, sunset policies, "
        "subscriber recency, complaint rates, list hygiene"
    ),
    InvestigatorRole.ISP: (
        "Gmail Microsoft Yahoo Apple mailbox provider filtering, "
        "inbox placement, provider-specific bounce codes, rate limiting"
    ),
    InvestigatorRole.DIAGNOSTICS: (
        "deliverability drop, bounce logs, SMTP response codes, "
        "data completeness, trend analysis, delivery lifecycle"
    ),
}


def get_role_grounding(role: InvestigatorRole, top_k: int = 5) -> str:
    """Retrieve grounding context for a specialist role.

    Queries the Grounded tier of the knowledge store with a role-specific
    query. Returns a compact formatted string for injection into the
    investigation brief. Returns empty string on failure (non-blocking).
    """
    from llm_pipeline.knowledge.models import KnowledgeTier
    from llm_pipeline.knowledge.retrieval import retrieve_knowledge

    query = _ROLE_QUERIES.get(role, _ROLE_QUERIES[InvestigatorRole.DIAGNOSTICS])

    try:
        results = retrieve_knowledge(
            query=query,
            tiers=[KnowledgeTier.GROUNDED],
            top_k=top_k,
        )
    except Exception as e:
        logger.warning("get_role_grounding failed for role=%s: %s", role, e)
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
