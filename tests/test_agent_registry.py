"""Tests for the agent auto-discovery registry."""

from llm_pipeline.agents.contracts import AgentManifest


class TestAgentRegistry:
    """Tests for agents.registry."""

    def setup_method(self):
        from llm_pipeline.agents.registry import reset_registry

        reset_registry()

    def test_discovers_investigator_agent(self):
        from llm_pipeline.agents.registry import get_agent

        manifest = get_agent("investigator")
        assert manifest is not None
        assert manifest.name == "investigator"
        assert manifest.agent_type == "investigation"
        assert manifest.tool_role == "investigator"

    def test_investigator_has_result_adapter(self):
        from llm_pipeline.agents.registry import get_agent

        manifest = get_agent("investigator")
        assert manifest is not None
        assert manifest.result_adapter is not None

    def test_investigator_build_graph_callable(self):
        from llm_pipeline.agents.registry import get_agent

        manifest = get_agent("investigator")
        assert manifest is not None
        assert callable(manifest.build_graph)

    def test_get_investigation_agents(self):
        from llm_pipeline.agents.registry import get_investigation_agents

        agents = get_investigation_agents()
        assert "investigator" in agents
        assert agents["investigator"].agent_type == "investigation"

    def test_get_pipeline_agents_empty(self):
        """No pipeline agents registered by default."""
        from llm_pipeline.agents.registry import get_pipeline_agents

        agents = get_pipeline_agents()
        # Currently no pipeline agents
        assert isinstance(agents, dict)

    def test_list_agents_includes_investigator(self):
        from llm_pipeline.agents.registry import list_agents

        agents = list_agents()
        assert "investigator" in agents

    def test_get_nonexistent_agent(self):
        from llm_pipeline.agents.registry import get_agent

        assert get_agent("nonexistent") is None

    def test_reset_forces_rediscovery(self):
        from llm_pipeline.agents.registry import get_agent, reset_registry

        m1 = get_agent("investigator")
        reset_registry()
        m2 = get_agent("investigator")
        assert m1 is not None
        assert m2 is not None
        assert m1.name == m2.name

    def test_result_adapter_adapt(self):
        from llm_pipeline.agents.registry import get_agent

        manifest = get_agent("investigator")
        assert manifest is not None
        assert manifest.result_adapter is not None

        output = manifest.result_adapter.adapt({
            "findings": ["f1"],
            "hypotheses": ["h1"],
            "digest_lines": ["d1"],
            "completed_topics": ["t1"],
            "topic_errors": ["e1"],
        })
        assert output["findings"] == ["f1"]
        assert output["hypotheses"] == ["h1"]
        assert output["digest_lines"] == ["d1"]
        assert output["completed_topics"] == ["t1"]
        assert output["topic_errors"] == ["e1"]

    def test_result_adapter_handles_missing_keys(self):
        from llm_pipeline.agents.registry import get_agent

        manifest = get_agent("investigator")
        assert manifest is not None
        assert manifest.result_adapter is not None

        output = manifest.result_adapter.adapt({})
        assert output["findings"] == []
        assert output["hypotheses"] == []


class TestAgentManifest:
    """Tests for the AgentManifest dataclass."""

    def test_creates_with_required_fields(self):
        m = AgentManifest(
            name="test",
            agent_type="investigation",
            tool_role="test_role",
            build_graph=lambda: None,
            state_class=dict,
        )
        assert m.name == "test"
        assert m.result_adapter is None
        assert m.cli_command is None
