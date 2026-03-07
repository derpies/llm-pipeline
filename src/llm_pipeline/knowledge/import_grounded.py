"""Import grounding corpus markdown files into the Weaviate Grounded tier.

Scans a directory of markdown files, splits them into section-aware chunks,
and stores each chunk as a GroundedEntry in the knowledge store.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from llm_pipeline.knowledge.models import GroundedEntry, KnowledgeScope

logger = logging.getLogger(__name__)


def _extract_heading(content: str) -> str:
    """Extract the first top-level heading (# ...) from markdown content."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped.lstrip("# ").strip()
    return ""


def _split_by_sections(content: str) -> list[tuple[str, str]]:
    """Split markdown content on ## headings.

    Returns a list of (section_title, section_text) tuples.
    Text before the first ## heading is returned with title "".
    """
    # Split on lines that start with ##  (but not ### etc via negative lookahead won't work
    # cleanly — instead, split on lines matching exactly ^## )
    parts = re.split(r"(?m)^(## .+)$", content)

    sections: list[tuple[str, str]] = []
    # parts[0] is text before the first ## heading
    preamble = parts[0].strip()
    if preamble:
        sections.append(("", preamble))

    # After the split, parts alternate: heading, text, heading, text, ...
    for i in range(1, len(parts), 2):
        title = parts[i].lstrip("# ").strip()
        text = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if text:
            sections.append((title, text))

    return sections


def _parse_markdown_file(
    path: Path,
    chunk_size: int = 800,
    chunk_overlap: int = 200,
) -> list[GroundedEntry]:
    """Read a markdown file and return GroundedEntry objects for each chunk.

    Splits by ## sections first, then applies RecursiveCharacterTextSplitter
    within each section to preserve section metadata per chunk.
    """
    content = path.read_text(encoding="utf-8")
    topic = _extract_heading(content)
    filename = path.name

    sections = _split_by_sections(content)
    if not sections:
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    entries: list[GroundedEntry] = []
    for section_title, section_text in sections:
        chunks = splitter.split_text(section_text)
        for chunk in chunks:
            entry = GroundedEntry(
                statement=chunk,
                topic=topic,
                source_document=filename,
                source_section=section_title,
                scope=KnowledgeScope.COMMUNITY,
                confidence=1.0,
            )
            entries.append(entry)

    return entries


def import_grounded_directory(
    path: str | Path,
    chunk_size: int = 800,
    chunk_overlap: int = 200,
    client=None,
) -> dict[str, int]:
    """Import all markdown files from a directory into the Grounded tier.

    Returns {"files": N, "chunks_stored": M, "chunks_merged": K}.
    """
    from llm_pipeline.knowledge.store import store_entry

    directory = Path(path)
    if not directory.is_dir():
        raise ValueError(f"Not a directory: {directory}")

    md_files = sorted(directory.glob("*.md"))
    # Exclude README files
    md_files = [f for f in md_files if f.name.upper() != "README.MD"]

    files_processed = 0
    chunks_stored = 0
    chunks_merged = 0

    for md_file in md_files:
        logger.info("Processing %s", md_file.name)
        entries = _parse_markdown_file(md_file, chunk_size, chunk_overlap)
        for entry in entries:
            try:
                _, was_merged = store_entry(entry, client=client)
                if was_merged:
                    chunks_merged += 1
                else:
                    chunks_stored += 1
            except Exception as e:
                logger.warning("Failed to store chunk from %s: %s", md_file.name, e)
        files_processed += 1

    return {
        "files": files_processed,
        "chunks_stored": chunks_stored,
        "chunks_merged": chunks_merged,
    }
