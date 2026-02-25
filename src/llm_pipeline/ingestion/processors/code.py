"""Code file processor — TextLoader + language-aware splitter."""

from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

from llm_pipeline.config import settings
from llm_pipeline.ingestion.processors.base import build_processor_subgraph

EXTENSION_TO_LANGUAGE: dict[str, Language] = {
    ".py": Language.PYTHON,
    ".js": Language.JS,
    ".ts": Language.TS,
    ".rs": Language.RUST,
    ".go": Language.GO,
    ".java": Language.JAVA,
    ".c": Language.C,
    ".cpp": Language.CPP,
    ".h": Language.C,
}


def _load(path: str):
    return TextLoader(path, encoding="utf-8").load()


def _split(docs):
    if not docs:
        return docs
    # Detect language from the source path
    source = docs[0].metadata.get("source", "")
    suffix = Path(source).suffix.lower()
    language = EXTENSION_TO_LANGUAGE.get(suffix)

    if language is not None:
        splitter = RecursiveCharacterTextSplitter.from_language(
            language=language,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
    else:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
    return splitter.split_documents(docs)


code_processor = build_processor_subgraph(_load, _split, "code")
