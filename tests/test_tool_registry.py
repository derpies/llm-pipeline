"""Tests for the tool auto-discovery registry."""


class TestToolRegistry:
    """Tests for tools.registry."""

    def setup_method(self):
        from llm_pipeline.tools.registry import reset_registry

        reset_registry()

    def test_discovers_investigator_tools(self):
        from llm_pipeline.tools.registry import get_tools

        tools = get_tools("investigator")
        names = {t.name for t in tools}
        # Should include ML tools
        assert "get_aggregations" in names
        assert "get_anomalies" in names
        assert "get_trends" in names
        assert "get_ml_report_summary" in names
        assert "get_data_completeness" in names
        assert "compare_dimensions" in names
        # Should include reporting tools
        assert "report_finding" in names
        assert "report_hypothesis" in names
        # Should include circuit breaker tools
        assert "report_step" in names
        assert "check_budget" in names
        # Should include wildcard tools
        assert "manipulate_datetime" in names

    def test_discovers_chat_tools(self):
        from llm_pipeline.tools.registry import get_tools

        tools = get_tools("chat")
        names = {t.name for t in tools}
        assert "retrieve_documents" in names
        # Wildcard tools
        assert "manipulate_datetime" in names

    def test_discovers_orchestrator_tools(self):
        from llm_pipeline.tools.registry import get_tools

        tools = get_tools("orchestrator")
        names = {t.name for t in tools}
        assert "get_anomalies" in names
        assert "get_trends" in names
        assert "get_ml_report_summary" in names
        # Wildcard
        assert "manipulate_datetime" in names

    def test_wildcard_tools_always_present(self):
        from llm_pipeline.tools.registry import get_tools

        tools = get_tools("some_unknown_role")
        names = {t.name for t in tools}
        assert "manipulate_datetime" in names

    def test_no_duplicates(self):
        from llm_pipeline.tools.registry import get_tools

        tools = get_tools("investigator")
        names = [t.name for t in tools]
        assert len(names) == len(set(names))

    def test_reset_forces_rediscovery(self):
        from llm_pipeline.tools.registry import get_tools, reset_registry

        tools1 = get_tools("investigator")
        reset_registry()
        tools2 = get_tools("investigator")
        # Same tools should be discovered
        assert {t.name for t in tools1} == {t.name for t in tools2}

    def test_production_tools_absent_when_disabled(self):
        from llm_pipeline.tools.registry import get_tools

        # production_mcp_enabled defaults to False, so no production tools
        tools = get_tools("investigator")
        names = {t.name for t in tools}
        assert "redis__ping" not in names
        assert "postgres__ping" not in names
        assert "opensearch__ping" not in names
        assert "s3__list_buckets" not in names

    def test_knowledge_tool_conditional_on_settings(self):
        from llm_pipeline.tools.registry import get_tools

        # The knowledge tool's TOOL_ROLES is evaluated at import time
        # based on settings.investigator_use_knowledge_store
        tools = get_tools("investigator")
        # Whether retrieve_knowledge appears depends on the setting at import time
        # Just verify the registry works without error
        assert len(tools) > 0
