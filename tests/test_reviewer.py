"""Tests for the reviewer agent — finding quality gate."""

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from llm_pipeline.agents.models import (
    Finding,
    FindingStatus,
    Hypothesis,
    ReviewAction,
    ReviewAnnotation,
    ReviewAssessment,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_finding(**overrides) -> Finding:
    defaults = {
        "topic_title": "Test Topic",
        "statement": "Delivery rate dropped 15% for VH segment",
        "status": FindingStatus.CONFIRMED,
        "evidence": ["bounce rate 12% vs baseline 3%"],
        "metrics_cited": {"delivery_rate": 0.85},
        "created_at": datetime.now(UTC),
        "run_id": "run-001",
    }
    defaults.update(overrides)
    return Finding(**defaults)


def _make_hypothesis(**overrides) -> Hypothesis:
    defaults = {
        "topic_title": "Test Topic",
        "statement": "IP warmup may be causing dips",
        "reasoning": "New IPs added to VH pool last week",
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Hypothesis(**defaults)


# ---------------------------------------------------------------------------
# _parse_annotations tests
# ---------------------------------------------------------------------------

class TestParseAnnotations:
    """Tests for reviewer._parse_annotations."""

    def test_parses_valid_annotations(self):
        from llm_pipeline.agents.reviewer import _parse_annotations

        findings = [_make_finding()]
        content = json.dumps([{
            "finding_index": 0,
            "finding_statement": "Delivery rate dropped 15% for VH segment",
            "assessment": "supported",
            "reasoning": "Evidence is consistent with bounce spike",
            "suggested_action": "accept",
            "follow_up_question": "",
        }])

        annotations = _parse_annotations(content, findings)
        assert len(annotations) == 1
        assert annotations[0].assessment == ReviewAssessment.SUPPORTED
        assert annotations[0].suggested_action == ReviewAction.ACCEPT

    def test_parses_multiple_annotations(self):
        from llm_pipeline.agents.reviewer import _parse_annotations

        findings = [_make_finding(), _make_finding(statement="Another finding")]
        content = json.dumps([
            {
                "finding_index": 0,
                "finding_statement": "Finding 1",
                "assessment": "supported",
                "reasoning": "OK",
                "suggested_action": "accept",
            },
            {
                "finding_index": 1,
                "finding_statement": "Finding 2",
                "assessment": "weak_evidence",
                "reasoning": "Needs more data",
                "suggested_action": "investigate_further",
                "follow_up_question": "Check bounce rates across ISPs",
            },
        ])

        annotations = _parse_annotations(content, findings)
        assert len(annotations) == 2
        assert annotations[1].assessment == ReviewAssessment.WEAK_EVIDENCE
        assert annotations[1].follow_up_question == "Check bounce rates across ISPs"

    def test_handles_code_fences(self):
        from llm_pipeline.agents.reviewer import _parse_annotations

        findings = [_make_finding()]
        content = (
            '```json\n[{"finding_index": 0, "finding_statement": "F1", '
            '"assessment": "supported", "reasoning": "OK", '
            '"suggested_action": "accept"}]\n```'
        )

        annotations = _parse_annotations(content, findings)
        assert len(annotations) == 1

    def test_coerces_invalid_assessment(self):
        from llm_pipeline.agents.reviewer import _parse_annotations

        findings = [_make_finding()]
        content = json.dumps([{
            "finding_index": 0,
            "finding_statement": "F1",
            "assessment": "maybe_ok",
            "reasoning": "OK",
            "suggested_action": "accept",
        }])

        annotations = _parse_annotations(content, findings)
        assert len(annotations) == 1
        assert annotations[0].assessment == ReviewAssessment.WEAK_EVIDENCE

    def test_coerces_invalid_action(self):
        from llm_pipeline.agents.reviewer import _parse_annotations

        findings = [_make_finding()]
        content = json.dumps([{
            "finding_index": 0,
            "finding_statement": "F1",
            "assessment": "supported",
            "reasoning": "OK",
            "suggested_action": "unknown_action",
        }])

        annotations = _parse_annotations(content, findings)
        assert len(annotations) == 1
        assert annotations[0].suggested_action == ReviewAction.FLAG_FOR_HUMAN

    def test_clamps_finding_index(self):
        from llm_pipeline.agents.reviewer import _parse_annotations

        findings = [_make_finding()]
        content = json.dumps([{
            "finding_index": 99,
            "finding_statement": "F1",
            "assessment": "supported",
            "reasoning": "OK",
            "suggested_action": "accept",
        }])

        annotations = _parse_annotations(content, findings)
        assert len(annotations) == 1
        assert annotations[0].finding_index == 0

    def test_returns_empty_on_invalid_json(self):
        from llm_pipeline.agents.reviewer import _parse_annotations

        annotations = _parse_annotations("not json", [_make_finding()])
        assert annotations == []

    def test_returns_empty_on_non_array(self):
        from llm_pipeline.agents.reviewer import _parse_annotations

        annotations = _parse_annotations('{"key": "value"}', [_make_finding()])
        assert annotations == []


# ---------------------------------------------------------------------------
# _build_review_input tests
# ---------------------------------------------------------------------------

class TestBuildReviewInput:
    """Tests for reviewer._build_review_input."""

    def test_formats_findings(self):
        from llm_pipeline.agents.reviewer import _build_review_input

        findings = [_make_finding()]
        result = _build_review_input(findings, [])
        assert "Delivery rate dropped 15%" in result
        assert "[0]" in result
        assert "bounce rate 12%" in result

    def test_includes_hypotheses(self):
        from llm_pipeline.agents.reviewer import _build_review_input

        result = _build_review_input([], [_make_hypothesis()])
        assert "IP warmup" in result

    def test_no_findings_message(self):
        from llm_pipeline.agents.reviewer import _build_review_input

        result = _build_review_input([], [])
        assert "No findings to review" in result


# ---------------------------------------------------------------------------
# review_findings node tests
# ---------------------------------------------------------------------------

class TestReviewFindings:
    """Tests for reviewer.review_findings graph node."""

    def test_skips_when_no_findings(self):
        from llm_pipeline.agents.reviewer import review_findings

        state = {
            "findings": [],
            "hypotheses": [],
            "run_id": "test-run",
        }

        result = review_findings(state)
        assert result["review_annotations"] == []
        assert any("skipped" in d for d in result["digest_lines"])

    def test_produces_annotations(self):
        from llm_pipeline.agents.reviewer import review_findings

        reviewer_response = AIMessage(content=json.dumps([{
            "finding_index": 0,
            "finding_statement": "Delivery rate dropped",
            "assessment": "supported",
            "reasoning": "Evidence checks out",
            "suggested_action": "accept",
        }]))

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.return_value = reviewer_response

        with patch("llm_pipeline.agents.reviewer.get_llm", return_value=mock_llm):
            state = {
                "findings": [_make_finding()],
                "hypotheses": [],
                "run_id": "test-run",
            }

            result = review_findings(state)

        assert len(result["review_annotations"]) == 1
        ann = result["review_annotations"][0]
        assert ann.assessment == ReviewAssessment.SUPPORTED
        assert any("[review]" in d for d in result["digest_lines"])

    def test_handles_reviewer_llm_failure(self):
        """If the reviewer LLM returns unparseable content, return empty annotations."""
        from llm_pipeline.agents.reviewer import review_findings

        bad_response = AIMessage(content="I cannot review these findings properly.")

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.invoke.return_value = bad_response

        with patch("llm_pipeline.agents.reviewer.get_llm", return_value=mock_llm):
            state = {
                "findings": [_make_finding()],
                "hypotheses": [],
                "run_id": "test-run",
            }

            result = review_findings(state)

        assert result["review_annotations"] == []
        assert any("[review]" in d for d in result["digest_lines"])


# ---------------------------------------------------------------------------
# ReviewAnnotation model tests
# ---------------------------------------------------------------------------

class TestReviewAnnotationModel:
    """Tests for ReviewAnnotation Pydantic model."""

    def test_all_assessments_valid(self):
        for assessment in ReviewAssessment:
            ann = ReviewAnnotation(
                finding_index=0,
                finding_statement="test",
                assessment=assessment,
                reasoning="test",
                suggested_action=ReviewAction.ACCEPT,
            )
            assert ann.assessment == assessment

    def test_all_actions_valid(self):
        for action in ReviewAction:
            ann = ReviewAnnotation(
                finding_index=0,
                finding_statement="test",
                assessment=ReviewAssessment.SUPPORTED,
                reasoning="test",
                suggested_action=action,
            )
            assert ann.suggested_action == action

    def test_default_follow_up_question(self):
        ann = ReviewAnnotation(
            finding_index=0,
            finding_statement="test",
            assessment=ReviewAssessment.SUPPORTED,
            reasoning="test",
            suggested_action=ReviewAction.ACCEPT,
        )
        assert ann.follow_up_question == ""


# ---------------------------------------------------------------------------
# Reviewer tool access tests
# ---------------------------------------------------------------------------

class TestReviewerTools:
    """Tests for reviewer tool access via registry."""

    def test_reviewer_gets_ml_tools(self):
        from llm_pipeline.tools.registry import get_tools, reset_registry

        reset_registry()
        tools = get_tools("reviewer")
        tool_names = {t.name for t in tools}
        expected_ml = {
            "get_aggregations", "get_anomalies", "get_trends",
            "get_ml_report_summary", "get_data_completeness", "compare_dimensions",
        }
        assert expected_ml <= tool_names

    def test_reviewer_does_not_get_reporting_tools(self):
        from llm_pipeline.tools.registry import get_tools, reset_registry

        reset_registry()
        tools = get_tools("reviewer")
        tool_names = {t.name for t in tools}
        assert "report_finding" not in tool_names
        assert "report_hypothesis" not in tool_names
