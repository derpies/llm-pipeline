"""Tests for HTTP investigator tools — auto-discovery and signatures."""


class TestHttpToolDiscovery:
    def setup_method(self):
        from llm_pipeline.tools.registry import reset_registry

        reset_registry()

    def test_all_http_tools_discovered(self):
        from llm_pipeline.tools.registry import get_tools

        tools = get_tools("investigator")
        names = {t.name for t in tools}
        assert "get_http_aggregations" in names
        assert "get_http_anomalies" in names
        assert "get_http_trends" in names
        assert "get_http_report_summary" in names
        assert "get_http_data_completeness" in names
        assert "compare_http_dimensions" in names

    def test_reviewer_gets_http_tools(self):
        from llm_pipeline.tools.registry import get_tools

        tools = get_tools("reviewer")
        names = {t.name for t in tools}
        assert "get_http_aggregations" in names
        assert "get_http_anomalies" in names

    def test_orchestrator_gets_summary_tools(self):
        from llm_pipeline.tools.registry import get_tools

        tools = get_tools("orchestrator")
        names = {t.name for t in tools}
        assert "get_http_anomalies" in names
        assert "get_http_trends" in names
        assert "get_http_report_summary" in names
        # Aggregations and completeness are investigator/reviewer only
        assert "get_http_aggregations" not in names
        assert "get_http_data_completeness" not in names


class TestHttpToolSignatures:
    """Verify tool function signatures and metadata."""

    def test_get_http_aggregations_args(self):
        from llm_pipeline.tools.http import get_http_aggregations

        schema = get_http_aggregations.args_schema.model_json_schema()
        props = schema["properties"]
        assert "run_id" in props
        assert "dimension" in props
        assert "limit" in props

    def test_get_http_anomalies_args(self):
        from llm_pipeline.tools.http import get_http_anomalies

        schema = get_http_anomalies.args_schema.model_json_schema()
        props = schema["properties"]
        assert "run_id" in props
        assert "anomaly_type" in props
        assert "severity" in props

    def test_compare_http_dimensions_args(self):
        from llm_pipeline.tools.http import compare_http_dimensions

        schema = compare_http_dimensions.args_schema.model_json_schema()
        props = schema["properties"]
        assert "run_id" in props
        assert "dimension" in props
        assert "values" in props
        assert "metric" in props

    def test_http_tools_no_name_collision_with_email(self):
        """HTTP tools should not collide with email tool names."""
        from llm_pipeline.tools.registry import get_tools, reset_registry

        reset_registry()
        tools = get_tools("investigator")
        names = [t.name for t in tools]
        # No duplicates
        assert len(names) == len(set(names))
        # Both email and HTTP tools present
        assert "get_aggregations" in names  # email
        assert "get_http_aggregations" in names  # http


class TestToolRolesDeclaration:
    def test_tool_roles_format(self):
        from llm_pipeline.tools.http import TOOL_ROLES

        assert isinstance(TOOL_ROLES, list)
        assert len(TOOL_ROLES) == 6
        for fn, roles in TOOL_ROLES:
            assert hasattr(fn, "name"), f"{fn} must be a tool"
            assert isinstance(roles, list)
            assert all(isinstance(r, str) for r in roles)
