"""Document ingestion — load, chunk, embed, and store in ChromaDB."""

from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from llm_pipeline.config import settings


def get_vectorstore() -> Chroma:
    """Return a ChromaDB vector store instance."""
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=settings.openai_api_key,
    )
    return Chroma(
        collection_name="llm_pipeline",
        embedding_function=embeddings,
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
