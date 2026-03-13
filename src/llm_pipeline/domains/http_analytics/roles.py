"""HTTP analytics specialist investigator role definitions.

Defines per-role prompt supplements and grounding queries
for the HTTP analytics domain.
"""

from __future__ import annotations

from llm_pipeline.agents.contracts import RoleDefinition

# ---------------------------------------------------------------------------
# Role definitions
# ---------------------------------------------------------------------------

ERROR_ANALYSIS = RoleDefinition(
    name="error_analysis",
    prompt_supplement="""\
You are an HTTP error analysis specialist. Focus on:
- Status code distribution patterns (4xx vs 5xx vs 679)
- Status 679 is a custom code meaning "known-valid content missing" — a bug indicator
- Edge rejection rates (requests handled at edge without reaching upstream)
- Per-host and per-request-category error breakdowns
- Correlation between error rates and specific upstreams or request paths
- PHP probe traffic (expect ~50% 4xx — this is normal scanner noise, not a bug)
Distinguish between expected errors (scanners hitting invalid paths) and unexpected errors (legitimate requests failing).""",
    grounding_queries=[
        "HTTP status codes, error rates, 4xx 5xx patterns, "
        "edge rejection, upstream errors, content availability",
    ],
    grounding_kb_prefixes=["KB-HTTP-03", "KB-HTTP-07"],
)

LATENCY = RoleDefinition(
    name="latency",
    prompt_supplement="""\
You are an HTTP latency specialist. Focus on:
- TTS (time to serve) distribution: p50, p90, p95, p99, max
- Latency by upstream backend (compare the two upstream backends)
- Latency by request category (tracking pixels should be fast, page loads slower)
- Latency outliers and spikes — identify affected hosts and paths
- WebSocket connections may show anomalous TTS — filter or flag separately
- Edge-only responses (no upstream) typically have very low TTS
Compare latency patterns across hosts, request categories, and time windows.""",
    grounding_queries=[
        "HTTP latency, time to serve, response time, "
        "upstream performance, backend latency, p95 p99",
    ],
    grounding_kb_prefixes=["KB-HTTP-01", "KB-HTTP-02"],
)

SECURITY = RoleDefinition(
    name="security",
    prompt_supplement="""\
You are an HTTP security and bot detection specialist. Focus on:
- PHP probe patterns: ~53% of traffic is vulnerability scanning (.php requests)
- Empty user-agent requests: ~40% of traffic — likely bots/scanners
- Scanner fingerprints (zgrab, masscan, nikto, etc.) in user-agent strings
- IP clustering: are scans from a small number of IPs or distributed?
- Apple MPP (Mail Privacy Protection) traffic — legitimate, not a threat
- Bot vs real browser ratio across hosts and time windows
- Unusual request paths that indicate automated probing
Categorize threats by severity: active scanners > passive bots > legitimate automated traffic.""",
    grounding_queries=[
        "HTTP bot detection, vulnerability scanning, PHP probes, "
        "scanner fingerprints, empty user-agent, security threats",
    ],
    grounding_kb_prefixes=["KB-HTTP-05", "KB-HTTP-06", "KB-HTTP-07"],
)

TRAFFIC = RoleDefinition(
    name="traffic",
    prompt_supplement="""\
You are an HTTP traffic analysis specialist. Focus on:
- Throughput patterns: requests/minute across time windows
- Traffic distribution by host, request category, and upstream
- Host category breakdown: ontraport.com vs ontralink.com vs custom domains
- Load balancing between upstream backends (172.26.x.x)
- Account-level traffic volume (when accountid is present)
- Traffic spikes or drops that correlate with specific events
- Edge rejection ratio: what percentage of requests never reach upstream?
Look for capacity signals: are any hosts or upstreams approaching limits?""",
    grounding_queries=[
        "HTTP traffic analysis, throughput, load balancing, "
        "request volume, capacity planning, traffic distribution",
    ],
    grounding_kb_prefixes=["KB-HTTP-04", "KB-HTTP-05", "KB-HTTP-01"],
)

ALL_ROLES = [ERROR_ANALYSIS, LATENCY, SECURITY, TRAFFIC]
