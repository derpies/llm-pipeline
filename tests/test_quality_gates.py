"""Tests for investigation pipeline quality gates.

Covers: run status computation, findings validation, normalization logging,
investigator error handling, orchestrator error surfacing, compare-runs warnings.
"""

import json
import logging
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from llm_pipeline.agents.models import (
    CircuitBreakerBudget,
    Finding,
    FindingStatus,
    Hypothesis,
    InvestigationTopic,
)
from llm_pipeline.email_analytics.models import (
    InvestigationFindingRecord,
    InvestigationRunRecord,
    InvestigationRunStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_finding(**overrides) -> Finding:
    defaults = {
        "topic_title": "Test Topic",
        "statement": "Delivery rate dropped 15%",
        "status": FindingStatus.CONFIRMED,
        "evidence": ["bounce rate 12%", "z-score 4.2"],
        "metrics_cited": {"delivery_rate": 0.85},
        "created_at": datetime(2026, 3, 1, tzinfo=UTC),
        "run_id": "run-001",
    }
    defaults.update(overrides)
    return Finding(**defaults)


def _make_hypothesis(**overrides) -> Hypothesis:
    defaults = {
        "topic_title": "Test Topic",
        "statement": "IP warming issue on pool VH-1",
        "reasoning": "New IPs added recently",
        "created_at": datetime(2026, 3, 1, tzinfo=UTC),
        "run_id": "run-001",
    }
    defaults.update(overrides)
    return Hypothesis(**defaults)


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


def _ai_msg_with_tool_calls(tool_calls, content=""):
    return AIMessage(content=content, tool_calls=tool_calls)


# ---------------------------------------------------------------------------
# InvestigationRunStatus enum
# ---------------------------------------------------------------------------

class TestInvestigationRunStatus:

    def test_enum_values(self):
        assert InvestigationRunStatus.SUCCESS == "success"
        assert InvestigationRunStatus.PARTIAL == "partial"
        assert InvestigationRunStatus.FAILED == "failed"
        assert InvestigationRunStatus.DRY_RUN == "dry_run"


# ---------------------------------------------------------------------------
# validate_finding / validate_hypothesis
# ---------------------------------------------------------------------------

class TestValidateFinding:

    def test_valid_finding_no_warnings(self):
        from llm_pipeline.agents.storage import validate_finding
        f = _make_finding()
        assert validate_finding(f) == []

    def test_empty_statement(self):
        from llm_pipeline.agents.storage import validate_finding
        f = _make_finding(statement="")
        warnings = validate_finding(f)
        assert "empty_statement" in warnings

    def test_whitespace_only_statement(self):
        from llm_pipeline.agents.storage import validate_finding
        f = _make_finding(statement="   ")
        warnings = validate_finding(f)
        assert "empty_statement" in warnings

    def test_short_statement(self):
        from llm_pipeline.agents.storage import validate_finding
        f = _make_finding(statement="short")
        warnings = validate_finding(f)
        assert "statement_too_short" in warnings

    def test_confirmed_without_evidence(self):
        from llm_pipeline.agents.storage import validate_finding
        f = _make_finding(status=FindingStatus.CONFIRMED, evidence=[])
        warnings = validate_finding(f)
        assert "confirmed_without_evidence" in warnings

    def test_tool_use_failed(self):
        from llm_pipeline.agents.storage import validate_finding
        f = _make_finding(tool_use_failed=True)
        warnings = validate_finding(f)
        assert "tool_use_failed" in warnings

    def test_inconclusive_without_evidence_no_warning(self):
        from llm_pipeline.agents.storage import validate_finding
        f = _make_finding(status=FindingStatus.INCONCLUSIVE, evidence=[])
        warnings = validate_finding(f)
        assert "confirmed_without_evidence" not in warnings


class TestValidateHypothesis:

    def test_valid_hypothesis_no_warnings(self):
        from llm_pipeline.agents.storage import validate_hypothesis
        h = _make_hypothesis()
        assert validate_hypothesis(h) == []

    def test_empty_statement(self):
        from llm_pipeline.agents.storage import validate_hypothesis
        h = _make_hypothesis(statement="")
        assert "empty_statement" in validate_hypothesis(h)


# ---------------------------------------------------------------------------
# store_investigation_results — new fields
# ---------------------------------------------------------------------------

class TestStoreWithQualityFields:

    @patch("llm_pipeline.agents.storage.get_engine")
    def test_stores_status_and_dry_run(self, mock_get_engine):
        from llm_pipeline.agents.storage import store_investigation_results

        added_objects = []

        with patch("llm_pipeline.agents.storage.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.add.side_effect = lambda obj: added_objects.append(obj)
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=mock_session)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_session_cls.return_value = ctx

            store_investigation_results(
                run_id="run-001",
                findings=[_make_finding()],
                hypotheses=[],
                checkpoint_digest="",
                iteration_count=1,
                started_at=datetime(2026, 3, 1, tzinfo=UTC),
                status="dry_run",
                is_dry_run=True,
                ml_run_id="ml-001",
            )

            run_records = [o for o in added_objects if isinstance(o, InvestigationRunRecord)]
            assert len(run_records) == 1
            rec = run_records[0]
            assert rec.status == "dry_run"
            assert rec.is_dry_run is True
            assert rec.ml_run_id == "ml-001"

    @patch("llm_pipeline.agents.storage.get_engine")
    def test_maps_tool_use_failed_to_is_fallback(self, mock_get_engine):
        from llm_pipeline.agents.storage import store_investigation_results

        added_objects = []

        with patch("llm_pipeline.agents.storage.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.add.side_effect = lambda obj: added_objects.append(obj)
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=mock_session)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_session_cls.return_value = ctx

            findings = [_make_finding(tool_use_failed=True)]
            store_investigation_results(
                run_id="run-001",
                findings=findings,
                hypotheses=[],
                checkpoint_digest="",
                iteration_count=1,
                started_at=datetime(2026, 3, 1, tzinfo=UTC),
            )

            finding_records = [o for o in added_objects if isinstance(o, InvestigationFindingRecord)]
            assert len(finding_records) == 1
            assert finding_records[0].is_fallback is True

    @patch("llm_pipeline.agents.storage.get_engine")
    def test_aggregates_quality_warnings(self, mock_get_engine):
        from llm_pipeline.agents.storage import store_investigation_results

        added_objects = []

        with patch("llm_pipeline.agents.storage.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.add.side_effect = lambda obj: added_objects.append(obj)
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=mock_session)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_session_cls.return_value = ctx

            findings = [
                _make_finding(statement="", tool_use_failed=True),
            ]
            store_investigation_results(
                run_id="run-001",
                findings=findings,
                hypotheses=[],
                checkpoint_digest="",
                iteration_count=1,
                started_at=datetime(2026, 3, 1, tzinfo=UTC),
            )

            run_records = [o for o in added_objects if isinstance(o, InvestigationRunRecord)]
            warnings = json.loads(run_records[0].quality_warnings)
            assert len(warnings) > 0
            assert any("empty_statement" in w for w in warnings)
            assert any("tool_use_failed" in w for w in warnings)


# ---------------------------------------------------------------------------
# Normalization logging in _extract_results
# ---------------------------------------------------------------------------

class TestNormalizationLogging:

    def test_logs_invalid_metrics_json(self, caplog):
        from llm_pipeline.agents.investigator import _extract_results

        msg = _ai_msg_with_tool_calls([{
            "id": "call_1",
            "name": "report_finding",
            "args": {
                "statement": "Test finding with bad metrics",
                "status": "confirmed",
                "metrics_cited": "not valid json{{{",
            },
        }])

        state = {
            "topic": _make_topic(),
            "run_id": "run-001",
            "messages": [msg, AIMessage(content="ok")],
            "findings": [],
            "hypotheses": [],
            "digest_lines": [],
            "prior_context": "",
        }

        with caplog.at_level(logging.WARNING):
            result = _extract_results(state)

        assert any("metrics_cited is not valid JSON" in r.message for r in caplog.records)
        assert len(result["findings"]) == 1
        assert result["findings"][0].metrics_cited == {}

    def test_logs_non_numeric_metric(self, caplog):
        from llm_pipeline.agents.investigator import _extract_results

        msg = _ai_msg_with_tool_calls([{
            "id": "call_1",
            "name": "report_finding",
            "args": {
                "statement": "Test finding with non-numeric metric",
                "status": "confirmed",
                "metrics_cited": {"good": 0.95, "bad": "not-a-number"},
            },
        }])

        state = {
            "topic": _make_topic(),
            "run_id": "run-001",
            "messages": [msg, AIMessage(content="ok")],
            "findings": [],
            "hypotheses": [],
            "digest_lines": [],
            "prior_context": "",
        }

        with caplog.at_level(logging.WARNING):
            result = _extract_results(state)

        assert any("dropping non-numeric metric" in r.message for r in caplog.records)
        assert result["findings"][0].metrics_cited == {"good": 0.95}

    def test_logs_invalid_status(self, caplog):
        from llm_pipeline.agents.investigator import _extract_results

        msg = _ai_msg_with_tool_calls([{
            "id": "call_1",
            "name": "report_finding",
            "args": {
                "statement": "Test finding with bad status",
                "status": "maybe_confirmed",
            },
        }])

        state = {
            "topic": _make_topic(),
            "run_id": "run-001",
            "messages": [msg, AIMessage(content="ok")],
            "findings": [],
            "hypotheses": [],
            "digest_lines": [],
            "prior_context": "",
        }

        with caplog.at_level(logging.WARNING):
            result = _extract_results(state)

        assert any("invalid status" in r.message for r in caplog.records)
        assert result["findings"][0].status == FindingStatus.INCONCLUSIVE

    def test_normalization_count_in_digest(self):
        from llm_pipeline.agents.investigator import _extract_results

        msg = _ai_msg_with_tool_calls([{
            "id": "call_1",
            "name": "report_finding",
            "args": {
                "statement": "Finding with multiple normalizations",
                "status": "bogus_status",
                "metrics_cited": "bad json",
            },
        }])

        state = {
            "topic": _make_topic(),
            "run_id": "run-001",
            "messages": [msg, AIMessage(content="ok")],
            "findings": [],
            "hypotheses": [],
            "digest_lines": [],
            "prior_context": "",
        }

        result = _extract_results(state)
        assert any("[normalization]" in d for d in result["digest_lines"])

    def test_logs_fallback_creation(self, caplog):
        from llm_pipeline.agents.investigator import _extract_results

        state = {
            "topic": _make_topic(),
            "run_id": "run-001",
            "messages": [
                HumanMessage(content="brief"),
                AIMessage(content="I didn't call any tools"),
            ],
            "findings": [],
            "hypotheses": [],
            "digest_lines": [],
            "prior_context": "",
        }

        with caplog.at_level(logging.WARNING):
            result = _extract_results(state)

        assert any("no reporting tools called" in r.message for r in caplog.records)
        assert result["findings"][0].tool_use_failed is True


# ---------------------------------------------------------------------------
# _investigate_topic error handling
# ---------------------------------------------------------------------------

class TestInvestigateTopicErrorHandling:

    def test_exception_produces_fallback_finding(self):
        from llm_pipeline.agents.graph import _compiled_cache, _make_investigate_runner
        from llm_pipeline.agents.registry import get_agent

        manifest = get_agent("investigator")
        runner = _make_investigate_runner(manifest)

        topic = _make_topic(title="Crashing Topic")
        state = {
            "topic": topic,
            "run_id": "run-001",
            "messages": [],
            "findings": [],
            "hypotheses": [],
            "digest_lines": [],
            "prior_context": "",
        }

        mock_compiled = MagicMock()
        mock_compiled.invoke.side_effect = RuntimeError("LLM exploded")
        _compiled_cache["investigator"] = mock_compiled
        try:
            result = runner(state)
        finally:
            _compiled_cache.pop("investigator", None)

        assert len(result["findings"]) == 1
        f = result["findings"][0]
        assert f.tool_use_failed is True
        assert f.status == FindingStatus.INCONCLUSIVE
        assert "RuntimeError" in f.statement
        assert "LLM exploded" in f.statement
        assert result["completed_topics"] == ["Crashing Topic"]

    def test_exception_surfaces_in_digest_and_errors(self):
        from llm_pipeline.agents.graph import _compiled_cache, _make_investigate_runner
        from llm_pipeline.agents.registry import get_agent

        manifest = get_agent("investigator")
        runner = _make_investigate_runner(manifest)

        topic = _make_topic(title="Error Topic")
        state = {
            "topic": topic,
            "run_id": "run-001",
            "messages": [],
            "findings": [],
            "hypotheses": [],
            "digest_lines": [],
            "prior_context": "",
        }

        mock_compiled = MagicMock()
        mock_compiled.invoke.side_effect = ValueError("bad data")
        _compiled_cache["investigator"] = mock_compiled
        try:
            result = runner(state)
        finally:
            _compiled_cache.pop("investigator", None)

        assert any("[error]" in d for d in result["digest_lines"])
        assert len(result["topic_errors"]) == 1
        assert "Error Topic" in result["topic_errors"][0]


# ---------------------------------------------------------------------------
# Orchestrator evaluation error surfacing
# ---------------------------------------------------------------------------

class TestOrchestratorErrorSurfacing:

    def test_evaluation_error_surfaces_in_digest(self):
        from llm_pipeline.agents.orchestrator import orchestrator_evaluate

        state = {
            "findings": [
                _make_finding(status=FindingStatus.INCONCLUSIVE),
            ],
            "hypotheses": [_make_hypothesis()],
            "iteration_count": 0,
            "started_at": datetime.now(UTC),
            "budget": CircuitBreakerBudget(max_iterations=5, max_seconds=600),
        }

        with patch("llm_pipeline.agents.orchestrator.get_llm") as mock_get_llm:
            mock_get_llm.side_effect = RuntimeError("API timeout")
            result = orchestrator_evaluate(state)

        assert result["evaluation_error"] is True
        assert result["investigation_plan"] == []
        assert any("[error]" in d for d in result["digest_lines"])
        assert any("API timeout" in d for d in result["digest_lines"])


class TestCheckpointErrorSection:

    def test_errors_section_when_errors_in_digest(self):
        from llm_pipeline.agents.orchestrator import orchestrator_checkpoint

        state = {
            "run_id": "run-001",
            "iteration_count": 1,
            "findings": [],
            "hypotheses": [],
            "digest_lines": [
                "[plan] Created 2 topics",
                "[error] Orchestrator evaluation failed: RuntimeError: boom",
            ],
        }

        result = orchestrator_checkpoint(state)
        digest = result["checkpoint_digest"]
        assert "## Errors" in digest
        assert "RuntimeError: boom" in digest

    def test_no_errors_section_when_clean(self):
        from llm_pipeline.agents.orchestrator import orchestrator_checkpoint

        state = {
            "run_id": "run-001",
            "iteration_count": 1,
            "findings": [],
            "hypotheses": [],
            "digest_lines": ["[plan] Created 2 topics"],
        }

        result = orchestrator_checkpoint(state)
        assert "## Errors" not in result["checkpoint_digest"]


# ---------------------------------------------------------------------------
# Compare-runs warnings
# ---------------------------------------------------------------------------

class TestCompareRunsWarnings:

    def _make_run(self, **overrides):
        defaults = {
            "run_id": "run-001",
            "started_at": datetime(2026, 3, 1, tzinfo=UTC),
            "completed_at": datetime(2026, 3, 1, 1, 0, tzinfo=UTC),
            "iteration_count": 1,
            "findings": [_make_finding()],
            "hypotheses": [],
            "checkpoint_digest": "",
            "label": "",
            "status": "success",
            "is_dry_run": False,
            "ml_run_id": "ml-001",
            "quality_warnings": [],
        }
        defaults.update(overrides)
        return defaults

    def test_dry_run_warning(self):
        from llm_pipeline.cli import _format_comparison

        a = self._make_run(is_dry_run=True, status="dry_run")
        b = self._make_run()
        output = _format_comparison(a, b)
        assert "WARNING" in output
        assert "dry-run" in output.lower()

    def test_failed_run_warning(self):
        from llm_pipeline.cli import _format_comparison

        a = self._make_run(status="failed")
        b = self._make_run()
        output = _format_comparison(a, b)
        assert "WARNING" in output
        assert "failed" in output

    def test_different_ml_reports_warning(self):
        from llm_pipeline.cli import _format_comparison

        a = self._make_run(ml_run_id="ml-001")
        b = self._make_run(ml_run_id="ml-002")
        output = _format_comparison(a, b)
        assert "WARNING" in output
        assert "different ML reports" in output

    def test_no_warnings_for_clean_runs(self):
        from llm_pipeline.cli import _format_comparison

        a = self._make_run()
        b = self._make_run(run_id="run-002")
        output = _format_comparison(a, b)
        assert "WARNINGS" not in output

    def test_status_shown_in_metadata(self):
        from llm_pipeline.cli import _format_comparison

        a = self._make_run(status="partial")
        b = self._make_run()
        output = _format_comparison(a, b)
        assert "status=partial" in output
        assert "status=success" in output


# ---------------------------------------------------------------------------
# Markdown output quality flags
# ---------------------------------------------------------------------------

class TestMarkdownQualityFlags:

    def test_fallback_finding_marked(self, tmp_path):
        from llm_pipeline.agents.storage import write_investigation_markdown

        findings = [_make_finding(tool_use_failed=True)]
        path = write_investigation_markdown(
            run_id="run-001",
            findings=findings,
            hypotheses=[],
            checkpoint_digest="",
            iteration_count=1,
            started_at=datetime(2026, 3, 1, tzinfo=UTC),
            output_dir=tmp_path,
        )
        content = path.read_text()
        assert "[FALLBACK]" in content

    def test_status_shown_in_header(self, tmp_path):
        from llm_pipeline.agents.storage import write_investigation_markdown

        path = write_investigation_markdown(
            run_id="run-001",
            findings=[],
            hypotheses=[],
            checkpoint_digest="",
            iteration_count=1,
            started_at=datetime(2026, 3, 1, tzinfo=UTC),
            status="partial",
            output_dir=tmp_path,
        )
        content = path.read_text()
        assert "PARTIAL" in content

    def test_dry_run_shown_in_header(self, tmp_path):
        from llm_pipeline.agents.storage import write_investigation_markdown

        path = write_investigation_markdown(
            run_id="run-001",
            findings=[],
            hypotheses=[],
            checkpoint_digest="",
            iteration_count=1,
            started_at=datetime(2026, 3, 1, tzinfo=UTC),
            is_dry_run=True,
            output_dir=tmp_path,
        )
        content = path.read_text()
        assert "DRY RUN" in content

    def test_quality_warnings_section(self, tmp_path):
        from llm_pipeline.agents.storage import write_investigation_markdown

        findings = [_make_finding(status=FindingStatus.CONFIRMED, evidence=[])]
        path = write_investigation_markdown(
            run_id="run-001",
            findings=findings,
            hypotheses=[],
            checkpoint_digest="",
            iteration_count=1,
            started_at=datetime(2026, 3, 1, tzinfo=UTC),
            output_dir=tmp_path,
        )
        content = path.read_text()
        assert "Quality Warnings" in content
        assert "confirmed_without_evidence" in content
