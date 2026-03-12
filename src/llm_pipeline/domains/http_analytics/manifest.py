"""HTTP analytics domain manifest — wires together all domain-specific content."""

from llm_pipeline.agents.contracts import DomainManifest
from llm_pipeline.domains.http_analytics.prompts import (
    INVESTIGATOR_DOMAIN_PROMPT,
    ORCHESTRATOR_ROLE_PROMPT,
)
from llm_pipeline.domains.http_analytics.report_builder import assemble_full_report
from llm_pipeline.domains.http_analytics.report_renderer import render_markdown
from llm_pipeline.domains.http_analytics.roles import ALL_ROLES

HTTP_ANALYTICS_DOMAIN = DomainManifest(
    name="http_analytics",
    description="HTTP access log analytics — error rates, latency, security, traffic patterns",
    roles=ALL_ROLES,
    investigator_domain_prompt=INVESTIGATOR_DOMAIN_PROMPT,
    orchestrator_role_prompt=ORCHESTRATOR_ROLE_PROMPT,
    report_builder=assemble_full_report,
    report_renderer=render_markdown,
)
