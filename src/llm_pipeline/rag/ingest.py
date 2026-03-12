"""Document ingestion — load, chunk, embed, and store in Weaviate."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from langchain_community.document_loaders import TextLoader
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from llm_pipeline.config import settings

logger = logging.getLogger(__name__)

_HUGGINGFACE_DEFAULT_MODEL = "all-MiniLM-L6-v2"
_OPENAI_DEFAULT_MODEL = "text-embedding-3-small"


def get_embeddings() -> Embeddings:
    """Return an embeddings instance based on config."""
    provider = settings.embedding_provider.lower()
    if provider == "huggingface":
        from langchain_huggingface import HuggingFaceEmbeddings

        model_name = settings.embedding_model or _HUGGINGFACE_DEFAULT_MODEL
        return HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": "cpu"},
        )
    elif provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        model = settings.embedding_model or _OPENAI_DEFAULT_MODEL
        return OpenAIEmbeddings(model=model, api_key=settings.openai_api_key)
    else:
        raise ValueError(
            f"Unknown embedding_provider: {provider!r}. Use 'huggingface' or 'openai'."
        )


class WeaviateVectorStore:
    """Thin wrapper around Weaviate providing the add_documents / similarity_search
    interface that the rest of the codebase expects (drop-in for the old ChromaDB store).
    """

    def __init__(self, collection_name: str):
        self._collection_name = collection_name
        self._embeddings = get_embeddings()

    def _get_client(self):
        from llm_pipeline.knowledge.store import get_weaviate_client

        return get_weaviate_client()

    def _get_collection(self):
        from llm_pipeline.knowledge.weaviate_schema import ensure_tenant

        client = self._get_client()
        ensure_tenant(client, self._collection_name, "community")
        return client.collections.get(self._collection_name).with_tenant("community")

    def add_documents(self, docs: list[Document]) -> None:
        """Embed and store documents in Weaviate."""
        if not docs:
            return

        collection = self._get_collection()
        texts = [d.page_content for d in docs]
        vectors = self._embeddings.embed_documents(texts)

        for doc, vector in zip(docs, vectors):
            props = {
                "statement": doc.page_content,
                "source": doc.metadata.get("source", ""),
            }
            # Copy relevant metadata
            for key in ("title", "document_type", "run_id", "chunk_index", "chunk_total"):
                if key in doc.metadata:
                    props[key] = doc.metadata[key]

            collection.data.insert(
                properties=props,
                vector=vector,
                uuid=uuid.uuid4(),
            )

        logger.debug("Stored %d documents in Weaviate collection %s", len(docs), self._collection_name)

    def similarity_search(self, query: str, k: int = 4) -> list[Document]:
        """Search for documents similar to the query."""
        vector = self._embeddings.embed_query(query)
        collection = self._get_collection()

        results = collection.query.near_vector(
            near_vector=vector,
            limit=k,
            return_properties=["statement", "source", "title"],
        )

        docs = []
        for obj in results.objects:
            props = obj.properties
            metadata = {}
            if props.get("source"):
                metadata["source"] = props["source"]
            if props.get("title"):
                metadata["title"] = props["title"]
            docs.append(Document(page_content=props.get("statement", ""), metadata=metadata))

        return docs


def get_vectorstore() -> WeaviateVectorStore:
    """Return a Weaviate-backed vector store instance for RAG documents."""
    from llm_pipeline.knowledge.weaviate_schema import RAG_COLLECTION

    return WeaviateVectorStore(RAG_COLLECTION)


def ingest_file(path: str | Path, chunk_size: int = 1000, chunk_overlap: int = 200) -> int:
    """Load a text file, split it, and store chunks in Weaviate.

    Returns the number of chunks stored.
    """
    loader = TextLoader(str(path))
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    chunks = splitter.split_documents(docs)

    vectorstore = get_vectorstore()
    vectorstore.add_documents(chunks)
    return len(chunks)
