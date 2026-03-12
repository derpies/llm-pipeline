"""HTTP analytics domain CLI commands.

These are auto-discovered by the main CLI via the domain manifest.
"""

import uuid
from pathlib import Path
from typing import Annotated

import typer

from llm_pipeline.models.rate_limiter import reset_rate_limiter
from llm_pipeline.models.token_tracker import get_tracker, reset_tracker
from llm_pipeline.utils.logging import setup_logging


def analyze_http(
    path: Annotated[Path, typer.Argument(help="File or directory of HTTP access log JSON data")],
) -> None:
    """Analyze HTTP access logs — aggregate, detect anomalies, find trends."""
    from datetime import UTC, datetime

    run_id = str(uuid.uuid4())
    started_at = datetime.now(UTC)
    setup_logging(command="analyze_http", run_id=run_id)
    reset_tracker()
    reset_rate_limiter()

    from llm_pipeline.http_analytics.graph import build_http_analytics_graph

    graph = build_http_analytics_graph()
    result = graph.invoke({
        "input_path": str(path.resolve()),
        "run_id": run_id,
    })

    report = result.get("report")
    if not report:
        typer.echo("No report generated.")
        raise typer.Exit(1)

    typer.echo(f"\nHTTP Analytics Report (run_id={report.run_id})")
    typer.echo(f"  Files processed: {report.files_processed}")
    typer.echo(f"  Events parsed:   {report.events_parsed}")
    typer.echo(f"  Aggregations:    {len(report.aggregations)}")
    typer.echo(f"  Anomalies:       {len(report.anomalies)}")
    typer.echo(f"  Trends:          {len(report.trends)}")

    if report.anomalies:
        typer.echo("\nAnomalies:")
        for a in report.anomalies:
            typer.echo(
                f"  [{a.severity}] {a.anomaly_type.value}: {a.dimension}={a.dimension_value} "
                f"({a.metric}: {a.current_value:.4f}, baseline: {a.baseline_mean:.4f}, "
                f"z={a.z_score:.2f})"
            )

    if report.trends:
        typer.echo("\nTrends:")
        for t in report.trends:
            typer.echo(
                f"  {t.direction.value}: {t.dimension}={t.dimension_value} "
                f"({t.metric}: {t.start_value:.4f} -> {t.end_value:.4f}, "
                f"R²={t.r_squared:.3f})"
            )

    if report.errors:
        typer.echo(f"\nErrors ({len(report.errors)}):")
        for err in report.errors:
            typer.echo(f"  - {err}")

    # Append manifest entry
    try:
        from llm_pipeline.agents.manifest import append_manifest

        completed_at = datetime.now(UTC)
        summary = (
            f"{len(report.anomalies)} anomalies, {len(report.trends)} trends "
            f"across {report.files_processed} files ({report.events_parsed} events)"
        )
        append_manifest(
            run_id=run_id,
            command="analyze_http",
            source_files=report.source_files,
            started_at=started_at,
            completed_at=completed_at,
            status="success",
            summary=summary,
            cost_usd=0.0,
            output_files=[],
        )
    except Exception as e:
        typer.echo(f"Warning: failed to write manifest: {e}")


def investigate_http(
    path: Annotated[Path, typer.Argument(help="File or directory of HTTP access log JSON data")],
    ml_run_id: Annotated[
        str | None,
        typer.Option("--ml-run-id", "-r", help="Reuse a previous ML run instead of re-analyzing"),
    ] = None,
    no_knowledge: Annotated[
        bool,
        typer.Option("--no-knowledge", help="Disable knowledge store retrieval for investigators"),
    ] = False,
    label: Annotated[
        str,
        typer.Option("--label", "-l", help="Label for this run"),
    ] = "",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Use fake LLM responses (no API calls, no cost)"),
    ] = False,
) -> None:
    """Run the HTTP investigation cycle — ML analysis -> agent investigation -> findings."""
    from datetime import UTC, datetime

    run_id = str(uuid.uuid4())
    inv_started_at = datetime.now(UTC)
    setup_logging(command="investigate_http", run_id=run_id)
    reset_tracker()
    reset_rate_limiter()

    if dry_run:
        from llm_pipeline.config import settings as _settings

        _settings.llm_provider = "dry-run"
        typer.echo("DRY-RUN MODE — no real LLM calls will be made")

    if no_knowledge:
        from llm_pipeline.config import settings

        settings.investigator_use_knowledge_store = False

    from llm_pipeline.models.db import init_db

    init_db()

    # Either load existing report or run ML analysis
    if ml_run_id:
        from llm_pipeline.http_analytics.storage import load_report

        report = load_report(ml_run_id)
        if not report:
            typer.echo(f"No HTTP analysis run found with ml_run_id={ml_run_id}")
            raise typer.Exit(1)
        typer.echo(f"Loaded existing report: {ml_run_id}")
    else:
        from llm_pipeline.http_analytics.graph import build_http_analytics_graph

        typer.echo("Running HTTP ML analysis...")
        ml_graph = build_http_analytics_graph()
        ml_result = ml_graph.invoke({
            "input_path": str(path.resolve()),
            "run_id": run_id,
        })
        report = ml_result.get("report")
        if not report:
            typer.echo("HTTP ML analysis produced no report.")
            raise typer.Exit(1)
        ml_run_id = run_id
        typer.echo(
            f"ML analysis complete: {len(report.anomalies)} anomalies, "
            f"{len(report.trends)} trends"
        )

    # Run the investigation cycle with domain_name set
    from llm_pipeline.agents.graph import build_investigation_graph

    typer.echo("\nStarting investigation cycle...")
    graph = build_investigation_graph()
    result = graph.invoke({
        "ml_report": report,
        "run_id": run_id,
        "ml_run_id": ml_run_id,
        "domain_name": "http_analytics",
    })

    # Print checkpoint digest
    digest = result.get("checkpoint_digest", "")
    if digest:
        typer.echo(f"\n{digest}")
    else:
        typer.echo("\nInvestigation complete (no digest produced).")

    # Persist results
    from llm_pipeline.agents.storage import (
        store_investigation_results,
        write_investigation_markdown,
    )

    findings = result.get("findings", [])
    hypotheses = result.get("hypotheses", [])
    started_at = result.get("started_at", report.started_at)
    completed_at = result.get("completed_at")
    iteration_count = result.get("iteration_count", 0)

    if dry_run:
        run_status = "dry_run"
    elif findings and all(f.tool_use_failed for f in findings):
        run_status = "failed"
    elif any(f.tool_use_failed for f in findings):
        run_status = "partial"
    else:
        run_status = "success"

    source_files = report.source_files
    output_file_paths: list[str] = []

    try:
        store_investigation_results(
            run_id=run_id,
            findings=findings,
            hypotheses=hypotheses,
            checkpoint_digest=digest,
            iteration_count=iteration_count,
            started_at=started_at,
            completed_at=completed_at,
            label=label,
            status=run_status,
            is_dry_run=dry_run,
            ml_run_id=ml_run_id,
            source_files=source_files,
            domain_name="http_analytics",
        )
        typer.echo(
            f"\nPersisted [{run_status}]: {len(findings)} findings, "
            f"{len(hypotheses)} hypotheses"
        )
    except Exception as e:
        typer.echo(f"\nWarning: failed to persist results: {e}")

    # Write human-readable markdown
    try:
        md_path = write_investigation_markdown(
            run_id=run_id,
            findings=findings,
            hypotheses=hypotheses,
            checkpoint_digest=digest,
            iteration_count=iteration_count,
            started_at=started_at,
            completed_at=completed_at,
            label=label,
            spend_summary=get_tracker().summary(),
            status=run_status,
            is_dry_run=dry_run,
            source_files=source_files,
        )
        output_file_paths.append(str(md_path))
        typer.echo(f"Report: {md_path}")
    except Exception as e:
        typer.echo(f"Warning: failed to write markdown report: {e}")

    # Write structured report
    inv_report = result.get("report")
    if inv_report:
        try:
            from llm_pipeline.agents.storage import (
                store_investigation_report,
                write_investigation_report_files,
            )

            store_investigation_report(run_id=run_id, report=inv_report, domain_name="http_analytics")
            json_path, rpt_md_path = write_investigation_report_files(
                run_id=run_id, report=inv_report, domain_name="http_analytics"
            )
            output_file_paths.append(str(json_path))
            output_file_paths.append(str(rpt_md_path))
            typer.echo(f"Structured report: {json_path}")
            typer.echo(f"Structured report: {rpt_md_path}")
        except Exception as e:
            typer.echo(f"Warning: failed to write structured report: {e}")

    # Store to knowledge hierarchy
    try:
        from llm_pipeline.knowledge.store import store_investigation_to_knowledge

        counts = store_investigation_to_knowledge(
            findings=findings,
            hypotheses=hypotheses,
            run_id=run_id,
            domain_name="http_analytics",
        )
        filtered = counts.get("filtered", 0)
        parts = [
            f"Knowledge store: {counts['stored']} entries stored",
            f"{counts['merged']} merged",
        ]
        if filtered:
            parts.append(f"{filtered} filtered")
        typer.echo(", ".join(parts))
    except Exception as e:
        typer.echo(f"Warning: failed to store to knowledge hierarchy: {e}")

    # Append manifest entry
    try:
        from llm_pipeline.agents.manifest import append_manifest

        inv_completed_at = datetime.now(UTC)
        tracker = get_tracker()

        confirmed = [f for f in findings if f.status.value == "confirmed"]
        top_finding = confirmed[0].statement[:80] if confirmed else ""
        manifest_summary = f"{len(confirmed)} confirmed, {len(hypotheses)} hypotheses"
        if top_finding:
            manifest_summary += f" — {top_finding}"

        append_manifest(
            run_id=run_id,
            command="investigate_http",
            source_files=source_files,
            started_at=inv_started_at,
            completed_at=inv_completed_at,
            status=run_status,
            summary=manifest_summary,
            cost_usd=tracker.total_cost_usd,
            output_files=output_file_paths,
            label=label,
            ml_run_id=ml_run_id or "",
        )
    except Exception as e:
        typer.echo(f"Warning: failed to write manifest: {e}")

    typer.echo(f"\nLLM spend: {get_tracker().summary()}")


# Commands to register on the main CLI app
DOMAIN_CLI_COMMANDS = [
    ("analyze-http", analyze_http),
    ("investigate-http", investigate_http),
]
