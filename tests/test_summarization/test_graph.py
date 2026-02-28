"""End-to-end tests for the summarization graph with a fake LLM."""

from unittest.mock import patch

from langchain_core.language_models.fake_chat_models import FakeListChatModel

from llm_pipeline.summarization.graph import build_summarization_graph
from llm_pipeline.summarization.models import DocumentType


def _make_fake_llm(n_responses: int = 50) -> FakeListChatModel:
    """Create a FakeListChatModel with enough canned responses."""
    responses = [f"This is generated document content #{i}." for i in range(n_responses)]
    return FakeListChatModel(responses=responses)


class TestSummarizationGraph:
    def test_produces_documents(self, sample_report):
        """Graph should produce the expected number of documents."""
        fake_llm = _make_fake_llm()

        with (
            patch("llm_pipeline.summarization.graph._get_llm", return_value=fake_llm),
            patch(
                "llm_pipeline.summarization.embed.store_documents",
                return_value=10,
            ) as mock_store,
        ):
            graph = build_summarization_graph()
            result = graph.invoke({
                "report": sample_report,
                "run_id": sample_report.run_id,
            })

        summ_result = result["result"]
        assert summ_result.run_id == "test-run-001"
        # 1 executive + 5 anomalies + 3 trends + 3 dimensions (top_n=10, only 3 exist)
        assert summ_result.documents_generated == 12
        assert summ_result.chunks_stored == 10
        assert mock_store.called

    def test_document_types(self, sample_report):
        """All four document types should be generated."""
        fake_llm = _make_fake_llm()

        with (
            patch("llm_pipeline.summarization.graph._get_llm", return_value=fake_llm),
            patch("llm_pipeline.summarization.embed.store_documents", return_value=5),
        ):
            graph = build_summarization_graph()
            result = graph.invoke({
                "report": sample_report,
                "run_id": sample_report.run_id,
            })

        docs = result.get("documents", [])
        doc_types = {d.document_type for d in docs}
        assert DocumentType.EXECUTIVE_SUMMARY in doc_types
        assert DocumentType.ANOMALY_NARRATIVE in doc_types
        assert DocumentType.TREND_NARRATIVE in doc_types
        assert DocumentType.DIMENSIONAL_SUMMARY in doc_types

    def test_metadata_on_documents(self, sample_report):
        """Generated documents should have correct metadata."""
        fake_llm = _make_fake_llm()

        with (
            patch("llm_pipeline.summarization.graph._get_llm", return_value=fake_llm),
            patch("llm_pipeline.summarization.embed.store_documents", return_value=5),
        ):
            graph = build_summarization_graph()
            result = graph.invoke({
                "report": sample_report,
                "run_id": sample_report.run_id,
            })

        docs = result.get("documents", [])
        # All docs should have the run_id
        for doc in docs:
            assert doc.run_id == "test-run-001"

        # Anomaly narratives should have severity
        anomaly_docs = [d for d in docs if d.document_type == DocumentType.ANOMALY_NARRATIVE]
        assert len(anomaly_docs) == 5
        severities = {d.severity for d in anomaly_docs}
        assert "high" in severities

        # Dimensional summaries should have dimension info
        dim_docs = [d for d in docs if d.document_type == DocumentType.DIMENSIONAL_SUMMARY]
        assert all(d.dimension == "recipient_domain" for d in dim_docs)

    def test_empty_report(self):
        """Graph should handle a report with no findings gracefully."""
        from datetime import UTC, datetime

        from llm_pipeline.email_analytics.models import AnalysisReport

        empty_report = AnalysisReport(
            run_id="empty-run",
            started_at=datetime.now(UTC),
        )

        fake_llm = _make_fake_llm()

        with (
            patch("llm_pipeline.summarization.graph._get_llm", return_value=fake_llm),
            patch("llm_pipeline.summarization.embed.store_documents", return_value=0),
        ):
            graph = build_summarization_graph()
            result = graph.invoke({
                "report": empty_report,
                "run_id": "empty-run",
            })

        summ_result = result["result"]
        # Just 1 executive summary (no anomalies, trends, or dimensions)
        assert summ_result.documents_generated == 1
        assert summ_result.errors == []

    def test_llm_error_captured(self, sample_report):
        """LLM errors should be captured in errors list, not crash the graph."""
        def exploding_get_llm():
            raise RuntimeError("LLM is down")

        with (
            patch("llm_pipeline.summarization.graph._get_llm", side_effect=exploding_get_llm),
            patch("llm_pipeline.summarization.embed.store_documents", return_value=0),
        ):
            graph = build_summarization_graph()
            result = graph.invoke({
                "report": sample_report,
                "run_id": sample_report.run_id,
            })

        summ_result = result["result"]
        assert summ_result.documents_generated == 0
        assert len(summ_result.errors) > 0
