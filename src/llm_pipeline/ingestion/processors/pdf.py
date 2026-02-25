"""PDF processor — PyPDFLoader + recursive character splitter."""

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from llm_pipeline.config import settings
from llm_pipeline.ingestion.processors.base import build_processor_subgraph


def _load(path: str):
    return PyPDFLoader(path).load()


def _split(docs):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    return splitter.split_documents(docs)


pdf_processor = build_processor_subgraph(_load, _split, "pdf")
