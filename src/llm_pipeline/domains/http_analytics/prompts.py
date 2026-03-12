"""HTTP analytics domain-specific prompt content.

These are injected into generic agent prompts via DomainManifest.
"""

# Appended to the orchestrator system prompt — describes available specialist roles
ORCHESTRATOR_ROLE_PROMPT = """\
- role: Which specialist to assign. One of:
  - "error_analysis" — Status code patterns, 679 bugs, 4xx/5xx distribution, edge rejections
  - "latency" — TTS profiling, slow endpoints, upstream performance comparison
  - "security" — Bot detection, scanner classification, PHP probes, IP clustering
  - "traffic" — Throughput patterns, host distribution, load balancing, account-level volume
  Choose the role that best matches the investigation topic. Default to "error_analysis" if unclear."""

# Appended to the investigator system prompt — HTTP domain knowledge
INVESTIGATOR_DOMAIN_PROMPT = """\
Key domain knowledge:
- HTTP 679 is a custom status code meaning "known-valid content missing" — indicates a frontend/backend bug
- ~53% of traffic is PHP vulnerability probes (scanners hitting .php paths) — these generate expected 4xx errors
- ~40% of requests have empty user-agents — primarily bots and scanners
- Apple MPP (Mail Privacy Protection) generates ~4% of traffic — legitimate, not bot traffic
- Two upstream backends serve traffic; edge server rejects ~28% of requests without forwarding
- Tracking pixels (/o?) and click tracking (/c/) are email engagement-related but processed in the HTTP domain
- request_category classifies traffic: php_probe, tracking_pixel, click_tracking, page_load, static_asset, api_call
- host_category groups hosts: ontraport.com, ontralink.com, ontraport.net, custom_domain
- Time windows are minute-level (not hour-level like email) due to higher event density"""
