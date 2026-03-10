"""Email delivery specialist investigator role definitions.

Defines per-role prompt supplements, KB prefixes, and grounding queries
for the email delivery domain.
"""

from __future__ import annotations

from llm_pipeline.agents.contracts import RoleDefinition

# ---------------------------------------------------------------------------
# Role definitions
# ---------------------------------------------------------------------------

REPUTATION = RoleDefinition(
    name="reputation",
    prompt_supplement="""\
You are a reputation specialist. Focus on:
- IP and domain reputation signals (sender score, blocklist presence)
- Warming schedules and volume ramp compliance
- Feedback loop complaint rates by IP pool
- Throttling and deferral patterns that indicate reputation damage
- Shared vs dedicated IP risk factors
Compare metrics across segments sharing the same IP pool.""",
    grounding_queries=[
        "IP reputation, sender score, blocklists, throttling, "
        "warming, feedback loops, deferral patterns, shared IP risk",
    ],
    grounding_kb_prefixes=[
        "KB-03", "KB-09-37", "KB-09-38", "KB-09-42", "KB-11-53",
    ],
)

COMPLIANCE = RoleDefinition(
    name="compliance",
    prompt_supplement="""\
You are an authentication/compliance specialist. Focus on:
- SPF, DKIM, DMARC pass/fail rates and alignment
- ARC chain validity for forwarded mail
- Per-account compliance breakdowns (accountid from XMRID)
- Policy misconfigurations (p=none vs p=reject implications)
- Non-compliant senders on shared pools as a risk vector
Cross-reference compliance failures with bounce codes (550 5.7.x).""",
    grounding_queries=[
        "SPF DKIM DMARC authentication, ARC, BIMI, "
        "compliance failures, policy alignment, email authentication",
    ],
    grounding_kb_prefixes=[
        "KB-02", "KB-09-39",
    ],
)

ENGAGEMENT = RoleDefinition(
    name="engagement",
    prompt_supplement="""\
You are an engagement/list quality specialist. Focus on:
- Segment behavior differences (VH/H/M/L/VL/RO/NM/DS)
- List hygiene indicators: spam trap hits, complaint spikes, bounce patterns
- Sunset policy effectiveness (engagement recency vs deliverability)
- Zero-value field rates as data quality signals
- Cohort analysis: new subscribers vs long-dormant contacts
Compare engagement segment metrics against expected baselines.""",
    grounding_queries=[
        "engagement segments, list quality, spam traps, sunset policies, "
        "subscriber recency, complaint rates, list hygiene",
    ],
    grounding_kb_prefixes=[
        "KB-05", "KB-07-30", "KB-11-51", "KB-09-43", "KB-09-44",
    ],
)

ISP = RoleDefinition(
    name="isp",
    prompt_supplement="""\
You are an ISP/mailbox provider specialist. Focus on:
- Provider-specific filtering behaviors (Gmail, Microsoft, Yahoo/AOL, Apple)
- MX-based provider identification patterns
- Provider-specific bounce code interpretation
- Inbox vs spam placement signals per provider
- Rate limiting and throttling policies unique to each provider
Group findings by provider and compare delivery patterns across them.""",
    grounding_queries=[
        "Gmail Microsoft Yahoo Apple mailbox provider filtering, "
        "inbox placement, provider-specific bounce codes, rate limiting",
    ],
    grounding_kb_prefixes=[
        "KB-06", "KB-10", "KB-07-28", "KB-07-29", "KB-12-54",
    ],
)

DIAGNOSTICS = RoleDefinition(
    name="diagnostics",
    prompt_supplement="""\
You are a general diagnostics investigator. Focus on:
- Sudden deliverability drops: isolate timing, affected segments, and trigger events
- Gradual declines: identify trend inflection points and contributing factors
- Bounce log analysis: classify by SMTP response code categories
- Data completeness: zero-value fields, missing tracking data, pipeline gaps
- Cross-cutting issues that span multiple domains
Start broad, then narrow to the most impactful signal.""",
    grounding_queries=[
        "deliverability drop, bounce logs, SMTP response codes, "
        "data completeness, trend analysis, delivery lifecycle",
    ],
    grounding_kb_prefixes=[
        "KB-01", "KB-04", "KB-07-31", "KB-08", "KB-09-41",
        "KB-09-45", "KB-11-50", "KB-11-52",
    ],
)

ALL_ROLES = [REPUTATION, COMPLIANCE, ENGAGEMENT, ISP, DIAGNOSTICS]
