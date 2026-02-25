"""Processor subgraph factory — shared load → chunk pattern."""

from collections.abc import Callable

from langchain_core.documents import Document
from langgraph.graph import END, START, StateGraph

from llm_pipeline.ingestion.state import ProcessedChunk, ProcessorState


def build_processor_subgraph(
    loader_fn: Callable[[str], list[Document]],
    splitter_fn: Callable[[list[Document]], list[Document]] | None,
    doc_type: str,
) -> StateGraph:
    """Build and compile a processor subgraph.

    Pattern: load → chunk → END (with error handling in load).

    Args:
        loader_fn: Takes a file path, returns LangChain Documents.
        splitter_fn: Takes Documents, returns split Documents. None to skip splitting.
        doc_type: Label for metadata.
    """

    def load(state: ProcessorState) -> dict:
        doc = state["document"]
        try:
            documents = loader_fn(doc.path)
        except Exception as e:
            return {"errors": [f"Failed to load {doc.filename}: {e}"]}
        return {"_raw_docs": documents}

    def check_load(state: ProcessorState) -> str:
        if state.get("errors"):
            return END
        return "chunk"

    def chunk(state: ProcessorState) -> dict:
        raw_docs: list[Document] = state["_raw_docs"]
        doc = state["document"]

        if splitter_fn is not None:
            split_docs = splitter_fn(raw_docs)
        else:
            split_docs = raw_docs

        chunks = [
            ProcessedChunk(
                content=d.page_content,
                metadata={
                    **d.metadata,
                    "source": doc.path,
                    "filename": doc.filename,
                    "doc_type": doc_type,
                },
            )
            for d in split_docs
        ]
        return {"chunks": chunks}

    graph = StateGraph(ProcessorState)
    graph.add_node("load", load)
    graph.add_node("chunk", chunk)

    graph.add_edge(START, "load")
    graph.add_conditional_edges("load", check_load, {"chunk": "chunk", END: END})
    graph.add_edge("chunk", END)

    return graph.compile()
