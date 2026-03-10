"""Email delivery domain manifest — wires together all domain-specific content."""

from llm_pipeline.agents.contracts import DomainManifest
from llm_pipeline.domains.email_delivery.prompts import (
    INVESTIGATOR_DOMAIN_PROMPT,
    ORCHESTRATOR_ROLE_PROMPT,
)
from llm_pipeline.domains.email_delivery.report_builder import assemble_full_report
from llm_pipeline.domains.email_delivery.report_renderer import render_markdown
from llm_pipeline.domains.email_delivery.roles import ALL_ROLES

EMAIL_DELIVERY_DOMAIN = DomainManifest(
    name="email_delivery",
    description="Email delivery analytics — reputation, compliance, engagement, ISP, diagnostics",
    roles=ALL_ROLES,
    investigator_domain_prompt=INVESTIGATOR_DOMAIN_PROMPT,
    orchestrator_role_prompt=ORCHESTRATOR_ROLE_PROMPT,
    report_builder=assemble_full_report,
    report_renderer=render_markdown,
)
