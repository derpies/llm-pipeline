"""Store generated documents in ChromaDB via existing RAG infrastructure."""

from __future__ import annotations

import logging

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from llm_pipeline.config import settings
from llm_pipeline.summarization.models import GeneratedDocument

logger = logging.getLogger(__name__)


def documents_to_langchain(docs: list[GeneratedDocument]) -> list[Document]:
    """Convert GeneratedDocument instances to LangChain Documents.

    Short documents (< chunk_size) are stored as single chunks.
    Longer documents are split using RecursiveCharacterTextSplitter.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )

    lc_docs: list[Document] = []
    for doc in docs:
        metadata = doc.to_metadata()
        metadata["title"] = doc.title

        full_text = f"{doc.title}\n\n{doc.content}"

        if len(full_text) <= settings.chunk_size:
            lc_docs.append(Document(page_content=full_text, metadata=metadata))
        else:
            chunks = splitter.split_text(full_text)
            for i, chunk in enumerate(chunks):
                chunk_meta = {**metadata, "chunk_index": i, "chunk_total": len(chunks)}
                lc_docs.append(Document(page_content=chunk, metadata=chunk_meta))

    return lc_docs


def store_documents(docs: list[GeneratedDocument]) -> int:
    """Convert and store generated documents in ChromaDB.

    Returns the number of chunks stored.
    """
    from llm_pipeline.rag.ingest import get_vectorstore

    lc_docs = documents_to_langchain(docs)
    if not lc_docs:
        return 0

    vectorstore = get_vectorstore()
    vectorstore.add_documents(lc_docs)
    logger.info("Stored %d chunks from %d generated documents", len(lc_docs), len(docs))
    return len(lc_docs)
