"""LangGraph pipeline for document generation from ML analysis output.

Graph: START → generate_executive_summary    ──→ embed_documents → END
             → generate_anomaly_narratives   ─↗
             → generate_trend_narratives     ─↗
             → generate_dimensional_summaries ↗
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from llm_pipeline.config import settings
from llm_pipeline.email_analytics.models import AnalysisReport
from llm_pipeline.summarization.models import (
    DocumentType,
    GeneratedDocument,
    SummarizationResult,
)
from llm_pipeline.summarization.prompts import (
    ANOMALY_NARRATIVE_PROMPT,
    DIMENSIONAL_SUMMARY_PROMPT,
    EXECUTIVE_SUMMARY_PROMPT,
    TREND_NARRATIVE_PROMPT,
)
from llm_pipeline.summarization.serializers import (
    get_top_dimensions,
    serialize_anomaly_context,
    serialize_dimension_context,
    serialize_executive_digest,
    serialize_trend_context,
)
from llm_pipeline.summarization.state import SummarizationState

logger = logging.getLogger(__name__)


def _get_llm() -> BaseChatModel:
    from llm_pipeline.models.llm import get_llm

    return get_llm()


def _invoke_llm(llm: BaseChatModel, prompt: str) -> str:
    """Invoke the LLM and return the response content as a string."""
    from llm_pipeline.models.token_tracker import get_tracker

    response = llm.invoke(prompt)
    get_tracker().record(response)
    return str(response.content)


def _time_range(report: AnalysisReport) -> tuple[datetime | None, datetime | None]:
    """Extract the min/max time window from report aggregations."""
    if not report.aggregations:
        return None, None
    times = [b.time_window for b in report.aggregations]
    return min(times), max(times)


def _generate_executive_summary(state: SummarizationState) -> dict:
    """Generate a single executive summary document."""
    report = state["report"]
    run_id = state["run_id"]

    try:
        llm = _get_llm()
        digest = serialize_executive_digest(report)
        prompt = EXECUTIVE_SUMMARY_PROMPT.format(digest=digest)
        content = _invoke_llm(llm, prompt)
        t_start, t_end = _time_range(report)

        doc = GeneratedDocument(
            document_type=DocumentType.EXECUTIVE_SUMMARY,
            title=f"Executive Summary — Email Delivery Analysis ({run_id})",
            content=content,
            run_id=run_id,
            time_window_start=t_start,
            time_window_end=t_end,
            generated_at=datetime.now(UTC),
        )
        return {"documents": [doc]}
    except Exception as exc:
        logger.error("Failed to generate executive summary: %s", exc)
        return {"errors": [f"Executive summary failed: {exc}"]}


def _generate_anomaly_narratives(state: SummarizationState) -> dict:
    """Generate one narrative per anomaly (capped)."""
    report = state["report"]
    run_id = state["run_id"]

    if not report.anomalies:
        return {"documents": [], "errors": []}

    max_narratives = settings.summarization_max_narratives

    # Sort by severity (z-score magnitude), cap
    sorted_anomalies = sorted(
        report.anomalies,
        key=lambda a: abs(a.z_score),
        reverse=True,
    )[:max_narratives]

    docs: list[GeneratedDocument] = []
    errors: list[str] = []

    try:
        llm = _get_llm()
    except Exception as exc:
        return {"errors": [f"Anomaly narratives failed — LLM init: {exc}"]}

    for anomaly in sorted_anomalies:
        try:
            context = serialize_anomaly_context(anomaly, report.aggregations)
            prompt = ANOMALY_NARRATIVE_PROMPT.format(anomaly_context=context)
            content = _invoke_llm(llm, prompt)

            doc = GeneratedDocument(
                document_type=DocumentType.ANOMALY_NARRATIVE,
                title=(
                    f"Anomaly: {anomaly.anomaly_type.value} — "
                    f"{anomaly.dimension}={anomaly.dimension_value}"
                ),
                content=content,
                run_id=run_id,
                dimension=anomaly.dimension,
                dimension_value=anomaly.dimension_value,
                severity=anomaly.severity,
                generated_at=datetime.now(UTC),
            )
            docs.append(doc)
        except Exception as exc:
            msg = (
                f"Anomaly narrative failed for "
                f"{anomaly.dimension}={anomaly.dimension_value}: {exc}"
            )
            logger.error(msg)
            errors.append(msg)

    return {"documents": docs, "errors": errors}


def _generate_trend_narratives(state: SummarizationState) -> dict:
    """Generate one narrative per trend (capped)."""
    report = state["report"]
    run_id = state["run_id"]

    if not report.trends:
        return {"documents": [], "errors": []}

    max_narratives = settings.summarization_max_narratives

    sorted_trends = sorted(
        report.trends,
        key=lambda t: abs(t.slope),
        reverse=True,
    )[:max_narratives]

    docs: list[GeneratedDocument] = []
    errors: list[str] = []

    try:
        llm = _get_llm()
    except Exception as exc:
        return {"errors": [f"Trend narratives failed — LLM init: {exc}"]}

    for trend in sorted_trends:
        try:
            context = serialize_trend_context(trend, report.aggregations)
            prompt = TREND_NARRATIVE_PROMPT.format(trend_context=context)
            content = _invoke_llm(llm, prompt)

            doc = GeneratedDocument(
                document_type=DocumentType.TREND_NARRATIVE,
                title=(
                    f"Trend: {trend.direction.value} — "
                    f"{trend.dimension}={trend.dimension_value} ({trend.metric})"
                ),
                content=content,
                run_id=run_id,
                dimension=trend.dimension,
                dimension_value=trend.dimension_value,
                generated_at=datetime.now(UTC),
            )
            docs.append(doc)
        except Exception as exc:
            msg = (
                f"Trend narrative failed for "
                f"{trend.dimension}={trend.dimension_value}: {exc}"
            )
            logger.error(msg)
            errors.append(msg)

    return {"documents": docs, "errors": errors}


def _generate_dimensional_summaries(state: SummarizationState) -> dict:
    """Generate one summary per top-N dimension."""
    report = state["report"]
    run_id = state["run_id"]

    if not report.aggregations:
        return {"documents": [], "errors": []}

    top_n = settings.summarization_top_dimensions
    top_dims = get_top_dimensions(report, top_n=top_n)

    docs: list[GeneratedDocument] = []
    errors: list[str] = []

    try:
        llm = _get_llm()
    except Exception as exc:
        return {"errors": [f"Dimensional summaries failed — LLM init: {exc}"]}

    for dimension, dimension_value in top_dims:
        try:
            context = serialize_dimension_context(
                dimension,
                dimension_value,
                report.aggregations,
                report.anomalies,
                report.trends,
            )
            prompt = DIMENSIONAL_SUMMARY_PROMPT.format(dimension_context=context)
            content = _invoke_llm(llm, prompt)

            t_start, t_end = _time_range(report)
            doc = GeneratedDocument(
                document_type=DocumentType.DIMENSIONAL_SUMMARY,
                title=f"Dimensional Summary: {dimension}={dimension_value}",
                content=content,
                run_id=run_id,
                dimension=dimension,
                dimension_value=dimension_value,
                time_window_start=t_start,
                time_window_end=t_end,
                generated_at=datetime.now(UTC),
            )
            docs.append(doc)
        except Exception as exc:
            msg = (
                f"Dimensional summary failed for "
                f"{dimension}={dimension_value}: {exc}"
            )
            logger.error(msg)
            errors.append(msg)

    return {"documents": docs, "errors": errors}


def _embed_documents(state: SummarizationState) -> dict:
    """Store generated documents in Weaviate and build the result."""
    from llm_pipeline.summarization.embed import store_documents

    docs = state.get("documents", [])
    errors = list(state.get("errors", []))
    run_id = state["run_id"]

    chunks_stored = 0
    if docs:
        try:
            chunks_stored = store_documents(docs)
        except Exception as exc:
            msg = f"Embedding failed: {exc}"
            logger.error(msg)
            errors.append(msg)

    result = SummarizationResult(
        run_id=run_id,
        documents_generated=len(docs),
        chunks_stored=chunks_stored,
        errors=errors,
    )

    return {"result": result}


def build_summarization_graph():
    """Construct and compile the summarization pipeline graph."""
    graph = StateGraph(SummarizationState)

    graph.add_node("generate_executive_summary", _generate_executive_summary)
    graph.add_node("generate_anomaly_narratives", _generate_anomaly_narratives)
    graph.add_node("generate_trend_narratives", _generate_trend_narratives)
    graph.add_node("generate_dimensional_summaries", _generate_dimensional_summaries)
    graph.add_node("embed_documents", _embed_documents)

    # Parallel generation from START
    graph.add_edge(START, "generate_executive_summary")
    graph.add_edge(START, "generate_anomaly_narratives")
    graph.add_edge(START, "generate_trend_narratives")
    graph.add_edge(START, "generate_dimensional_summaries")

    # All generators fan-in to embed
    graph.add_edge("generate_executive_summary", "embed_documents")
    graph.add_edge("generate_anomaly_narratives", "embed_documents")
    graph.add_edge("generate_trend_narratives", "embed_documents")
    graph.add_edge("generate_dimensional_summaries", "embed_documents")

    graph.add_edge("embed_documents", END)

    return graph.compile()
