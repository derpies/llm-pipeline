"""Retriever chain — query Weaviate and return relevant documents."""

from langchain_core.documents import Document

from llm_pipeline.rag.ingest import get_vectorstore


def retrieve(query: str, k: int = 4) -> list[Document]:
    """Search Weaviate for documents similar to the query."""
    vectorstore = get_vectorstore()
    return vectorstore.similarity_search(query, k=k)
