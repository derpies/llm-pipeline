"""LangGraph state schemas for the email analytics pipeline."""

import operator
from typing import Annotated

from typing_extensions import TypedDict

from llm_pipeline.email_analytics.models import (
    AggregationBucket,
    AnalysisReport,
    AnomalyFinding,
    DataCompleteness,
    TrendFinding,
)


class FileProcessingState(TypedDict, total=False):
    """State for processing a single file via Send."""

    file_path: str
    json_format: str  # "ndjson" or "concatenated"
    aggregations: list[AggregationBucket]
    completeness: list[DataCompleteness]
    event_count: int
    errors: list[str]


class EmailAnalyticsState(TypedDict, total=False):
    """Top-level state for the email analytics pipeline.

    Lists use operator.add so fan-out/fan-in merges correctly.
    Raw events are never accumulated — each file is aggregated in-stream
    and only compact buckets are carried forward.
    """

    # Input
    input_path: str
    json_format: str  # "ndjson" or "concatenated"
    file_paths: list[str]

    # Accumulated from file processing (fan-in via operator.add)
    aggregations: Annotated[list[AggregationBucket], operator.add]
    completeness: Annotated[list[DataCompleteness], operator.add]
    event_count: Annotated[int, operator.add]
    errors: Annotated[list[str], operator.add]

    # Merged aggregation output (deduplicated across files)
    merged_aggregations: list[AggregationBucket]
    merged_completeness: list[DataCompleteness]

    # Analysis output
    anomalies: list[AnomalyFinding]
    trends: list[TrendFinding]

    # Final report
    report: AnalysisReport
    run_id: str
