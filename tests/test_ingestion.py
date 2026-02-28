"""Tests for the ingestion pipeline."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from llm_pipeline.ingestion.classify import classify_path, collect_documents
from llm_pipeline.ingestion.state import DocumentItem

# --- Classifier tests ---


class TestClassifyPath:
    def test_txt(self):
        assert classify_path(Path("file.txt")) == "txt"

    def test_md(self):
        assert classify_path(Path("README.md")) == "txt"

    def test_pdf(self):
        assert classify_path(Path("doc.pdf")) == "pdf"

    def test_csv(self):
        assert classify_path(Path("data.csv")) == "csv"

    def test_python(self):
        assert classify_path(Path("main.py")) == "code"

    def test_image_png(self):
        assert classify_path(Path("photo.png")) == "image"

    def test_image_jpg(self):
        assert classify_path(Path("photo.jpg")) == "image"

    def test_unsupported(self):
        assert classify_path(Path("file.xyz")) is None

    def test_case_insensitive(self):
        assert classify_path(Path("file.PDF")) == "pdf"


class TestCollectDocuments:
    def test_single_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        docs, errors = collect_documents([str(f)])
        assert len(docs) == 1
        assert docs[0].doc_type == "txt"
        assert not errors

    def test_directory(self, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.md").write_text("b")
        (tmp_path / "c.xyz").write_text("c")
        docs, errors = collect_documents([str(tmp_path)])
        assert len(docs) == 2
        assert len(errors) == 1  # unsupported .xyz

    def test_nonexistent_path(self):
        docs, errors = collect_documents(["/nonexistent/path"])
        assert not docs
        assert len(errors) == 1

    def test_skips_hidden(self, tmp_path):
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "secret.txt").write_text("hidden")
        (tmp_path / "visible.txt").write_text("visible")
        docs, errors = collect_documents([str(tmp_path)])
        assert len(docs) == 1
        assert docs[0].filename == "visible.txt"


# --- Processor tests ---


class TestTxtProcessor:
    @patch("llm_pipeline.ingestion.processors.txt.settings")
    def test_processes_txt_file(self, mock_settings, tmp_path):
        mock_settings.chunk_size = 100
        mock_settings.chunk_overlap = 20

        # Reimport to pick up mocked settings
        from llm_pipeline.ingestion.processors.txt import txt_processor

        f = tmp_path / "test.txt"
        f.write_text("Hello world. " * 50)

        doc = DocumentItem(path=str(f), doc_type="txt", filename="test.txt")
        result = txt_processor.invoke({"document": doc})

        assert len(result.get("chunks", [])) > 0
        assert not result.get("errors")

    def test_handles_missing_file(self):
        from llm_pipeline.ingestion.processors.txt import txt_processor

        doc = DocumentItem(path="/nonexistent.txt", doc_type="txt", filename="nonexistent.txt")
        result = txt_processor.invoke({"document": doc})

        assert len(result.get("errors", [])) > 0


class TestCsvProcessor:
    def test_processes_csv_file(self, tmp_path):
        from llm_pipeline.ingestion.processors.csv import csv_processor

        f = tmp_path / "data.csv"
        f.write_text("name,age\nAlice,30\nBob,25\n")

        doc = DocumentItem(path=str(f), doc_type="csv", filename="data.csv")
        result = csv_processor.invoke({"document": doc})

        assert len(result.get("chunks", [])) == 2  # one per row
        assert not result.get("errors")


class TestCodeProcessor:
    @patch("llm_pipeline.ingestion.processors.code.settings")
    def test_processes_python_file(self, mock_settings, tmp_path):
        mock_settings.chunk_size = 100
        mock_settings.chunk_overlap = 20

        from llm_pipeline.ingestion.processors.code import code_processor

        f = tmp_path / "example.py"
        f.write_text("def hello():\n    print('hello')\n\ndef world():\n    print('world')\n")

        doc = DocumentItem(path=str(f), doc_type="code", filename="example.py")
        result = code_processor.invoke({"document": doc})

        assert len(result.get("chunks", [])) > 0
        assert not result.get("errors")


class TestPdfProcessor:
    @patch("llm_pipeline.ingestion.processors.pdf.PyPDFLoader")
    @patch("llm_pipeline.ingestion.processors.pdf.settings")
    def test_processes_pdf(self, mock_settings, mock_loader_cls):
        from langchain_core.documents import Document

        mock_settings.chunk_size = 1000
        mock_settings.chunk_overlap = 200

        mock_loader = MagicMock()
        mock_loader.load.return_value = [
            Document(page_content="Page 1 content", metadata={"page": 0}),
            Document(page_content="Page 2 content", metadata={"page": 1}),
        ]
        mock_loader_cls.return_value = mock_loader

        from llm_pipeline.ingestion.processors.pdf import pdf_processor

        doc = DocumentItem(path="/fake/doc.pdf", doc_type="pdf", filename="doc.pdf")
        result = pdf_processor.invoke({"document": doc})

        assert len(result.get("chunks", [])) == 2
        assert not result.get("errors")


class TestImageProcessor:
    @patch("llm_pipeline.ingestion.processors.image.get_llm")
    def test_processes_image(self, mock_get_llm, tmp_path):
        from langchain_core.messages import AIMessage

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="A photo of a cat sitting on a mat.")
        mock_get_llm.return_value = mock_llm

        # Create a minimal PNG file (1x1 pixel)
        f = tmp_path / "test.png"
        # Minimal valid PNG
        import struct
        import zlib

        def minimal_png():
            signature = b"\x89PNG\r\n\x1a\n"
            ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
            ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
            ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
            raw = b"\x00\x00\x00\x00"
            idat_data = zlib.compress(raw)
            idat_crc = zlib.crc32(b"IDAT" + idat_data) & 0xFFFFFFFF
            idat = (
                struct.pack(">I", len(idat_data))
                + b"IDAT"
                + idat_data
                + struct.pack(">I", idat_crc)
            )
            iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
            iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
            return signature + ihdr + idat + iend

        f.write_bytes(minimal_png())

        from llm_pipeline.ingestion.processors.image import image_processor

        doc = DocumentItem(path=str(f), doc_type="image", filename="test.png")
        result = image_processor.invoke({"document": doc})

        assert len(result.get("chunks", [])) > 0
        assert not result.get("errors")
        mock_llm.invoke.assert_called_once()


# --- Marshalling graph tests ---


class TestIngestionGraph:
    @patch("llm_pipeline.ingestion.graph._store")
    def test_batch_ingest_txt(self, mock_store, tmp_path):
        mock_store.return_value = {}

        f = tmp_path / "hello.txt"
        f.write_text("Hello world. This is a test document with some content.")

        from llm_pipeline.ingestion.graph import build_ingestion_graph

        graph = build_ingestion_graph(mode="batch")
        result = graph.invoke({"paths": [str(f)], "mode": "batch"})

        assert len(result.get("chunks", [])) > 0
        assert result.get("approved") is True

    def test_empty_paths(self):
        from llm_pipeline.ingestion.graph import build_ingestion_graph

        graph = build_ingestion_graph(mode="batch")
        result = graph.invoke({"paths": [], "mode": "batch"})

        assert result.get("chunks", []) == []

    @patch("llm_pipeline.ingestion.graph._store")
    def test_mixed_file_types(self, mock_store, tmp_path):
        mock_store.return_value = {}

        (tmp_path / "readme.md").write_text("# README\nSome content here.")
        (tmp_path / "data.csv").write_text("col1,col2\nval1,val2\n")
        (tmp_path / "script.py").write_text("print('hello')\n")

        from llm_pipeline.ingestion.graph import build_ingestion_graph

        graph = build_ingestion_graph(mode="batch")
        result = graph.invoke({"paths": [str(tmp_path)], "mode": "batch"})

        assert len(result.get("chunks", [])) >= 3  # at least one chunk per file


# --- Q&A retriever tool test ---


class TestRetrieveDocumentsTool:
    @patch("llm_pipeline.rag.retriever.get_vectorstore")
    def test_retrieve_returns_formatted_results(self, mock_get_vs):
        from langchain_core.documents import Document

        mock_vs = MagicMock()
        mock_vs.similarity_search.return_value = [
            Document(page_content="chunk 1", metadata={"source": "file.txt"}),
            Document(page_content="chunk 2", metadata={"source": "file.txt"}),
        ]
        mock_get_vs.return_value = mock_vs

        from llm_pipeline.tools.common import retrieve_documents

        result = retrieve_documents.invoke({"query": "test query"})
        assert "[1]" in result
        assert "[2]" in result
        assert "chunk 1" in result

    @patch("llm_pipeline.rag.retriever.get_vectorstore")
    def test_retrieve_no_results(self, mock_get_vs):
        mock_vs = MagicMock()
        mock_vs.similarity_search.return_value = []
        mock_get_vs.return_value = mock_vs

        from llm_pipeline.tools.common import retrieve_documents

        result = retrieve_documents.invoke({"query": "nonexistent"})
        assert "No relevant documents" in result
