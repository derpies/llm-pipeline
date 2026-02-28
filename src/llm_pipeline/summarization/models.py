"""Data models for the summarization pipeline."""

from __future__ import annotations

import enum
from datetime import datetime

from pydantic import BaseModel, Field


class DocumentType(enum.StrEnum):
    EXECUTIVE_SUMMARY = "executive_summary"
    ANOMALY_NARRATIVE = "anomaly_narrative"
    TREND_NARRATIVE = "trend_narrative"
    DIMENSIONAL_SUMMARY = "dimensional_summary"


class GeneratedDocument(BaseModel):
    """A single LLM-generated plain-language document."""

    document_type: DocumentType
    title: str
    content: str
    run_id: str
    dimension: str = ""
    dimension_value: str = ""
    time_window_start: datetime | None = None
    time_window_end: datetime | None = None
    severity: str = ""
    generated_at: datetime

    def to_metadata(self) -> dict:
        """Flat dict suitable for ChromaDB metadata storage."""
        meta: dict = {
            "document_type": self.document_type.value,
            "run_id": self.run_id,
            "source": "summarization",
        }
        if self.dimension:
            meta["dimension"] = self.dimension
        if self.dimension_value:
            meta["dimension_value"] = self.dimension_value
        if self.severity:
            meta["severity"] = self.severity
        if self.time_window_start:
            meta["time_window_start"] = self.time_window_start.isoformat()
        if self.time_window_end:
            meta["time_window_end"] = self.time_window_end.isoformat()
        return meta


class SummarizationResult(BaseModel):
    """Summary of a summarization pipeline run."""

    run_id: str
    documents_generated: int = 0
    chunks_stored: int = 0
    errors: list[str] = Field(default_factory=list)
