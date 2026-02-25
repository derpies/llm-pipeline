"""Marshalling graph — classify, fan-out to processors, review, store."""

from langgraph.types import Send
from langgraph.graph import END, START, StateGraph

from llm_pipeline.ingestion.classify import collect_documents
from llm_pipeline.ingestion.state import IngestionState, ProcessedChunk


def _classify(state: IngestionState) -> dict:
    """Classify all input paths into typed DocumentItems."""
    documents, errors = collect_documents(state["paths"])
    return {"documents": documents, "errors": errors}


def _route_to_processors(state: IngestionState) -> list[Send]:
    """Fan-out: emit one Send per document to the appropriate processor node."""
    sends = []
    for doc in state.get("documents", []):
        node_name = f"process_{doc.doc_type}"
        sends.append(Send(node_name, {"document": doc}))
    if not sends:
        return [Send("review", {})]
    return sends


def _make_processor_node(doc_type: str):
    """Create a node function that invokes the processor subgraph for a doc type."""

    def node_fn(state: dict) -> dict:
        from llm_pipeline.ingestion.processors.code import code_processor
        from llm_pipeline.ingestion.processors.csv import csv_processor
        from llm_pipeline.ingestion.processors.image import image_processor
        from llm_pipeline.ingestion.processors.pdf import pdf_processor
        from llm_pipeline.ingestion.processors.txt import txt_processor

        processors = {
            "txt": txt_processor,
            "pdf": pdf_processor,
            "csv": csv_processor,
            "image": image_processor,
            "code": code_processor,
        }
        processor = processors[doc_type]
        result = processor.invoke(state)
        return {
            "chunks": result.get("chunks", []),
            "errors": result.get("errors", []),
        }

    node_fn.__name__ = f"process_{doc_type}"
    return node_fn


def _review(state: IngestionState) -> dict:
    """Review node — in interactive mode this is an interrupt point.

    In batch mode this is a passthrough that auto-approves.
    """
    return {"approved": True}


def _store(state: IngestionState) -> dict:
    """Store approved chunks in ChromaDB."""
    if not state.get("approved", False):
        return {"errors": ["Storage not approved"]}

    chunks: list[ProcessedChunk] = state.get("chunks", [])
    if not chunks:
        return {}

    from langchain_core.documents import Document

    from llm_pipeline.rag.ingest import get_vectorstore

    vectorstore = get_vectorstore()
    docs = [
        Document(page_content=c.content, metadata=c.metadata)
        for c in chunks
    ]
    vectorstore.add_documents(docs)
    return {}


DOC_TYPES = ["txt", "pdf", "csv", "image", "code"]


def build_ingestion_graph(mode: str = "batch"):
    """Construct and compile the ingestion pipeline graph.

    Args:
        mode: "batch" (auto-approve) or "interactive" (interrupt before review).
    """
    graph = StateGraph(IngestionState)

    # Nodes
    graph.add_node("classify", _classify)
    for dt in DOC_TYPES:
        graph.add_node(f"process_{dt}", _make_processor_node(dt))
    graph.add_node("review", _review)
    graph.add_node("store", _store)

    # Edges
    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify",
        _route_to_processors,
        [f"process_{dt}" for dt in DOC_TYPES] + ["review"],
    )
    for dt in DOC_TYPES:
        graph.add_edge(f"process_{dt}", "review")
    graph.add_edge("review", "store")
    graph.add_edge("store", END)

    interrupt = ["review"] if mode == "interactive" else None
    return graph.compile(interrupt_before=interrupt)
