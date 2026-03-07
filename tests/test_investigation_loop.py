"""Tests for the Phase 2 investigation loop — structured findings, iteration, circuit breaker."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from llm_pipeline.agents.models import (
    CircuitBreakerBudget,
    Finding,
    FindingStatus,
    Hypothesis,
    InvestigationTopic,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_topic(**overrides) -> InvestigationTopic:
    defaults = {
        "title": "Test Topic",
        "dimension": "listid",
        "dimension_value": "VH",
        "metrics": ["delivery_rate"],
        "question": "Why is delivery dropping?",
        "priority": "high",
        "context": "Test context",
    }
    defaults.update(overrides)
    return InvestigationTopic(**defaults)


def _ai_msg_with_tool_calls(tool_calls: list[dict], content: str = "") -> AIMessage:
    """Create an AIMessage with tool_calls."""
    return AIMessage(content=content, tool_calls=tool_calls)


def _tool_msg(tool_call_id: str, content: str = "ok") -> ToolMessage:
    return ToolMessage(content=content, tool_call_id=tool_call_id)


# ---------------------------------------------------------------------------
# _extract_results tests
# ---------------------------------------------------------------------------

class TestExtractResults:
    """Tests for investigator._extract_results."""

    def test_parses_report_finding_tool_call(self):
        from llm_pipeline.agents.investigator import _extract_results

        msg = _ai_msg_with_tool_calls([{
            "id": "call_1",
            "name": "report_finding",
            "args": {
                "statement": "Delivery rate dropped 15% for VH segment",
                "status": "confirmed",
                "evidence": '["bounce rate 12% vs baseline 3%", "z-score 4.2"]',
                "metrics_cited": '{"delivery_rate": 0.85, "bounce_rate": 0.12}',
            },
        }])
        tool_resp = _tool_msg("call_1")

        state = {
            "topic": _make_topic(),
            "run_id": "run-001",
            "messages": [HumanMessage(content="brief"), msg, tool_resp],
            "findings": [],
            "hypotheses": [],
            "digest_lines": [],
            "prior_context": "",
        }

        result = _extract_results(state)
        assert len(result["findings"]) == 1
        f = result["findings"][0]
        assert f.status == FindingStatus.CONFIRMED
        assert f.statement == "Delivery rate dropped 15% for VH segment"
        assert len(f.evidence) == 2
        assert f.metrics_cited["delivery_rate"] == 0.85
        assert f.topic_title == "Test Topic"

    def test_parses_report_hypothesis_tool_call(self):
        from llm_pipeline.agents.investigator import _extract_results

        msg = _ai_msg_with_tool_calls([
            {
                "id": "call_1",
                "name": "report_finding",
                "args": {
                    "statement": "Something confirmed",
                    "status": "confirmed",
                },
            },
            {
                "id": "call_2",
                "name": "report_hypothesis",
                "args": {
                    "statement": "IP warmup may be causing dips",
                    "reasoning": "New IPs added to VH pool last week",
                },
            },
        ])
        tool_resp1 = _tool_msg("call_1")
        tool_resp2 = _tool_msg("call_2")

        state = {
            "topic": _make_topic(),
            "run_id": "run-001",
            "messages": [HumanMessage(content="brief"), msg, tool_resp1, tool_resp2],
            "findings": [],
            "hypotheses": [],
            "digest_lines": [],
            "prior_context": "",
        }

        result = _extract_results(state)
        assert len(result["findings"]) == 1
        assert len(result["hypotheses"]) == 1
        h = result["hypotheses"][0]
        assert h.statement == "IP warmup may be causing dips"
        assert h.reasoning == "New IPs added to VH pool last week"

    def test_fallback_inconclusive_when_no_reporting_tools(self):
        from llm_pipeline.agents.investigator import _extract_results

        state = {
            "topic": _make_topic(),
            "run_id": "run-001",
            "messages": [
                HumanMessage(content="brief"),
                AIMessage(content="I looked at the data but couldn't determine anything."),
            ],
            "findings": [],
            "hypotheses": [],
            "digest_lines": [],
            "prior_context": "",
        }

        result = _extract_results(state)
        assert len(result["findings"]) == 1
        assert result["findings"][0].status == FindingStatus.INCONCLUSIVE

    def test_handles_metrics_cited_as_dict(self):
        """When LLM passes metrics_cited as a dict instead of JSON string."""
        from llm_pipeline.agents.investigator import _extract_results

        msg = _ai_msg_with_tool_calls([{
            "id": "call_1",
            "name": "report_finding",
            "args": {
                "statement": "Test finding",
                "status": "confirmed",
                "evidence": ["evidence item"],
                "metrics_cited": {"rate": 0.95},
            },
        }])

        state = {
            "topic": _make_topic(),
            "run_id": "run-001",
            "messages": [HumanMessage(content="brief"), msg, _tool_msg("call_1")],
            "findings": [],
            "hypotheses": [],
            "digest_lines": [],
            "prior_context": "",
        }

        result = _extract_results(state)
        assert result["findings"][0].metrics_cited == {"rate": 0.95}

    def test_handles_invalid_status_string(self):
        from llm_pipeline.agents.investigator import _extract_results

        msg = _ai_msg_with_tool_calls([{
            "id": "call_1",
            "name": "report_finding",
            "args": {
                "statement": "Some finding",
                "status": "maybe",
            },
        }])

        state = {
            "topic": _make_topic(),
            "run_id": "run-001",
            "messages": [HumanMessage(content="brief"), msg, _tool_msg("call_1")],
            "findings": [],
            "hypotheses": [],
            "digest_lines": [],
            "prior_context": "",
        }

        result = _extract_results(state)
        assert result["findings"][0].status == FindingStatus.INCONCLUSIVE

    def test_digest_lines_contain_finding_and_hypothesis(self):
        from llm_pipeline.agents.investigator import _extract_results

        msg = _ai_msg_with_tool_calls([
            {
                "id": "call_1",
                "name": "report_finding",
                "args": {"statement": "F1", "status": "confirmed"},
            },
            {
                "id": "call_2",
                "name": "report_hypothesis",
                "args": {"statement": "H1", "reasoning": "R1"},
            },
        ])

        state = {
            "topic": _make_topic(),
            "run_id": "run-001",
            "messages": [msg, _tool_msg("call_1"), _tool_msg("call_2")],
            "findings": [],
            "hypotheses": [],
            "digest_lines": [],
            "prior_context": "",
        }

        result = _extract_results(state)
        assert any("[finding:confirmed]" in d for d in result["digest_lines"])
        assert any("[hypothesis]" in d for d in result["digest_lines"])


# ---------------------------------------------------------------------------
# _route_after_evaluate tests
# ---------------------------------------------------------------------------

class TestRouteAfterEvaluate:
    """Tests for graph._route_after_evaluate."""

    def test_returns_synthesize_when_plan_empty(self):
        from llm_pipeline.agents.graph import _route_after_evaluate

        state = {"investigation_plan": []}
        assert _route_after_evaluate(state) == "synthesize"

    def test_returns_synthesize_when_plan_missing(self):
        from llm_pipeline.agents.graph import _route_after_evaluate

        state = {}
        assert _route_after_evaluate(state) == "synthesize"

    def test_returns_send_list_when_topics_exist(self):
        from langgraph.types import Send

        from llm_pipeline.agents.graph import _route_after_evaluate

        topic = _make_topic(title="Follow-up")
        state = {
            "investigation_plan": [topic],
            "run_id": "run-001",
            "prior_findings": [
                Finding(
                    topic_title="Initial",
                    statement="Found something",
                    status=FindingStatus.CONFIRMED,
                    evidence=["ev1"],
                    created_at=datetime.now(UTC),
                    run_id="run-001",
                ),
            ],
            "prior_hypotheses": [],
        }

        result = _route_after_evaluate(state)
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], Send)
        assert result[0].node == "investigate_topic"
        # Prior context should be populated
        assert "Found something" in result[0].arg["prior_context"]

    def test_prior_context_empty_when_no_prior_findings(self):
        from llm_pipeline.agents.graph import _route_after_evaluate

        topic = _make_topic(title="Round 1")
        state = {
            "investigation_plan": [topic],
            "run_id": "run-001",
            "prior_findings": [],
            "prior_hypotheses": [],
        }

        result = _route_after_evaluate(state)
        assert isinstance(result, list)
        assert result[0].arg["prior_context"] == ""


# ---------------------------------------------------------------------------
# orchestrator_evaluate tests
# ---------------------------------------------------------------------------

class TestOrchestratorEvaluate:
    """Tests for orchestrator.orchestrator_evaluate."""

    def test_stops_when_budget_exceeded(self):
        from llm_pipeline.agents.orchestrator import orchestrator_evaluate

        state = {
            "findings": [
                Finding(
                    topic_title="T1",
                    statement="S1",
                    status=FindingStatus.INCONCLUSIVE,
                    created_at=datetime.now(UTC),
                ),
            ],
            "hypotheses": [],
            "iteration_count": 4,  # Will become 5, matching max_iterations=5
            "started_at": datetime.now(UTC),
            "budget": CircuitBreakerBudget(max_iterations=5, max_seconds=600),
        }

        result = orchestrator_evaluate(state)
        assert result["investigation_plan"] == []
        assert any("Budget exceeded" in d for d in result["digest_lines"])

    def test_stops_when_all_resolved(self):
        """No INCONCLUSIVE findings and no hypotheses → stop."""
        from llm_pipeline.agents.orchestrator import orchestrator_evaluate

        state = {
            "findings": [
                Finding(
                    topic_title="T1",
                    statement="S1",
                    status=FindingStatus.CONFIRMED,
                    created_at=datetime.now(UTC),
                ),
            ],
            "hypotheses": [],
            "iteration_count": 0,
            "started_at": datetime.now(UTC),
            "budget": CircuitBreakerBudget(max_iterations=5, max_seconds=600),
        }

        result = orchestrator_evaluate(state)
        assert result["investigation_plan"] == []
        assert any("All findings resolved" in d for d in result["digest_lines"])

    def test_calls_llm_for_follow_up_when_inconclusive(self):
        """When there are inconclusive findings, LLM is called for follow-up."""
        from llm_pipeline.agents.orchestrator import orchestrator_evaluate

        mock_response = AIMessage(content="[]")

        with patch("llm_pipeline.agents.orchestrator.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.invoke.return_value = mock_response
            mock_get_llm.return_value = mock_llm

            state = {
                "findings": [
                    Finding(
                        topic_title="T1",
                        statement="S1",
                        status=FindingStatus.INCONCLUSIVE,
                        created_at=datetime.now(UTC),
                    ),
                ],
                "hypotheses": [],
                "iteration_count": 0,
                "started_at": datetime.now(UTC),
                "budget": CircuitBreakerBudget(max_iterations=5, max_seconds=600),
            }

            result = orchestrator_evaluate(state)
            mock_llm.invoke.assert_called_once()
            assert result["investigation_plan"] == []


# ---------------------------------------------------------------------------
# orchestrator_checkpoint tests
# ---------------------------------------------------------------------------

class TestOrchestratorCheckpoint:
    """Tests for orchestrator.orchestrator_checkpoint."""

    def test_groups_findings_by_status(self):
        from llm_pipeline.agents.orchestrator import orchestrator_checkpoint

        now = datetime.now(UTC)
        state = {
            "run_id": "run-001",
            "iteration_count": 2,
            "findings": [
                Finding(
                    topic_title="T1", statement="Confirmed thing",
                    status=FindingStatus.CONFIRMED,
                    evidence=["ev1"], metrics_cited={"rate": 0.9},
                    created_at=now,
                ),
                Finding(
                    topic_title="T2", statement="Disproven thing",
                    status=FindingStatus.DISPROVEN,
                    created_at=now,
                ),
                Finding(
                    topic_title="T3", statement="Inconclusive thing",
                    status=FindingStatus.INCONCLUSIVE,
                    created_at=now,
                ),
            ],
            "hypotheses": [
                Hypothesis(
                    topic_title="T1", statement="Maybe X",
                    reasoning="Because Y", created_at=now,
                ),
            ],
            "digest_lines": ["[plan] Created 2 topics", "[eval] Iteration 1"],
        }

        result = orchestrator_checkpoint(state)
        digest = result["checkpoint_digest"]

        assert "CONFIRMED" in digest
        assert "DISPROVEN" in digest
        assert "INCONCLUSIVE" in digest
        assert "Confirmed thing" in digest
        assert "Disproven thing" in digest
        assert "ev1" in digest
        assert "rate=0.9" in digest
        assert "Maybe X" in digest
        assert "Because Y" in digest
        assert "Iterations: 2" in digest


# ---------------------------------------------------------------------------
# Integration: full loop with mocked LLM
# ---------------------------------------------------------------------------

class TestInvestigationLoopIntegration:
    """Integration tests for the full investigation cycle graph."""

    def _make_mock_report(self):
        """Create a minimal AnalysisReport for testing."""
        from llm_pipeline.email_analytics.models import (
            AnalysisReport,
            AnomalyFinding,
            AnomalyType,
        )

        return AnalysisReport(
            run_id="test-run",
            started_at=datetime.now(UTC),
            events_parsed=1000,
            anomalies=[
                AnomalyFinding(
                    anomaly_type=AnomalyType.RATE_DROP,
                    dimension="listid",
                    dimension_value="VH",
                    metric="delivery_rate",
                    current_value=0.85,
                    baseline_mean=0.95,
                    z_score=3.5,
                    severity="high",
                ),
            ],
        )

    def test_full_loop_single_iteration(self):
        """Full graph: plan → investigate → evaluate → synthesize → checkpoint."""
        from llm_pipeline.agents.graph import build_investigation_graph

        # Mock the orchestrator plan LLM to return one topic
        plan_response = AIMessage(content='[{"title": "VH delivery drop", '
            '"dimension": "listid", "dimension_value": "VH", '
            '"metrics": ["delivery_rate"], "question": "Why is delivery dropping?", '
            '"priority": "high", "context": "z=3.5"}]')

        # Mock the investigator LLM: first call returns a report_finding tool call,
        # second call returns final text (no more tool calls)
        investigator_first = _ai_msg_with_tool_calls([{
            "id": "call_1",
            "name": "report_finding",
            "args": {
                "statement": "VH delivery rate dropped due to bounce spike",
                "status": "confirmed",
                "evidence": '["bounce rate 12%"]',
                "metrics_cited": '{"delivery_rate": 0.85}',
            },
        }])
        investigator_final = AIMessage(content="Investigation complete.")

        # Mock the orchestrator evaluate LLM to return no follow-ups
        eval_response = AIMessage(content="[]")

        call_counter = {"plan": 0, "investigator": 0, "eval": 0}

        def mock_llm_factory(role=None, **kwargs):
            mock = MagicMock()

            if role == "orchestrator":
                def invoke_side_effect(messages, **kw):
                    # Distinguish plan vs evaluate by looking at message content
                    content = messages[-1].content if messages else ""
                    if "create investigation topics" in content.lower():
                        call_counter["plan"] += 1
                        return plan_response
                    else:
                        call_counter["eval"] += 1
                        return eval_response
                mock.invoke.side_effect = invoke_side_effect
            else:
                # Investigator mock
                def inv_invoke(messages, **kw):
                    call_counter["investigator"] += 1
                    if call_counter["investigator"] == 1:
                        return investigator_first
                    return investigator_final
                mock.bind_tools.return_value = mock
                mock.invoke.side_effect = inv_invoke

            return mock

        with patch("llm_pipeline.agents.orchestrator.get_llm", side_effect=mock_llm_factory):
            with patch("llm_pipeline.agents.investigator.get_llm", side_effect=mock_llm_factory):
                graph = build_investigation_graph()
                result = graph.invoke({
                    "ml_report": self._make_mock_report(),
                    "run_id": "test-run",
                })

        assert result["iteration_count"] >= 1
        assert len(result["findings"]) >= 1
        assert result["findings"][0].status == FindingStatus.CONFIRMED
        assert "checkpoint_digest" in result
        assert "CONFIRMED" in result["checkpoint_digest"]

    def test_circuit_breaker_stops_iteration(self):
        """Circuit breaker stops the loop even when LLM wants more investigation."""
        from llm_pipeline.agents.graph import build_investigation_graph

        plan_response = AIMessage(content='[{"title": "Test topic", '
            '"dimension": "listid", "dimension_value": "VH", '
            '"metrics": ["delivery_rate"], "question": "Why?", '
            '"priority": "high", "context": "test"}]')

        investigator_finding = _ai_msg_with_tool_calls([{
            "id": "call_1",
            "name": "report_finding",
            "args": {
                "statement": "Inconclusive result",
                "status": "inconclusive",
            },
        }])
        investigator_final = AIMessage(content="Done.")

        # Eval LLM always wants follow-up — but circuit breaker should stop it
        follow_up_response = AIMessage(content='[{"title": "Follow up", '
            '"dimension": "listid", "dimension_value": "VH", '
            '"metrics": ["delivery_rate"], "question": "Dig deeper", '
            '"priority": "high", "context": "follow up"}]')

        inv_call_count = {"count": 0}

        def mock_llm_factory(role=None, **kwargs):
            mock = MagicMock()

            if role == "orchestrator":
                def invoke_side_effect(messages, **kw):
                    content = messages[-1].content if messages else ""
                    if "create investigation topics" in content.lower():
                        return plan_response
                    else:
                        return follow_up_response
                mock.invoke.side_effect = invoke_side_effect
            else:
                def inv_invoke(messages, **kw):
                    inv_call_count["count"] += 1
                    # Alternate: tool call then final
                    if inv_call_count["count"] % 2 == 1:
                        return investigator_finding
                    return investigator_final
                mock.bind_tools.return_value = mock
                mock.invoke.side_effect = inv_invoke

            return mock

        with patch("llm_pipeline.agents.orchestrator.get_llm", side_effect=mock_llm_factory):
            with patch("llm_pipeline.agents.investigator.get_llm", side_effect=mock_llm_factory):
                with patch("llm_pipeline.agents.orchestrator.settings") as mock_settings:
                    mock_settings.circuit_breaker_max_iterations = 2
                    mock_settings.circuit_breaker_max_seconds = 600

                    graph = build_investigation_graph()
                    result = graph.invoke({
                        "ml_report": self._make_mock_report(),
                        "run_id": "test-run",
                    })

        # Should have stopped at 2 iterations
        assert result["iteration_count"] <= 2
        assert any("Budget exceeded" in d for d in result["digest_lines"])
        assert "checkpoint_digest" in result


# ---------------------------------------------------------------------------
# _build_prior_context tests
# ---------------------------------------------------------------------------

class TestBuildPriorContext:
    """Tests for graph._build_prior_context."""

    def test_empty_when_no_findings(self):
        from llm_pipeline.agents.graph import _build_prior_context

        assert _build_prior_context({"prior_findings": [], "prior_hypotheses": []}) == ""

    def test_includes_findings_and_hypotheses(self):
        from llm_pipeline.agents.graph import _build_prior_context

        now = datetime.now(UTC)
        state = {
            "prior_findings": [
                Finding(
                    topic_title="T1", statement="Found X",
                    status=FindingStatus.CONFIRMED,
                    evidence=["ev1"], created_at=now,
                ),
            ],
            "prior_hypotheses": [
                Hypothesis(
                    topic_title="T1", statement="Maybe Y",
                    reasoning="Because Z", created_at=now,
                ),
            ],
        }

        ctx = _build_prior_context(state)
        assert "Found X" in ctx
        assert "confirmed" in ctx
        assert "ev1" in ctx
        assert "Maybe Y" in ctx
        assert "Because Z" in ctx


# ---------------------------------------------------------------------------
# Investigator tool list toggle tests
# ---------------------------------------------------------------------------

class TestInvestigatorToolToggle:
    """Tests for dynamic investigator tool list based on config."""

    def test_knowledge_tool_included_when_enabled(self):
        from llm_pipeline.agents.investigator import _get_investigator_tools

        with patch("llm_pipeline.agents.investigator.settings") as mock_settings:
            mock_settings.investigator_use_knowledge_store = True
            tools = _get_investigator_tools()
            tool_names = [t.name for t in tools]
            assert "retrieve_knowledge" in tool_names

    def test_knowledge_tool_excluded_when_disabled(self):
        from llm_pipeline.agents.investigator import _get_investigator_tools

        with patch("llm_pipeline.agents.investigator.settings") as mock_settings:
            mock_settings.investigator_use_knowledge_store = False
            tools = _get_investigator_tools()
            tool_names = [t.name for t in tools]
            assert "retrieve_knowledge" not in tool_names

    def test_base_tools_always_present(self):
        from llm_pipeline.agents.investigator import INVESTIGATOR_BASE_TOOLS, _get_investigator_tools

        with patch("llm_pipeline.agents.investigator.settings") as mock_settings:
            mock_settings.investigator_use_knowledge_store = False
            tools = _get_investigator_tools()
            # All base tools should be present
            base_names = {t.name for t in INVESTIGATOR_BASE_TOOLS}
            tool_names = {t.name for t in tools}
            assert base_names <= tool_names
