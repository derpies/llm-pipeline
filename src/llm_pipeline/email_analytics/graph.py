"""LangGraph pipeline for email delivery analytics.

Graph: discover_files → fan-out(process_file per file)
       → fan-in(merge_aggregations) → parallel(detect_anomalies, detect_trends)
       → store_results
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from langgraph.graph import START, StateGraph
from langgraph.types import Send

from llm_pipeline.email_analytics.models import AnalysisReport
from llm_pipeline.email_analytics.state import EmailAnalyticsState, FileProcessingState

logger = logging.getLogger(__name__)


def _discover(state: EmailAnalyticsState) -> dict:
    """Discover JSON files at the input path."""
    from llm_pipeline.email_analytics.loader import discover_files

    input_path = state["input_path"]
    file_paths = discover_files(input_path)
    run_id = state.get("run_id") or str(uuid.uuid4())
    logger.info("Discovered %d files at %s (run_id=%s)", len(file_paths), input_path, run_id)
    return {"file_paths": file_paths, "run_id": run_id}


def _route_to_files(state: EmailAnalyticsState) -> list[Send]:
    """Fan-out: one Send per file for parallel streaming aggregation."""
    file_paths = state.get("file_paths", [])
    json_format = state.get("json_format")
    if not file_paths:
        return [Send("merge_aggregations", {})]
    return [
        Send("process_file", {"file_path": fp, "json_format": json_format})
        for fp in file_paths
    ]


def _process_file(state: FileProcessingState) -> dict:
    """Stream-aggregate a single file — no raw events in state."""
    from llm_pipeline.email_analytics.aggregator import aggregate_file

    file_path = state["file_path"]
    json_format = state.get("json_format")
    try:
        result = aggregate_file(file_path, json_format=json_format)
    except Exception as exc:
        return {"errors": [f"Failed to process {file_path}: {exc}"], "event_count": 0}

    logger.info(
        "Processed %d events from %s into %d buckets",
        result.event_count, file_path, len(result.buckets),
    )
    return {
        "aggregations": result.buckets,
        "completeness": result.completeness,
        "event_count": result.event_count,
    }


def _merge_aggregations(state: EmailAnalyticsState) -> dict:
    """Deduplicate fan-in concatenated buckets across all files."""
    from llm_pipeline.email_analytics.aggregator import (
        merge_bucket_list,
        merge_completeness,
    )

    raw_buckets = state.get("aggregations", [])
    merged = merge_bucket_list(raw_buckets)

    raw_completeness = state.get("completeness", [])
    merged_comp = merge_completeness(raw_completeness)

    logger.info(
        "Merged %d fan-in buckets into %d unique buckets, %d completeness records",
        len(raw_buckets),
        len(merged),
        len(merged_comp),
    )
    return {"merged_aggregations": merged, "merged_completeness": merged_comp}


def _detect_anomalies(state: EmailAnalyticsState) -> dict:
    """Detect anomalies against historical baselines."""
    from llm_pipeline.email_analytics.anomaly import detect_anomalies

    aggregations = state.get("merged_aggregations", [])
    if not aggregations:
        return {"anomalies": []}

    # Load historical data for baseline comparison
    try:
        from llm_pipeline.email_analytics.storage import load_historical_aggregations

        run_id = state.get("run_id", "")
        historical = load_historical_aggregations(exclude_run_id=run_id)
    except Exception as exc:
        logger.warning("Could not load historical data, skipping anomaly detection: %s", exc)
        return {"anomalies": []}

    anomalies = detect_anomalies(aggregations, historical)
    logger.info("Detected %d anomalies", len(anomalies))
    return {"anomalies": anomalies}


def _detect_trends(state: EmailAnalyticsState) -> dict:
    """Detect trends across time-windowed aggregations."""
    from llm_pipeline.email_analytics.trends import detect_trends

    aggregations = state.get("merged_aggregations", [])
    if not aggregations:
        return {"trends": []}

    trends = detect_trends(aggregations)
    logger.info("Detected %d trends", len(trends))
    return {"trends": trends}


def _store_results(state: EmailAnalyticsState) -> dict:
    """Build the final report and persist to Postgres."""
    file_paths = state.get("file_paths", [])
    report = AnalysisReport(
        run_id=state.get("run_id", "unknown"),
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        files_processed=len(file_paths),
        events_parsed=state.get("event_count", 0),
        source_files=file_paths,
        aggregations=state.get("merged_aggregations", []),
        completeness=state.get("merged_completeness", []),
        anomalies=state.get("anomalies", []),
        trends=state.get("trends", []),
        errors=state.get("errors", []),
    )

    try:
        from llm_pipeline.email_analytics.storage import init_db, store_results

        init_db()
        store_results(report)
    except Exception as exc:
        logger.warning("Failed to store results to Postgres: %s", exc)
        report.errors.append(f"Storage failed: {exc}")

    return {"report": report}


def build_email_analytics_graph():
    """Construct and compile the email analytics pipeline graph."""
    graph = StateGraph(EmailAnalyticsState)

    # Nodes
    graph.add_node("discover", _discover)
    graph.add_node("process_file", _process_file)
    graph.add_node("merge_aggregations", _merge_aggregations)
    graph.add_node("detect_anomalies", _detect_anomalies)
    graph.add_node("detect_trends", _detect_trends)
    graph.add_node("store_results", _store_results)

    # Edges
    graph.add_edge(START, "discover")
    graph.add_conditional_edges(
        "discover",
        _route_to_files,
        ["process_file", "merge_aggregations"],
    )
    graph.add_edge("process_file", "merge_aggregations")
    graph.add_edge("merge_aggregations", "detect_anomalies")
    graph.add_edge("merge_aggregations", "detect_trends")
    graph.add_edge("detect_anomalies", "store_results")
    graph.add_edge("detect_trends", "store_results")

    return graph.compile()
