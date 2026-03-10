"""Tests for the synthesizer agent — narrative synthesis after investigation loop."""

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


def _make_annotation(**overrides) -> ReviewAnnotation:
    defaults = {
        "finding_index": 0,
        "finding_statement": "Delivery rate dropped",
        "assessment": ReviewAssessment.SUPPORTED,
        "reasoning": "Evidence checks out",
        "suggested_action": ReviewAction.ACCEPT,
    }
    defaults.update(overrides)
    return ReviewAnnotation(**defaults)


# ---------------------------------------------------------------------------
# _parse_synthesis tests
# ---------------------------------------------------------------------------

class TestParseSynthesis:
    """Tests for synthesizer._parse_synthesis."""

    def test_parses_valid_json(self):
        from llm_pipeline.agents.synthesizer import _parse_synthesis

        content = json.dumps({
            "executive_summary": "VH segment experienced a delivery drop.",
            "observations": [
                {"section": "cross_cutting_patterns", "note": "Bounce rates correlated."},
                {"section": "next_cycle_focus", "note": "Monitor VH closely."},
            ],
        })

        narrative, summary = _parse_synthesis(content)
        assert "VH segment experienced a delivery drop" in narrative
        assert "Bounce rates correlated" in narrative
        assert "Monitor VH closely" in narrative
        assert summary == "VH segment experienced a delivery drop."

    def test_handles_code_fences(self):
        from llm_pipeline.agents.synthesizer import _parse_synthesis

        content = '```json\n{"executive_summary": "Test summary.", "observations": []}\n```'
        narrative, summary = _parse_synthesis(content)
        assert "Test summary" in narrative
        assert summary == "Test summary."

    def test_returns_raw_on_invalid_json(self):
        from llm_pipeline.agents.synthesizer import _parse_synthesis

        content = "This is not JSON but still useful text."
        narrative, summary = _parse_synthesis(content)
        assert narrative == content
        assert summary == ""

    def test_handles_empty_observations(self):
        from llm_pipeline.agents.synthesizer import _parse_synthesis

        content = json.dumps({
            "executive_summary": "No significant patterns found.",
            "observations": [],
        })

        narrative, summary = _parse_synthesis(content)
        assert "No significant patterns found" in narrative
        assert summary == "No significant patterns found."

    def test_groups_observations_by_section(self):
        from llm_pipeline.agents.synthesizer import _parse_synthesis

        content = json.dumps({
            "executive_summary": "Summary.",
            "observations": [
                {"section": "data_quality", "note": "High zero-value rate in DS."},
                {"section": "data_quality", "note": "Missing XMRID fields."},
                {"section": "contradictions", "note": "VH bounce up but delivery stable."},
            ],
        })

        narrative, _ = _parse_synthesis(content)
        assert "Data Quality:" in narrative
        assert "High zero-value rate" in narrative
        assert "Contradictions:" in narrative


# ---------------------------------------------------------------------------
# _build_synthesis_input tests
# ---------------------------------------------------------------------------

class TestBuildSynthesisInput:
    """Tests for synthesizer._build_synthesis_input."""

    def test_includes_findings_by_status(self):
        from llm_pipeline.agents.synthesizer import _build_synthesis_input

        state = {
            "findings": [
                _make_finding(status=FindingStatus.CONFIRMED),
                _make_finding(status=FindingStatus.DISPROVEN, statement="Disproven thing"),
            ],
            "hypotheses": [],
            "review_annotations": [],
        }

        result = _build_synthesis_input(state)
        assert "CONFIRMED" in result
        assert "DISPROVEN" in result
        assert "Delivery rate dropped" in result
        assert "Disproven thing" in result

    def test_includes_reviewer_annotations(self):
        from llm_pipeline.agents.synthesizer import _build_synthesis_input

        state = {
            "findings": [_make_finding()],
            "hypotheses": [],
            "review_annotations": [_make_annotation()],
        }

        result = _build_synthesis_input(state)
        assert "supported" in result
        assert "accept" in result

    def test_includes_hypotheses(self):
        from llm_pipeline.agents.synthesizer import _build_synthesis_input

        state = {
            "findings": [],
            "hypotheses": [_make_hypothesis()],
            "review_annotations": [],
        }

        result = _build_synthesis_input(state)
        assert "IP warmup" in result

    def test_empty_state(self):
        from llm_pipeline.agents.synthesizer import _build_synthesis_input

        state = {
            "findings": [],
            "hypotheses": [],
            "review_annotations": [],
        }

        result = _build_synthesis_input(state)
        assert "No findings" in result


# ---------------------------------------------------------------------------
# synthesize_narrative node tests
# ---------------------------------------------------------------------------

class TestSynthesizeNarrative:
    """Tests for synthesizer.synthesize_narrative graph node."""

    def test_skips_when_no_findings(self):
        from llm_pipeline.agents.synthesizer import synthesize_narrative

        state = {
            "findings": [],
            "hypotheses": [],
            "review_annotations": [],
            "run_id": "test-run",
        }

        result = synthesize_narrative(state)
        assert result["synthesis_narrative"] == ""
        assert any("skipped" in d for d in result["digest_lines"])

    def test_produces_narrative(self):
        from llm_pipeline.agents.synthesizer import synthesize_narrative

        synth_response = AIMessage(content=json.dumps({
            "executive_summary": "VH segment needs attention.",
            "observations": [
                {"section": "next_cycle_focus", "note": "Focus on bounce analysis."},
            ],
        }))

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = synth_response

        with patch("llm_pipeline.agents.synthesizer.get_llm", return_value=mock_llm):
            state = {
                "findings": [_make_finding()],
                "hypotheses": [],
                "review_annotations": [],
                "run_id": "test-run",
            }

            result = synthesize_narrative(state)

        assert "VH segment needs attention" in result["synthesis_narrative"]
        assert any("[synthesis]" in d for d in result["digest_lines"])

    def test_handles_unparseable_response(self):
        """If LLM returns non-JSON, narrative is still captured as raw text."""
        from llm_pipeline.agents.synthesizer import synthesize_narrative

        raw_response = AIMessage(content="The investigation reveals concerning patterns.")

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = raw_response

        with patch("llm_pipeline.agents.synthesizer.get_llm", return_value=mock_llm):
            state = {
                "findings": [_make_finding()],
                "hypotheses": [],
                "review_annotations": [],
                "run_id": "test-run",
            }

            result = synthesize_narrative(state)

        assert "concerning patterns" in result["synthesis_narrative"]
