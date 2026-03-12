"""LangGraph state schemas for the HTTP analytics pipeline."""

import operator
from typing import Annotated

from typing_extensions import TypedDict

from llm_pipeline.http_analytics.models import (
    HttpAggregationBucket,
    HttpAnalysisReport,
    HttpAnomalyFinding,
    HttpDataCompleteness,
    HttpTrendFinding,
)


class HttpFileProcessingState(TypedDict, total=False):
    """State for processing a single file via Send."""

    file_path: str
    aggregations: list[HttpAggregationBucket]
    completeness: list[HttpDataCompleteness]
    event_count: int
    errors: list[str]


class HttpAnalyticsState(TypedDict, total=False):
    """Top-level state for the HTTP analytics pipeline.

    Lists use operator.add so fan-out/fan-in merges correctly.
    """

    # Input
    input_path: str
    file_paths: list[str]

    # Accumulated from file processing (fan-in via operator.add)
    aggregations: Annotated[list[HttpAggregationBucket], operator.add]
    completeness: Annotated[list[HttpDataCompleteness], operator.add]
    event_count: Annotated[int, operator.add]
    errors: Annotated[list[str], operator.add]

    # Merged aggregation output (deduplicated across files)
    merged_aggregations: list[HttpAggregationBucket]
    merged_completeness: list[HttpDataCompleteness]

    # Analysis output
    anomalies: list[HttpAnomalyFinding]
    trends: list[HttpTrendFinding]

    # Final report
    report: HttpAnalysisReport
    run_id: str
