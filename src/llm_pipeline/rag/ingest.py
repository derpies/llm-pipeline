"""Document ingestion — load, chunk, embed, and store in ChromaDB."""

from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from llm_pipeline.config import settings

_HUGGINGFACE_DEFAULT_MODEL = "all-MiniLM-L6-v2"
_OPENAI_DEFAULT_MODEL = "text-embedding-3-small"


def get_embeddings() -> Embeddings:
    """Return an embeddings instance based on config."""
    provider = settings.embedding_provider.lower()
    if provider == "huggingface":
        from langchain_huggingface import HuggingFaceEmbeddings

        model_name = settings.embedding_model or _HUGGINGFACE_DEFAULT_MODEL
        return HuggingFaceEmbeddings(model_name=model_name)
    elif provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        model = settings.embedding_model or _OPENAI_DEFAULT_MODEL
        return OpenAIEmbeddings(model=model, api_key=settings.openai_api_key)
    else:
        raise ValueError(
            f"Unknown embedding_provider: {provider!r}. Use 'huggingface' or 'openai'."
        )


def get_vectorstore() -> Chroma:
    """Return a ChromaDB vector store instance."""
    return Chroma(
        collection_name="llm_pipeline",
        embedding_function=get_embeddings(),
        persist_directory=settings.chroma_persist_dir,
    )


def ingest_file(path: str | Path, chunk_size: int = 1000, chunk_overlap: int = 200) -> int:
    """Load a text file, split it, and store chunks in ChromaDB.

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
