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
        "role": "diagnostics",
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
            "grounding_context": "",
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
            "grounding_context": "",
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
            "grounding_context": "",
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
            "grounding_context": "",
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
            "grounding_context": "",
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
            "grounding_context": "",
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
        assert _route_after_evaluate(state) == "assemble_report"

    def test_returns_synthesize_when_plan_missing(self):
        from llm_pipeline.agents.graph import _route_after_evaluate

        state = {}
        assert _route_after_evaluate(state) == "assemble_report"

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
        assert result[0].node == "investigate_investigator"
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
        """Full graph: plan → investigate → review → evaluate → assemble → synthesize → checkpoint."""
        import json

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

        # Mock the reviewer LLM
        reviewer_response = AIMessage(content=json.dumps([{
            "finding_index": 0,
            "finding_statement": "VH delivery rate dropped due to bounce spike",
            "assessment": "supported",
            "reasoning": "Evidence is consistent",
            "suggested_action": "accept",
        }]))

        # Mock the synthesizer LLM
        synthesizer_response = AIMessage(content=json.dumps({
            "executive_summary": "VH segment experienced a delivery drop.",
            "observations": [
                {"section": "next_cycle_focus", "note": "Monitor bounce rates."},
            ],
        }))

        call_counter = {"plan": 0, "investigator": 0, "eval": 0}

        def mock_llm_factory(role=None, **kwargs):
            mock = MagicMock()

            if role == "orchestrator":
                def invoke_side_effect(messages, **kw):
                    content = messages[-1].content if messages else ""
                    if "create investigation topics" in content.lower():
                        call_counter["plan"] += 1
                        return plan_response
                    else:
                        call_counter["eval"] += 1
                        return eval_response
                mock.invoke.side_effect = invoke_side_effect
            elif role == "reviewer":
                mock.bind_tools.return_value = mock
                mock.invoke.return_value = reviewer_response
            elif role == "synthesizer":
                mock.invoke.return_value = synthesizer_response
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

        inv_patch = "llm_pipeline.agents.plugins.investigator.agent.get_llm"
        rev_patch = "llm_pipeline.agents.reviewer.get_llm"
        syn_patch = "llm_pipeline.agents.synthesizer.get_llm"
        with patch("llm_pipeline.agents.orchestrator.get_llm", side_effect=mock_llm_factory):
            with patch(inv_patch, side_effect=mock_llm_factory):
                with patch(rev_patch, side_effect=mock_llm_factory):
                    with patch(syn_patch, side_effect=mock_llm_factory):
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
        # Verify reviewer annotations present
        assert len(result.get("review_annotations", [])) >= 1
        # Verify synthesis narrative present
        assert result.get("synthesis_narrative", "")

    def test_assemble_report_produces_report(self):
        """Assemble_report node produces a report key in state with segment health."""
        from llm_pipeline.agents.graph import _assemble_report
        from llm_pipeline.email_analytics.models import AggregationBucket

        now = datetime.now(UTC)
        report = self._make_mock_report()
        # Add engagement_segment aggregations so segment_health is populated
        report.aggregations = [
            AggregationBucket(
                time_window=now, dimension="engagement_segment",
                dimension_value="VH", total=100, delivered=95,
                bounced=3, deferred=2, complained=0,
                delivery_rate=0.95, bounce_rate=0.03,
                deferral_rate=0.02, complaint_rate=0.0,
            ),
        ]

        state = {
            "ml_report": report,
            "run_id": "test-run",
            "findings": [
                Finding(
                    topic_title="T1",
                    statement="Confirmed thing",
                    status=FindingStatus.CONFIRMED,
                    evidence=["ev1"],
                    created_at=now,
                ),
            ],
            "hypotheses": [
                Hypothesis(
                    topic_title="T1", statement="Maybe X",
                    reasoning="Because Y", created_at=now,
                ),
            ],
            "digest_lines": ["[plan] Created 1 topic"],
        }

        result = _assemble_report(state)
        assert "report" in result
        inv_report = result["report"]
        assert len(inv_report.structured.segment_health) == 1
        assert inv_report.structured.segment_health[0].segment == "VH"
        assert len(inv_report.structured.confirmed_issues) == 1
        assert len(inv_report.notes.hypotheses) == 1

    def test_circuit_breaker_stops_iteration(self):
        """Circuit breaker stops the loop even when LLM wants more investigation."""
        import json

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

        reviewer_response = AIMessage(content=json.dumps([{
            "finding_index": 0,
            "finding_statement": "Inconclusive result",
            "assessment": "weak_evidence",
            "reasoning": "Needs more data",
            "suggested_action": "investigate_further",
            "follow_up_question": "Check more dimensions",
        }]))

        synthesizer_response = AIMessage(content=json.dumps({
            "executive_summary": "Investigation was halted by circuit breaker.",
            "observations": [],
        }))

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
            elif role == "reviewer":
                mock.bind_tools.return_value = mock
                mock.invoke.return_value = reviewer_response
            elif role == "synthesizer":
                mock.invoke.return_value = synthesizer_response
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

        inv_patch = "llm_pipeline.agents.plugins.investigator.agent.get_llm"
        rev_patch = "llm_pipeline.agents.reviewer.get_llm"
        syn_patch = "llm_pipeline.agents.synthesizer.get_llm"
        with patch("llm_pipeline.agents.orchestrator.get_llm", side_effect=mock_llm_factory):
            with patch(inv_patch, side_effect=mock_llm_factory):
                with patch(rev_patch, side_effect=mock_llm_factory):
                    with patch(syn_patch, side_effect=mock_llm_factory):
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
    """Tests for dynamic investigator tool list via tool registry.

    Note: The knowledge tool's inclusion is determined by TOOL_ROLES in
    knowledge.py, evaluated at import time based on settings. These tests
    verify the registry-based approach works correctly.
    """

    def test_registry_returns_investigator_tools(self):
        from llm_pipeline.tools.registry import get_tools, reset_registry

        reset_registry()
        tools = get_tools("investigator")
        tool_names = [t.name for t in tools]
        # Core ML tools should always be present
        assert "get_aggregations" in tool_names
        assert "report_finding" in tool_names

    def test_knowledge_tool_conditional_via_registry(self):
        """Knowledge tool inclusion depends on settings at import time."""
        from llm_pipeline.tools.registry import get_tools, reset_registry

        reset_registry()
        tools = get_tools("investigator")
        # Whether retrieve_knowledge appears depends on the current setting
        # Just verify the registry works without error
        assert len(tools) > 0

    def test_base_tools_always_present(self):
        from llm_pipeline.tools.registry import get_tools, reset_registry

        reset_registry()
        tools = get_tools("investigator")
        tool_names = {t.name for t in tools}
        # Core investigator tools from multiple modules
        expected = {
            "get_aggregations", "get_anomalies", "get_trends",
            "get_ml_report_summary", "get_data_completeness", "compare_dimensions",
            "report_finding", "report_hypothesis",
            "report_step", "check_budget",
            "get_current_datetime",  # wildcard
        }
        assert expected <= tool_names


# ---------------------------------------------------------------------------
# _count_consecutive_non_ok tests
# ---------------------------------------------------------------------------

class TestCountConsecutiveNonOk:
    """Tests for investigator._count_consecutive_non_ok."""

    def test_counts_consecutive_empty_results(self):
        from llm_pipeline.agents.investigator import _count_consecutive_non_ok

        messages = [
            HumanMessage(content="brief"),
            AIMessage(content="", tool_calls=[{"id": "c1", "name": "t", "args": {}}]),
            _tool_msg("c1", "[EMPTY] No data found"),
            AIMessage(content="", tool_calls=[{"id": "c2", "name": "t", "args": {}}]),
            _tool_msg("c2", "[EMPTY] No anomalies found"),
        ]
        assert _count_consecutive_non_ok(messages) == 1

    def test_counts_consecutive_error_results(self):
        from llm_pipeline.agents.investigator import _count_consecutive_non_ok

        messages = [
            AIMessage(content="", tool_calls=[
                {"id": "c1", "name": "t", "args": {}},
                {"id": "c2", "name": "t", "args": {}},
            ]),
            _tool_msg("c1", "[ERROR] Invalid metric"),
            _tool_msg("c2", "[ERROR] Missing parameter"),
        ]
        assert _count_consecutive_non_ok(messages) == 2

    def test_mixed_empty_and_error(self):
        from llm_pipeline.agents.investigator import _count_consecutive_non_ok

        messages = [
            AIMessage(content="", tool_calls=[
                {"id": "c1", "name": "t", "args": {}},
                {"id": "c2", "name": "t", "args": {}},
            ]),
            _tool_msg("c1", "[EMPTY] No data"),
            _tool_msg("c2", "[ERROR] Bad param"),
        ]
        assert _count_consecutive_non_ok(messages) == 2

    def test_ok_breaks_the_streak(self):
        from llm_pipeline.agents.investigator import _count_consecutive_non_ok

        messages = [
            AIMessage(content="", tool_calls=[
                {"id": "c1", "name": "t", "args": {}},
                {"id": "c2", "name": "t", "args": {}},
                {"id": "c3", "name": "t", "args": {}},
            ]),
            _tool_msg("c1", "[EMPTY] No data"),
            _tool_msg("c2", "[OK] {\"result\": 1}"),
            _tool_msg("c3", "[EMPTY] No data"),
        ]
        # Only the last one counts — c2 (OK) breaks the streak
        assert _count_consecutive_non_ok(messages) == 1

    def test_unprefixed_messages_treated_as_ok(self):
        from llm_pipeline.agents.investigator import _count_consecutive_non_ok

        messages = [
            AIMessage(content="", tool_calls=[
                {"id": "c1", "name": "t", "args": {}},
                {"id": "c2", "name": "t", "args": {}},
            ]),
            _tool_msg("c1", "ok"),  # no prefix — backward compat
            _tool_msg("c2", "[EMPTY] No data"),
        ]
        # Only c2 counts; c1 (unprefixed) treated as OK, breaks the streak
        assert _count_consecutive_non_ok(messages) == 1

    def test_zero_when_all_ok(self):
        from llm_pipeline.agents.investigator import _count_consecutive_non_ok

        messages = [
            AIMessage(content="", tool_calls=[
                {"id": "c1", "name": "t", "args": {}},
            ]),
            _tool_msg("c1", "[OK] Some data"),
        ]
        assert _count_consecutive_non_ok(messages) == 0

    def test_zero_when_no_tool_messages(self):
        from llm_pipeline.agents.investigator import _count_consecutive_non_ok

        messages = [
            HumanMessage(content="brief"),
            AIMessage(content="thinking..."),
        ]
        assert _count_consecutive_non_ok(messages) == 0


# ---------------------------------------------------------------------------
# _extract_results tool_errors digest tests
# ---------------------------------------------------------------------------

class TestExtractResultsToolErrors:
    """Tests for tool_errors digest line in _extract_results."""

    def test_digest_includes_tool_errors_count(self):
        from llm_pipeline.agents.investigator import _extract_results

        msg = _ai_msg_with_tool_calls([
            {
                "id": "call_1",
                "name": "get_aggregations",
                "args": {"run_id": "r1"},
            },
            {
                "id": "call_2",
                "name": "report_finding",
                "args": {"statement": "Found it", "status": "confirmed"},
            },
        ])

        state = {
            "topic": _make_topic(),
            "run_id": "run-001",
            "messages": [
                HumanMessage(content="brief"),
                msg,
                _tool_msg("call_1", "[EMPTY] No aggregation data found"),
                _tool_msg("call_2", "[OK] Finding recorded"),
            ],
            "findings": [],
            "hypotheses": [],
            "digest_lines": [],
            "prior_context": "",
            "grounding_context": "",
        }

        result = _extract_results(state)
        assert any("[tool_errors]" in d for d in result["digest_lines"])
        assert any("1 tool calls returned EMPTY/ERROR" in d for d in result["digest_lines"])

    def test_no_tool_errors_digest_when_all_ok(self):
        from llm_pipeline.agents.investigator import _extract_results

        msg = _ai_msg_with_tool_calls([
            {
                "id": "call_1",
                "name": "report_finding",
                "args": {"statement": "Found it", "status": "confirmed"},
            },
        ])

        state = {
            "topic": _make_topic(),
            "run_id": "run-001",
            "messages": [
                HumanMessage(content="brief"),
                msg,
                _tool_msg("call_1", "[OK] Finding recorded"),
            ],
            "findings": [],
            "hypotheses": [],
            "digest_lines": [],
            "prior_context": "",
            "grounding_context": "",
        }

        result = _extract_results(state)
        assert not any("[tool_errors]" in d for d in result["digest_lines"])


# ---------------------------------------------------------------------------
# InvestigatorRole tests
# ---------------------------------------------------------------------------

class TestInvestigatorRole:
    """Tests for specialist role assignment and prompt injection."""

    def test_investigation_topic_defaults_to_diagnostics(self):
        topic = _make_topic()
        assert topic.role == "diagnostics"

    def test_investigation_topic_accepts_valid_role(self):
        topic = _make_topic(role="reputation")
        assert topic.role == "reputation"

    def test_role_prompt_supplement_injected_in_call_investigator(self):
        """_call_investigator should include the role's prompt supplement in the system message."""
        from llm_pipeline.agents.investigator import _call_investigator

        mock_response = AIMessage(content="I will investigate.")
        mock_response.usage_metadata = {"input_tokens": 100, "output_tokens": 50}

        with patch("llm_pipeline.agents.plugins.investigator.agent.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.bind_tools.return_value = mock_llm
            mock_llm.invoke.return_value = mock_response
            mock_get_llm.return_value = mock_llm

            state = {
                "topic": _make_topic(role="reputation"),
                "run_id": "run-001",
                "ml_run_id": "ml-001",
                "messages": [],
                "findings": [],
                "hypotheses": [],
                "digest_lines": [],
                "prior_context": "",
                "grounding_context": "",
            }

            _call_investigator(state)

            # Check that the system message contains the reputation supplement
            call_args = mock_llm.invoke.call_args[0][0]
            system_msg = call_args[0]
            assert "reputation specialist" in system_msg.content.lower()

    def test_grounding_context_injected_in_brief(self):
        """_call_investigator should include grounding_context in the brief."""
        from llm_pipeline.agents.investigator import _call_investigator

        mock_response = AIMessage(content="I will investigate.")
        mock_response.usage_metadata = {"input_tokens": 100, "output_tokens": 50}

        with patch("llm_pipeline.agents.plugins.investigator.agent.get_llm") as mock_get_llm:
            mock_llm = MagicMock()
            mock_llm.bind_tools.return_value = mock_llm
            mock_llm.invoke.return_value = mock_response
            mock_get_llm.return_value = mock_llm

            grounding = "- [Reputation] IP warming is critical for new senders"
            state = {
                "topic": _make_topic(role="reputation"),
                "run_id": "run-001",
                "ml_run_id": "ml-001",
                "messages": [],
                "findings": [],
                "hypotheses": [],
                "digest_lines": [],
                "prior_context": "",
                "grounding_context": grounding,
            }

            _call_investigator(state)

            call_args = mock_llm.invoke.call_args[0][0]
            brief_msg = call_args[1]  # HumanMessage (the brief)
            assert "--- Domain Knowledge ---" in brief_msg.content
            assert "IP warming is critical" in brief_msg.content

    def test_orchestrator_parse_topics_with_valid_role(self):
        from llm_pipeline.agents.orchestrator import _parse_topics

        content = '[{"title": "T1", "dimension": "listid", "dimension_value": "VH", ' \
                  '"metrics": ["delivery_rate"], "question": "Why?", ' \
                  '"priority": "high", "context": "ctx", "role": "compliance"}]'
        topics = _parse_topics(content)
        assert len(topics) == 1
        assert topics[0].role == "compliance"

    def test_orchestrator_parse_topics_invalid_role_defaults_to_diagnostics(self):
        from llm_pipeline.agents.orchestrator import _parse_topics

        content = '[{"title": "T1", "dimension": "listid", "dimension_value": "VH", ' \
                  '"metrics": ["delivery_rate"], "question": "Why?", ' \
                  '"priority": "high", "context": "ctx", "role": "invalid_role"}]'
        topics = _parse_topics(content)
        assert len(topics) == 1
        assert topics[0].role == "diagnostics"

    def test_orchestrator_parse_topics_missing_role_defaults_to_diagnostics(self):
        from llm_pipeline.agents.orchestrator import _parse_topics

        content = '[{"title": "T1", "dimension": "listid", "dimension_value": "VH", ' \
                  '"metrics": ["delivery_rate"], "question": "Why?", ' \
                  '"priority": "high", "context": "ctx"}]'
        topics = _parse_topics(content)
        assert len(topics) == 1
        assert topics[0].role == "diagnostics"

    def test_route_investigations_includes_grounding_context(self):
        """_route_investigations should pass grounding_context in Send payloads."""
        from llm_pipeline.agents.graph import _route_investigations

        topic = _make_topic(role="compliance")
        state = {
            "investigation_plan": [topic],
            "run_id": "run-001",
            "ml_run_id": "ml-001",
        }

        with patch("llm_pipeline.agents.roles.get_role_grounding", return_value="grounding text"):
            result = _route_investigations(state)

        assert len(result) == 1
        assert result[0].arg["grounding_context"] == "grounding text"

    def test_route_after_evaluate_includes_grounding_context(self):
        """_route_after_evaluate should pass grounding_context in Send payloads."""
        from llm_pipeline.agents.graph import _route_after_evaluate

        topic = _make_topic(role="isp")
        state = {
            "investigation_plan": [topic],
            "run_id": "run-001",
            "ml_run_id": "ml-001",
            "prior_findings": [],
            "prior_hypotheses": [],
        }

        with patch("llm_pipeline.agents.roles.get_role_grounding", return_value="isp grounding"):
            result = _route_after_evaluate(state)

        assert isinstance(result, list)
        assert result[0].arg["grounding_context"] == "isp grounding"


class TestGetRoleGrounding:
    """Tests for roles.get_role_grounding."""

    def test_returns_formatted_results(self):
        from llm_pipeline.agents.roles import get_role_grounding

        from llm_pipeline.knowledge.retrieval import KnowledgeResult
        from llm_pipeline.knowledge.models import KnowledgeTier

        mock_results = [
            KnowledgeResult(
                entry_id="1",
                tier=KnowledgeTier.GROUNDED,
                statement="SPF validates sender IP",
                topic="Authentication",
                similarity=0.9,
                weighted_score=0.9,
            ),
        ]

        with patch("llm_pipeline.knowledge.retrieval.retrieve_knowledge", return_value=mock_results):
            result = get_role_grounding("compliance", top_k=3)

        assert "Authentication" in result
        assert "SPF validates sender IP" in result

    def test_returns_empty_on_failure(self):
        from llm_pipeline.agents.roles import get_role_grounding

        with patch("llm_pipeline.knowledge.retrieval.retrieve_knowledge", side_effect=Exception("conn err")):
            result = get_role_grounding("reputation")

        assert result == ""

    def test_returns_empty_when_no_results(self):
        from llm_pipeline.agents.roles import get_role_grounding

        with patch("llm_pipeline.knowledge.retrieval.retrieve_knowledge", return_value=[]):
            result = get_role_grounding("isp")

        assert result == ""

    def test_truncates_long_statements(self):
        from llm_pipeline.agents.roles import get_role_grounding

        from llm_pipeline.knowledge.retrieval import KnowledgeResult
        from llm_pipeline.knowledge.models import KnowledgeTier

        long_statement = "x" * 500
        mock_results = [
            KnowledgeResult(
                entry_id="1",
                tier=KnowledgeTier.GROUNDED,
                statement=long_statement,
                topic="Test",
                similarity=0.9,
                weighted_score=0.9,
            ),
        ]

        with patch("llm_pipeline.knowledge.retrieval.retrieve_knowledge", return_value=mock_results):
            result = get_role_grounding("diagnostics")

        # Should be truncated to 300 chars (297 + "...")
        assert "..." in result
        assert len(result.split("] ")[1]) == 300
