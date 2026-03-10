"""RAG retrieval tools."""

from llm_pipeline.tools.rag.retrieve_documents import retrieve_documents

# --- Tool role declarations for auto-discovery ---
TOOL_ROLES = [
    (retrieve_documents, ["chat"]),
]

__all__ = ["retrieve_documents", "TOOL_ROLES"]
