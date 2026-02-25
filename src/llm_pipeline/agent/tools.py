"""Tool registry and built-in tools for the agent."""

from datetime import UTC, datetime

from langchain_core.tools import tool


@tool
def get_current_datetime() -> str:
    """Get the current date and time in UTC."""
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


@tool
def retrieve_documents(query: str) -> str:
    """Search the knowledge base for documents relevant to the query.

    Use this tool when the user asks about information that may have been
    ingested into the knowledge base.
    """
    from llm_pipeline.rag.retriever import retrieve

    docs = retrieve(query)
    if not docs:
        return "No relevant documents found in the knowledge base."

    results = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        results.append(f"[{i}] (source: {source})\n{doc.page_content}")
    return "\n\n---\n\n".join(results)


# Tool registry — add new tools here
TOOLS: list = [
    get_current_datetime,
    retrieve_documents,
]
