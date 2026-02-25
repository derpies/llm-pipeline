"""State schemas for the ingestion pipeline."""

import operator
from typing import Annotated, Literal

from pydantic import BaseModel, Field
from typing_extensions import TypedDict

DocType = Literal["pdf", "csv", "txt", "image", "code"]


class DocumentItem(BaseModel):
    """A single document to be ingested."""

    path: str
    doc_type: DocType
    filename: str = ""


class ProcessedChunk(BaseModel):
    """A chunk produced by a processor, ready for storage."""

    content: str
    metadata: dict = Field(default_factory=dict)


class IngestionState(TypedDict, total=False):
    """Top-level state for the marshalling graph.

    `chunks` and `errors` use operator.add so Send fan-in merges lists.
    """

    paths: list[str]
    documents: list[DocumentItem]
    chunks: Annotated[list[ProcessedChunk], operator.add]
    errors: Annotated[list[str], operator.add]
    mode: Literal["batch", "interactive"]
    approved: bool


class ProcessorState(TypedDict, total=False):
    """State passed to each processor subgraph via Send."""

    document: DocumentItem
    chunks: Annotated[list[ProcessedChunk], operator.add]
    errors: Annotated[list[str], operator.add]
    _raw_docs: list  # internal: carries loaded docs from load → chunk
