"""Tests for multi-domain support — both email and HTTP domains coexisting."""

from llm_pipeline.agents.domain_registry import (
    get_active_domain,
    get_all_domains,
    get_domain,
)


class TestMultiDomain:
    def test_both_domains_discovered(self):
        domains = get_all_domains()
        assert "email_delivery" in domains
        assert "http_analytics" in domains

    def test_get_domain_by_name(self):
        domain = get_domain("http_analytics")
        assert domain is not None
        assert domain.name == "http_analytics"

    def test_get_domain_email(self):
        domain = get_domain("email_delivery")
        assert domain is not None
        assert domain.name == "email_delivery"

    def test_get_domain_nonexistent(self):
        domain = get_domain("nonexistent_domain")
        assert domain is None

    def test_get_active_domain_with_name(self):
        domain = get_active_domain(domain_name="http_analytics")
        assert domain is not None
        assert domain.name == "http_analytics"

    def test_get_active_domain_default(self):
        """get_active_domain with no name returns the first discovered domain."""
        domain = get_active_domain()
        assert domain is not None
        assert domain.name in ("email_delivery", "http_analytics")

    def test_domains_have_distinct_roles(self):
        email = get_domain("email_delivery")
        http = get_domain("http_analytics")
        email_roles = {r.name for r in email.roles}
        http_roles = {r.name for r in http.roles}
        # Roles should be different between domains
        assert email_roles != http_roles

    def test_domain_prompts_are_distinct(self):
        email = get_domain("email_delivery")
        http = get_domain("http_analytics")
        assert email.investigator_domain_prompt != http.investigator_domain_prompt
        assert email.orchestrator_role_prompt != http.orchestrator_role_prompt
