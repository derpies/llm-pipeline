"""Email delivery domain-specific prompt content.

These are injected into generic agent prompts via DomainManifest.
"""

# Appended to the orchestrator system prompt — describes available specialist roles
ORCHESTRATOR_ROLE_PROMPT = """\
- role: Which specialist to assign. One of:
  - "reputation" — IP/domain reputation, warming, blocklists, throttling, deferral patterns
  - "compliance" — SPF, DKIM, DMARC, authentication failures, policy violations
  - "engagement" — Segment behavior (VH/H/M/L), list quality, spam traps, complaint rates
  - "isp" — Provider-specific issues (Gmail, Microsoft, Yahoo, Apple filtering)
  - "diagnostics" — General-purpose: sudden drops, gradual declines, data quality, catch-all
  Choose the role that best matches the investigation topic. Default to "diagnostics" if unclear."""

# Appended to the investigator system prompt — email delivery domain knowledge
INVESTIGATOR_DOMAIN_PROMPT = """\
Key domain knowledge:
- listid is the primary grouping key (engagement segments: VH/H/M/L/VL/RO/NM/DS)
- Each engagement segment routes through mechanically isolated IP pools
- Pool reputation is segment-specific
- Zero-value fields mean "data unavailable", not zero
- Seasonal patterns need sufficient temporal coverage to validate"""
