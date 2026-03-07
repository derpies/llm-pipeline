"""Tests for grounding corpus import (knowledge/import_grounded.py)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from llm_pipeline.knowledge.import_grounded import (
    _extract_heading,
    _parse_markdown_file,
    _split_by_sections,
    import_grounded_directory,
)
from llm_pipeline.knowledge.models import KnowledgeScope, KnowledgeTier


# ---------------------------------------------------------------------------
# _extract_heading
# ---------------------------------------------------------------------------


class TestExtractHeading:
    def test_extracts_first_h1(self):
        content = "# SPF (Sender Policy Framework)\n\n## Overview\nSome text."
        assert _extract_heading(content) == "SPF (Sender Policy Framework)"

    def test_ignores_h2(self):
        content = "## Not this one\n# This one\nBody."
        assert _extract_heading(content) == "This one"

    def test_returns_empty_when_no_heading(self):
        content = "Just plain text\nno headings here."
        assert _extract_heading(content) == ""

    def test_strips_whitespace(self):
        content = "#   Padded Heading  \nBody."
        assert _extract_heading(content) == "Padded Heading"


# ---------------------------------------------------------------------------
# _split_by_sections
# ---------------------------------------------------------------------------


class TestSplitBySections:
    def test_splits_on_h2_headings(self):
        content = "# Title\n\nPreamble text.\n\n## Section A\n\nContent A.\n\n## Section B\n\nContent B."
        sections = _split_by_sections(content)

        assert len(sections) == 3
        assert sections[0][0] == ""  # preamble has no section title
        assert "Preamble" in sections[0][1]
        assert sections[1][0] == "Section A"
        assert "Content A" in sections[1][1]
        assert sections[2][0] == "Section B"
        assert "Content B" in sections[2][1]

    def test_no_sections_returns_preamble(self):
        content = "# Title\n\nJust a body with no subsections."
        sections = _split_by_sections(content)
        assert len(sections) == 1
        assert sections[0][0] == ""

    def test_empty_sections_are_skipped(self):
        content = "## Non-empty\n\nHas text.\n\n## Empty\n\n"
        sections = _split_by_sections(content)
        # Empty section has no text after stripping
        assert len(sections) == 1
        assert sections[0][0] == "Non-empty"

    def test_nested_h3_not_split(self):
        content = "## Parent\n\nSome text.\n\n### Child\n\nChild text."
        sections = _split_by_sections(content)
        # h3 should NOT cause a split
        assert len(sections) == 1
        assert sections[0][0] == "Parent"
        assert "Child text" in sections[0][1]


# ---------------------------------------------------------------------------
# _parse_markdown_file
# ---------------------------------------------------------------------------


class TestParseMarkdownFile:
    def test_creates_entries_with_correct_metadata(self, tmp_path):
        md = tmp_path / "KB-01-01-test.md"
        md.write_text("# Test Topic\n\n## First Section\n\nShort content.\n\n## Second Section\n\nMore content.")

        entries = _parse_markdown_file(md, chunk_size=800, chunk_overlap=100)
        assert len(entries) >= 2

        for entry in entries:
            assert entry.tier == KnowledgeTier.GROUNDED
            assert entry.topic == "Test Topic"
            assert entry.source_document == "KB-01-01-test.md"
            assert entry.scope == KnowledgeScope.COMMUNITY
            assert entry.confidence == 1.0

        # Check section metadata
        section_titles = {e.source_section for e in entries}
        assert "First Section" in section_titles
        assert "Second Section" in section_titles

    def test_large_section_gets_chunked(self, tmp_path):
        long_text = "Word " * 500  # ~2500 chars
        md = tmp_path / "long.md"
        md.write_text(f"# Long Doc\n\n## Big Section\n\n{long_text}")

        entries = _parse_markdown_file(md, chunk_size=200, chunk_overlap=50)
        # Filter to just the Big Section entries
        big_entries = [e for e in entries if e.source_section == "Big Section"]
        assert len(big_entries) > 1
        for entry in big_entries:
            assert entry.source_section == "Big Section"

    def test_empty_file_returns_empty(self, tmp_path):
        md = tmp_path / "empty.md"
        md.write_text("")
        entries = _parse_markdown_file(md)
        assert entries == []


# ---------------------------------------------------------------------------
# import_grounded_directory
# ---------------------------------------------------------------------------


class TestImportGroundedDirectory:
    @patch("llm_pipeline.knowledge.store.store_entry")
    def test_imports_files_and_counts(self, mock_store, tmp_path):
        # Create two small markdown files
        (tmp_path / "KB-01.md").write_text("# Topic One\n\n## Section\n\nContent one.")
        (tmp_path / "KB-02.md").write_text("# Topic Two\n\n## Section\n\nContent two.")
        # README should be excluded
        (tmp_path / "README.MD").write_text("# Readme\n\nNot imported.")

        mock_store.return_value = ("some-id", False)

        result = import_grounded_directory(tmp_path, chunk_size=800, chunk_overlap=100)

        assert result["files"] == 2
        assert result["chunks_stored"] >= 2
        assert result["chunks_merged"] == 0
        assert mock_store.call_count >= 2

        # Verify GroundedEntry objects were passed
        for call in mock_store.call_args_list:
            entry = call[0][0]
            assert entry.tier == KnowledgeTier.GROUNDED
            assert entry.confidence == 1.0

    @patch("llm_pipeline.knowledge.store.store_entry")
    def test_counts_merged(self, mock_store, tmp_path):
        (tmp_path / "KB-01.md").write_text("# Topic\n\n## Sec\n\nContent.")
        mock_store.return_value = ("some-id", True)

        result = import_grounded_directory(tmp_path)
        assert result["chunks_merged"] >= 1
        assert result["chunks_stored"] == 0

    def test_raises_on_invalid_path(self):
        with pytest.raises(ValueError, match="Not a directory"):
            import_grounded_directory("/nonexistent/path")

    @patch("llm_pipeline.knowledge.store.store_entry")
    def test_handles_store_failure_gracefully(self, mock_store, tmp_path):
        (tmp_path / "KB-01.md").write_text("# Topic\n\n## Sec\n\nContent.")
        mock_store.side_effect = Exception("Weaviate down")

        # Should not raise — logs warning instead
        result = import_grounded_directory(tmp_path)
        assert result["files"] == 1
        assert result["chunks_stored"] == 0
