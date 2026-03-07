"""Postgres persistence for email analytics results."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from llm_pipeline.config import settings
from llm_pipeline.email_analytics.models import (
    AggregationBucket,
    AggregationRecord,
    AnalysisReport,
    AnalysisRunRecord,
    AnomalyFinding,
    AnomalyRecord,
    AnomalyType,
    Base,
    DataCompleteness,
    DataCompletenessRecord,
    TrendDirection,
    TrendFinding,
    TrendRecord,
)

logger = logging.getLogger(__name__)

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        url = settings.database_url
        # Ensure we use psycopg3 driver, not the legacy psycopg2
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        _engine = create_engine(url)
    return _engine


def init_db() -> None:
    """Create all tables (email analytics + knowledge audit). Idempotent."""
    import llm_pipeline.knowledge.models  # noqa: F401 — registers KnowledgeAuditRecord with Base

    engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info("Email analytics tables created/verified")


def store_results(report: AnalysisReport) -> None:
    """Persist an analysis report to Postgres."""
    engine = get_engine()

    with Session(engine) as session:
        # Store run record
        run = AnalysisRunRecord(
            run_id=report.run_id,
            started_at=report.started_at,
            completed_at=report.completed_at,
            files_processed=report.files_processed,
            events_parsed=report.events_parsed,
            anomaly_count=len(report.anomalies),
            trend_count=len(report.trends),
            errors=json.dumps(report.errors),
        )
        session.add(run)

        # Store aggregations
        for agg in report.aggregations:
            session.add(
                AggregationRecord(
                    run_id=report.run_id,
                    time_window=agg.time_window,
                    dimension=agg.dimension,
                    dimension_value=agg.dimension_value,
                    total=agg.total,
                    delivered=agg.delivered,
                    bounced=agg.bounced,
                    deferred=agg.deferred,
                    complained=agg.complained,
                    delivery_rate=agg.delivery_rate,
                    bounce_rate=agg.bounce_rate,
                    deferral_rate=agg.deferral_rate,
                    complaint_rate=agg.complaint_rate,
                    pre_edge_latency_mean=agg.pre_edge_latency_mean,
                    pre_edge_latency_p50=agg.pre_edge_latency_p50,
                    pre_edge_latency_p95=agg.pre_edge_latency_p95,
                    delivery_time_mean=agg.delivery_time_mean,
                    delivery_time_p50=agg.delivery_time_p50,
                    delivery_time_p95=agg.delivery_time_p95,
                )
            )

        # Store completeness
        for comp in report.completeness:
            session.add(
                DataCompletenessRecord(
                    run_id=report.run_id,
                    time_window=comp.time_window,
                    dimension=comp.dimension,
                    dimension_value=comp.dimension_value,
                    total_records=comp.total_records,
                    field_name=comp.field_name,
                    zero_count=comp.zero_count,
                    zero_rate=comp.zero_rate,
                )
            )

        # Store anomalies
        for anomaly in report.anomalies:
            session.add(
                AnomalyRecord(
                    run_id=report.run_id,
                    anomaly_type=anomaly.anomaly_type.value,
                    dimension=anomaly.dimension,
                    dimension_value=anomaly.dimension_value,
                    metric=anomaly.metric,
                    current_value=anomaly.current_value,
                    baseline_mean=anomaly.baseline_mean,
                    z_score=anomaly.z_score,
                    severity=anomaly.severity,
                )
            )

        # Store trends
        for trend in report.trends:
            session.add(
                TrendRecord(
                    run_id=report.run_id,
                    direction=trend.direction.value,
                    dimension=trend.dimension,
                    dimension_value=trend.dimension_value,
                    metric=trend.metric,
                    slope=trend.slope,
                    r_squared=trend.r_squared,
                    num_points=trend.num_points,
                    start_value=trend.start_value,
                    end_value=trend.end_value,
                )
            )

        session.commit()
        logger.info(
            "Stored analysis run %s: %d aggregations, %d completeness, %d anomalies, %d trends",
            report.run_id,
            len(report.aggregations),
            len(report.completeness),
            len(report.anomalies),
            len(report.trends),
        )


def load_historical_aggregations(
    lookback_days: int | None = None,
) -> list[AggregationBucket]:
    """Load historical aggregation records for baseline comparison."""
    lookback_days = lookback_days or settings.email_lookback_days
    engine = get_engine()
    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)

    with Session(engine) as session:
        stmt = select(AggregationRecord).where(AggregationRecord.time_window >= cutoff)
        rows = session.execute(stmt).scalars().all()

        return [
            AggregationBucket(
                time_window=row.time_window,
                dimension=row.dimension,
                dimension_value=row.dimension_value,
                total=row.total,
                delivered=row.delivered,
                bounced=row.bounced,
                deferred=row.deferred,
                complained=row.complained,
                delivery_rate=row.delivery_rate,
                bounce_rate=row.bounce_rate,
                deferral_rate=row.deferral_rate,
                complaint_rate=row.complaint_rate,
                pre_edge_latency_mean=getattr(row, "pre_edge_latency_mean", None),
                pre_edge_latency_p50=getattr(row, "pre_edge_latency_p50", None),
                pre_edge_latency_p95=getattr(row, "pre_edge_latency_p95", None),
                delivery_time_mean=getattr(row, "delivery_time_mean", None),
                delivery_time_p50=getattr(row, "delivery_time_p50", None),
                delivery_time_p95=getattr(row, "delivery_time_p95", None),
            )
            for row in rows
        ]


def load_report(run_id: str) -> AnalysisReport | None:
    """Load a complete AnalysisReport from Postgres by run_id."""
    engine = get_engine()

    with Session(engine) as session:
        run = session.execute(
            select(AnalysisRunRecord).where(AnalysisRunRecord.run_id == run_id)
        ).scalar_one_or_none()
        if run is None:
            return None

        agg_rows = session.execute(
            select(AggregationRecord).where(AggregationRecord.run_id == run_id)
        ).scalars().all()

        comp_rows = session.execute(
            select(DataCompletenessRecord).where(DataCompletenessRecord.run_id == run_id)
        ).scalars().all()

        anomaly_rows = session.execute(
            select(AnomalyRecord).where(AnomalyRecord.run_id == run_id)
        ).scalars().all()

        trend_rows = session.execute(
            select(TrendRecord).where(TrendRecord.run_id == run_id)
        ).scalars().all()

        aggregations = [
            AggregationBucket(
                time_window=r.time_window,
                dimension=r.dimension,
                dimension_value=r.dimension_value,
                total=r.total,
                delivered=r.delivered,
                bounced=r.bounced,
                deferred=r.deferred,
                complained=r.complained,
                delivery_rate=r.delivery_rate,
                bounce_rate=r.bounce_rate,
                deferral_rate=r.deferral_rate,
                complaint_rate=r.complaint_rate,
                pre_edge_latency_mean=getattr(r, "pre_edge_latency_mean", None),
                pre_edge_latency_p50=getattr(r, "pre_edge_latency_p50", None),
                pre_edge_latency_p95=getattr(r, "pre_edge_latency_p95", None),
                delivery_time_mean=getattr(r, "delivery_time_mean", None),
                delivery_time_p50=getattr(r, "delivery_time_p50", None),
                delivery_time_p95=getattr(r, "delivery_time_p95", None),
            )
            for r in agg_rows
        ]

        completeness = [
            DataCompleteness(
                time_window=r.time_window,
                dimension=r.dimension,
                dimension_value=r.dimension_value,
                total_records=r.total_records,
                field_name=r.field_name,
                zero_count=r.zero_count,
                zero_rate=r.zero_rate,
            )
            for r in comp_rows
        ]

        anomalies = [
            AnomalyFinding(
                anomaly_type=AnomalyType(r.anomaly_type),
                dimension=r.dimension,
                dimension_value=r.dimension_value,
                metric=r.metric,
                current_value=r.current_value,
                baseline_mean=r.baseline_mean,
                z_score=r.z_score,
                severity=r.severity,
            )
            for r in anomaly_rows
        ]

        trends = [
            TrendFinding(
                direction=TrendDirection(r.direction),
                dimension=r.dimension,
                dimension_value=r.dimension_value,
                metric=r.metric,
                slope=r.slope,
                r_squared=r.r_squared,
                num_points=r.num_points,
                start_value=r.start_value,
                end_value=r.end_value,
            )
            for r in trend_rows
        ]

        errors = json.loads(run.errors) if run.errors else []

        return AnalysisReport(
            run_id=run.run_id,
            started_at=run.started_at,
            completed_at=run.completed_at,
            files_processed=run.files_processed,
            events_parsed=run.events_parsed,
            aggregations=aggregations,
            completeness=completeness,
            anomalies=anomalies,
            trends=trends,
            errors=errors,
        )
