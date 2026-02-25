"""Extension-based document classification — no LLM needed."""

from pathlib import Path

from llm_pipeline.ingestion.state import DocType, DocumentItem

EXTENSION_MAP: dict[str, DocType] = {
    ".pdf": "pdf",
    ".csv": "csv",
    ".txt": "txt",
    ".md": "txt",
    ".rst": "txt",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".webp": "image",
    ".py": "code",
    ".js": "code",
    ".ts": "code",
    ".rs": "code",
    ".go": "code",
    ".java": "code",
    ".c": "code",
    ".cpp": "code",
    ".h": "code",
}


def classify_path(path: Path) -> DocType | None:
    """Return the document type for a file path, or None if unsupported."""
    return EXTENSION_MAP.get(path.suffix.lower())


def collect_documents(paths: list[str]) -> tuple[list[DocumentItem], list[str]]:
    """Walk paths (files or directories), classify each file.

    Returns (documents, errors) where errors lists skipped/unsupported files.
    """
    documents: list[DocumentItem] = []
    errors: list[str] = []

    for raw_path in paths:
        p = Path(raw_path)
        if not p.exists():
            errors.append(f"Path not found: {raw_path}")
            continue

        file_iter = p.rglob("*") if p.is_dir() else [p]
        for fp in file_iter:
            if not fp.is_file():
                continue
            # Skip hidden files and directories
            if any(part.startswith(".") for part in fp.parts):
                continue

            doc_type = classify_path(fp)
            if doc_type is None:
                errors.append(f"Unsupported file type: {fp}")
                continue

            documents.append(
                DocumentItem(
                    path=str(fp.resolve()),
                    doc_type=doc_type,
                    filename=fp.name,
                )
            )

    return documents, errors
