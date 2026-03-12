"""Postgres persistence for HTTP analytics results."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from llm_pipeline.email_analytics.models import TrendDirection
from llm_pipeline.http_analytics.models import (
    HttpAggregationBucket,
    HttpAggregationRecord,
    HttpAnalysisReport,
    HttpAnalysisRunRecord,
    HttpAnomalyFinding,
    HttpAnomalyRecord,
    HttpAnomalyType,
    HttpDataCompleteness,
    HttpDataCompletenessRecord,
    HttpTrendFinding,
    HttpTrendRecord,
)
from llm_pipeline.models.db import get_engine

logger = logging.getLogger(__name__)


def store_results(report: HttpAnalysisReport) -> None:
    """Persist an HTTP analysis report to Postgres."""
    engine = get_engine()

    with Session(engine) as session:
        run = HttpAnalysisRunRecord(
            run_id=report.run_id,
            started_at=report.started_at,
            completed_at=report.completed_at,
            files_processed=report.files_processed,
            events_parsed=report.events_parsed,
            anomaly_count=len(report.anomalies),
            trend_count=len(report.trends),
            errors=json.dumps(report.errors),
            source_files=json.dumps(report.source_files),
        )
        session.add(run)

        for agg in report.aggregations:
            session.add(
                HttpAggregationRecord(
                    run_id=report.run_id,
                    time_window=agg.time_window,
                    dimension=agg.dimension,
                    dimension_value=agg.dimension_value,
                    total=agg.total,
                    status_2xx=agg.status_2xx,
                    status_3xx=agg.status_3xx,
                    status_4xx=agg.status_4xx,
                    status_5xx=agg.status_5xx,
                    status_679=agg.status_679,
                    status_other=agg.status_other,
                    success_rate=agg.success_rate,
                    client_error_rate=agg.client_error_rate,
                    server_error_rate=agg.server_error_rate,
                    known_content_error_rate=agg.known_content_error_rate,
                    tts_p50=agg.tts_p50,
                    tts_p90=agg.tts_p90,
                    tts_p95=agg.tts_p95,
                    tts_p99=agg.tts_p99,
                    tts_max=agg.tts_max,
                    tts_mean=agg.tts_mean,
                    total_bytes=agg.total_bytes,
                    mean_bytes=agg.mean_bytes,
                    empty_ua_count=agg.empty_ua_count,
                    empty_upstream_count=agg.empty_upstream_count,
                    empty_referrer_count=agg.empty_referrer_count,
                )
            )

        for comp in report.completeness:
            session.add(
                HttpDataCompletenessRecord(
                    run_id=report.run_id,
                    time_window=comp.time_window,
                    dimension=comp.dimension,
                    dimension_value=comp.dimension_value,
                    total_records=comp.total_records,
                    field_name=comp.field_name,
                    empty_count=comp.empty_count,
                    empty_rate=comp.empty_rate,
                )
            )

        for anomaly in report.anomalies:
            session.add(
                HttpAnomalyRecord(
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

        for trend in report.trends:
            session.add(
                HttpTrendRecord(
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
            "Stored HTTP analysis run %s: %d aggregations, %d completeness, "
            "%d anomalies, %d trends",
            report.run_id,
            len(report.aggregations),
            len(report.completeness),
            len(report.anomalies),
            len(report.trends),
        )


def load_historical_aggregations(
    lookback_days: int | None = None,
) -> list[HttpAggregationBucket]:
    """Load historical HTTP aggregation records for baseline comparison."""
    from llm_pipeline.config import settings

    lookback_days = lookback_days or getattr(settings, "http_lookback_days", 7)
    engine = get_engine()
    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)

    with Session(engine) as session:
        stmt = select(HttpAggregationRecord).where(
            HttpAggregationRecord.time_window >= cutoff
        )
        rows = session.execute(stmt).scalars().all()

        return [
            HttpAggregationBucket(
                time_window=row.time_window,
                dimension=row.dimension,
                dimension_value=row.dimension_value,
                total=row.total,
                status_2xx=row.status_2xx,
                status_3xx=row.status_3xx,
                status_4xx=row.status_4xx,
                status_5xx=row.status_5xx,
                status_679=row.status_679,
                status_other=row.status_other,
                success_rate=row.success_rate,
                client_error_rate=row.client_error_rate,
                server_error_rate=row.server_error_rate,
                known_content_error_rate=row.known_content_error_rate,
                tts_p50=row.tts_p50,
                tts_p90=row.tts_p90,
                tts_p95=row.tts_p95,
                tts_p99=row.tts_p99,
                tts_max=row.tts_max,
                tts_mean=row.tts_mean,
                total_bytes=row.total_bytes,
                mean_bytes=row.mean_bytes,
                empty_ua_count=row.empty_ua_count,
                empty_upstream_count=row.empty_upstream_count,
                empty_referrer_count=row.empty_referrer_count,
            )
            for row in rows
        ]


def load_report(run_id: str) -> HttpAnalysisReport | None:
    """Load a complete HttpAnalysisReport from Postgres by run_id."""
    engine = get_engine()

    with Session(engine) as session:
        run = session.execute(
            select(HttpAnalysisRunRecord).where(
                HttpAnalysisRunRecord.run_id == run_id
            )
        ).scalar_one_or_none()
        if run is None:
            return None

        agg_rows = (
            session.execute(
                select(HttpAggregationRecord).where(
                    HttpAggregationRecord.run_id == run_id
                )
            )
            .scalars()
            .all()
        )

        comp_rows = (
            session.execute(
                select(HttpDataCompletenessRecord).where(
                    HttpDataCompletenessRecord.run_id == run_id
                )
            )
            .scalars()
            .all()
        )

        anomaly_rows = (
            session.execute(
                select(HttpAnomalyRecord).where(
                    HttpAnomalyRecord.run_id == run_id
                )
            )
            .scalars()
            .all()
        )

        trend_rows = (
            session.execute(
                select(HttpTrendRecord).where(HttpTrendRecord.run_id == run_id)
            )
            .scalars()
            .all()
        )

        aggregations = [
            HttpAggregationBucket(
                time_window=r.time_window,
                dimension=r.dimension,
                dimension_value=r.dimension_value,
                total=r.total,
                status_2xx=r.status_2xx,
                status_3xx=r.status_3xx,
                status_4xx=r.status_4xx,
                status_5xx=r.status_5xx,
                status_679=r.status_679,
                status_other=r.status_other,
                success_rate=r.success_rate,
                client_error_rate=r.client_error_rate,
                server_error_rate=r.server_error_rate,
                known_content_error_rate=r.known_content_error_rate,
                tts_p50=r.tts_p50,
                tts_p90=r.tts_p90,
                tts_p95=r.tts_p95,
                tts_p99=r.tts_p99,
                tts_max=r.tts_max,
                tts_mean=r.tts_mean,
                total_bytes=r.total_bytes,
                mean_bytes=r.mean_bytes,
                empty_ua_count=r.empty_ua_count,
                empty_upstream_count=r.empty_upstream_count,
                empty_referrer_count=r.empty_referrer_count,
            )
            for r in agg_rows
        ]

        completeness = [
            HttpDataCompleteness(
                time_window=r.time_window,
                dimension=r.dimension,
                dimension_value=r.dimension_value,
                total_records=r.total_records,
                field_name=r.field_name,
                empty_count=r.empty_count,
                empty_rate=r.empty_rate,
            )
            for r in comp_rows
        ]

        anomalies = [
            HttpAnomalyFinding(
                anomaly_type=HttpAnomalyType(r.anomaly_type),
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
            HttpTrendFinding(
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
        source_files = json.loads(getattr(run, "source_files", "[]") or "[]")

        return HttpAnalysisReport(
            run_id=run.run_id,
            started_at=run.started_at,
            completed_at=run.completed_at,
            files_processed=run.files_processed,
            events_parsed=run.events_parsed,
            source_files=source_files,
            aggregations=aggregations,
            completeness=completeness,
            anomalies=anomalies,
            trends=trends,
            errors=errors,
        )
