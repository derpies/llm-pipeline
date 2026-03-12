"""Tests for the HTTP analytics domain plugin — manifest, roles, prompts."""

from llm_pipeline.agents.contracts import DomainManifest
from llm_pipeline.agents.domain_registry import get_all_domains


class TestHttpDomainManifest:
    def test_manifest_loads(self):
        from llm_pipeline.domains.http_analytics.manifest import HTTP_ANALYTICS_DOMAIN

        assert isinstance(HTTP_ANALYTICS_DOMAIN, DomainManifest)
        assert HTTP_ANALYTICS_DOMAIN.name == "http_analytics"

    def test_manifest_has_roles(self):
        from llm_pipeline.domains.http_analytics.manifest import HTTP_ANALYTICS_DOMAIN

        assert len(HTTP_ANALYTICS_DOMAIN.roles) == 4
        role_names = {r.name for r in HTTP_ANALYTICS_DOMAIN.roles}
        assert "error_analysis" in role_names
        assert "latency" in role_names
        assert "security" in role_names
        assert "traffic" in role_names

    def test_manifest_has_prompts(self):
        from llm_pipeline.domains.http_analytics.manifest import HTTP_ANALYTICS_DOMAIN

        assert HTTP_ANALYTICS_DOMAIN.investigator_domain_prompt
        assert HTTP_ANALYTICS_DOMAIN.orchestrator_role_prompt
        assert "679" in HTTP_ANALYTICS_DOMAIN.investigator_domain_prompt

    def test_manifest_has_report_builder(self):
        from llm_pipeline.domains.http_analytics.manifest import HTTP_ANALYTICS_DOMAIN

        assert callable(HTTP_ANALYTICS_DOMAIN.report_builder)
        assert callable(HTTP_ANALYTICS_DOMAIN.report_renderer)


class TestDomainDiscovery:
    def test_http_analytics_discovered(self):
        domains = get_all_domains()
        assert "http_analytics" in domains
        assert "email_delivery" in domains

    def test_both_domains_have_roles(self):
        domains = get_all_domains()
        for name, domain in domains.items():
            assert len(domain.roles) > 0, f"{name} has no roles"


class TestHttpRoles:
    def test_role_prompt_supplements(self):
        from llm_pipeline.domains.http_analytics.roles import ALL_ROLES

        for role in ALL_ROLES:
            assert role.name, "Role must have a name"
            assert role.prompt_supplement, f"Role {role.name} must have a prompt_supplement"

    def test_role_names_unique(self):
        from llm_pipeline.domains.http_analytics.roles import ALL_ROLES

        names = [r.name for r in ALL_ROLES]
        assert len(names) == len(set(names))
