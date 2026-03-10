"""retrieve_documents tool."""

from langchain_core.tools import tool

from llm_pipeline.tools.result import ToolStatus, tool_result


@tool
def retrieve_documents(query: str) -> str:
    """Search the knowledge base for documents relevant to the query.

    Use this tool when the user asks about information that may have been
    ingested into the knowledge base.
    """
    from llm_pipeline.rag.retriever import retrieve

    docs = retrieve(query)
    if not docs:
        return tool_result(ToolStatus.EMPTY, "No relevant documents found in the knowledge base.")

    results = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        results.append(f"[{i}] (source: {source})\n{doc.page_content}")
    return tool_result(ToolStatus.OK, "\n\n---\n\n".join(results))
