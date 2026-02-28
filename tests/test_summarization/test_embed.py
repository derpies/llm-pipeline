"""Tests for the embed module — document conversion and storage."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from llm_pipeline.summarization.embed import documents_to_langchain, store_documents
from llm_pipeline.summarization.models import DocumentType, GeneratedDocument


def _make_doc(
    doc_type: DocumentType = DocumentType.ANOMALY_NARRATIVE,
    content: str = "Short content.",
    title: str = "Test Doc",
    **kwargs,
) -> GeneratedDocument:
    return GeneratedDocument(
        document_type=doc_type,
        title=title,
        content=content,
        run_id="test-run",
        generated_at=datetime.now(UTC),
        **kwargs,
    )


class TestDocumentsToLangchain:
    def test_short_doc_single_chunk(self):
        """Short documents should produce a single LangChain Document."""
        doc = _make_doc(content="Brief anomaly description.")
        lc_docs = documents_to_langchain([doc])
        assert len(lc_docs) == 1
        assert "Brief anomaly description" in lc_docs[0].page_content
        assert lc_docs[0].metadata["document_type"] == "anomaly_narrative"
        assert lc_docs[0].metadata["run_id"] == "test-run"

    def test_long_doc_split(self):
        """Long documents should be split into multiple chunks."""
        long_content = "word " * 500  # ~2500 chars, > default chunk_size of 1000
        doc = _make_doc(content=long_content)
        lc_docs = documents_to_langchain([doc])
        assert len(lc_docs) > 1
        # All chunks should have chunk_index metadata
        for i, lc_doc in enumerate(lc_docs):
            assert lc_doc.metadata["chunk_index"] == i
            assert lc_doc.metadata["chunk_total"] == len(lc_docs)

    def test_metadata_mapping(self):
        """Metadata should be correctly mapped from GeneratedDocument."""
        doc = _make_doc(
            doc_type=DocumentType.DIMENSIONAL_SUMMARY,
            dimension="recipient_domain",
            dimension_value="gmail.com",
            severity="high",
        )
        lc_docs = documents_to_langchain([doc])
        meta = lc_docs[0].metadata
        assert meta["document_type"] == "dimensional_summary"
        assert meta["dimension"] == "recipient_domain"
        assert meta["dimension_value"] == "gmail.com"
        assert meta["severity"] == "high"
        assert meta["source"] == "summarization"
        assert meta["title"] == "Test Doc"

    def test_empty_list(self):
        """Empty input should return empty output."""
        assert documents_to_langchain([]) == []

    def test_title_prepended(self):
        """Page content should start with the title."""
        doc = _make_doc(title="My Title", content="My content.")
        lc_docs = documents_to_langchain([doc])
        assert lc_docs[0].page_content.startswith("My Title")


class TestStoreDocuments:
    def test_calls_vectorstore(self):
        """store_documents should convert and add to vectorstore."""
        doc = _make_doc()
        mock_vs = MagicMock()

        with patch("llm_pipeline.rag.ingest.get_vectorstore", return_value=mock_vs):
            count = store_documents([doc])

        assert count == 1
        mock_vs.add_documents.assert_called_once()

    def test_empty_docs_returns_zero(self):
        """No docs should skip vectorstore call."""
        count = store_documents([])
        assert count == 0
