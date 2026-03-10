# rag/

Retrieval-Augmented Generation infrastructure. Handles document embedding, vector store management, and similarity search via Weaviate.

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Package marker |
| `ingest.py` | `get_embeddings()` (HuggingFace or OpenAI), `get_vectorstore()` (Weaviate), `ingest_documents()`, `ingest_from_file()`. Handles chunking via RecursiveCharacterTextSplitter |
| `retriever.py` | `retrieve(query, k)` — similarity search wrapper around the vector store |

## Contracts

- **Imports from**: `config` (embedding provider, Weaviate URL, chunk sizes)
- **Exports**: `get_embeddings()`, `get_vectorstore()`, `ingest_documents()`, `retrieve()`
- **Consumed by**: `tools/rag/` (LLM-callable retrieval), `ingestion/` (document storage), `summarization/embed.py` (generated document storage)
