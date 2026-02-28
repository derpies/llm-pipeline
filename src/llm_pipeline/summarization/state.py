"""LangGraph state schema for the summarization pipeline."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from llm_pipeline.email_analytics.models import AnalysisReport
from llm_pipeline.summarization.models import GeneratedDocument, SummarizationResult


class SummarizationState(TypedDict, total=False):
    # Input
    report: AnalysisReport
    run_id: str

    # Accumulated from generation nodes (fan-in via operator.add)
    documents: Annotated[list[GeneratedDocument], operator.add]
    errors: Annotated[list[str], operator.add]

    # Output
    result: SummarizationResult
