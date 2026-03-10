"""CLI entry point — interactive chat and document ingestion."""

import uuid
from pathlib import Path
from typing import Annotated

import typer
from langchain_core.messages import HumanMessage

from llm_pipeline.models.rate_limiter import reset_rate_limiter
from llm_pipeline.models.token_tracker import get_tracker, reset_tracker
from llm_pipeline.utils.logging import setup_logging

app = typer.Typer(help="llm-pipeline: Agentic LLM tool")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Default to chat if no subcommand given."""
    if ctx.invoked_subcommand is None:
        chat()


@app.command()
def chat() -> None:
    """Start an interactive chat session with the agent."""
    run_id = str(uuid.uuid4())
    setup_logging(command="chat", run_id=run_id)

    # Lazy import so startup is fast and config errors surface at use-time
    from llm_pipeline.agents.chat import build_chat_graph

    agent = build_chat_graph()

    config = {"configurable": {"thread_id": run_id}}

    typer.echo("llm-pipeline chat (type 'exit' or Ctrl+C to quit)\n")

    while True:
        try:
            user_input = typer.prompt("you", prompt_suffix="> ")
        except (KeyboardInterrupt, EOFError):
            typer.echo("\nBye!")
            raise typer.Exit()

        if user_input.strip().lower() in ("exit", "quit"):
            typer.echo("Bye!")
            raise typer.Exit()

        result = agent.invoke({"messages": [HumanMessage(content=user_input)]}, config)
        response = result["messages"][-1].content
        typer.echo(f"\nassistant> {response}\n")


@app.command()
def ingest(
    paths: Annotated[list[Path], typer.Argument(help="Files or directories to ingest")],
    interactive: Annotated[
        bool, typer.Option("--interactive", "-i", help="Review before storing")
    ] = False,
) -> None:
    """Ingest documents into the knowledge base."""
    run_id = str(uuid.uuid4())
    setup_logging(command="ingest", run_id=run_id)

    from llm_pipeline.ingestion.graph import build_ingestion_graph

    mode = "interactive" if interactive else "batch"
    graph = build_ingestion_graph(mode=mode)

    str_paths = [str(p.resolve()) for p in paths]
    state = {"paths": str_paths, "mode": mode}

    if interactive:
        # Run until interrupt at review node
        result = graph.invoke(state)

        chunks = result.get("chunks", [])
        errors = result.get("errors", [])

        if errors:
            typer.echo(f"\nErrors ({len(errors)}):")
            for err in errors:
                typer.echo(f"  - {err}")

        typer.echo(f"\nReady to store {len(chunks)} chunks.")
        if chunks:
            approve = typer.confirm("Proceed with storing?", default=True)
            if approve:
                result = graph.invoke(None, result.get("__config__", {}))
                typer.echo("Stored successfully.")
            else:
                typer.echo("Aborted — nothing stored.")
    else:
        result = graph.invoke(state)
        chunks = result.get("chunks", [])
        errors = result.get("errors", [])

        typer.echo(f"\nIngestion complete: {len(chunks)} chunks stored.")
        if errors:
            typer.echo(f"Errors ({len(errors)}):")
            for err in errors:
                typer.echo(f"  - {err}")


@app.command()
def analyze_email(
    path: Annotated[Path, typer.Argument(help="File or directory of email delivery JSON data")],
    json_format: Annotated[
        str,
        typer.Option(
            "--json-format",
            "-f",
            help="JSON format: 'ndjson' (one object per line) or 'concatenated' ({…}{…}{…})",
        ),
    ] = "ndjson",
    summarize: Annotated[
        bool,
        typer.Option("--summarize", "-s", help="Generate plain-language documents after analysis"),
    ] = False,
) -> None:
    """Analyze email delivery data — aggregate, detect anomalies, find trends."""
    run_id = str(uuid.uuid4())
    setup_logging(command="analyze_email", run_id=run_id)
    reset_tracker()
    reset_rate_limiter()

    from llm_pipeline.email_analytics.graph import build_email_analytics_graph

    graph = build_email_analytics_graph()
    result = graph.invoke({
        "input_path": str(path.resolve()),
        "json_format": json_format,
        "run_id": run_id,
    })

    report = result.get("report")
    if not report:
        typer.echo("No report generated.")
        raise typer.Exit(1)

    typer.echo(f"\nEmail Analytics Report (run_id={report.run_id})")
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
                f"({t.metric}: {t.start_value:.4f} → {t.end_value:.4f}, "
                f"R²={t.r_squared:.3f})"
            )

    if report.errors:
        typer.echo(f"\nErrors ({len(report.errors)}):")
        for err in report.errors:
            typer.echo(f"  - {err}")

    if summarize:
        _run_summarization(report)

    tracker = get_tracker()
    if tracker.call_count > 0:
        typer.echo(f"\nLLM spend: {tracker.summary()}")


@app.command()
def investigate(
    path: Annotated[Path, typer.Argument(help="File or directory of email delivery JSON data")],
    json_format: Annotated[
        str,
        typer.Option(
            "--json-format",
            "-f",
            help="JSON format: 'ndjson' or 'concatenated'",
        ),
    ] = "ndjson",
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
        typer.Option("--label", "-l", help="Label for this run (for A/B comparison)"),
    ] = "",
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Use fake LLM responses (no API calls, no cost)"),
    ] = False,
) -> None:
    """Run the investigation cycle — ML analysis → agent investigation → findings."""
    run_id = str(uuid.uuid4())
    setup_logging(command="investigate", run_id=run_id)
    reset_tracker()
    reset_rate_limiter()

    if dry_run:
        from llm_pipeline.config import settings as _settings

        _settings.llm_provider = "dry-run"
        typer.echo("DRY-RUN MODE — no real LLM calls will be made")

    # Apply knowledge store toggle
    if no_knowledge:
        from llm_pipeline.config import settings

        settings.investigator_use_knowledge_store = False

    from llm_pipeline.email_analytics.storage import init_db, load_report

    init_db()

    # Either load existing report or run ML analysis first
    if ml_run_id:
        report = load_report(ml_run_id)
        if not report:
            typer.echo(f"No analysis run found with ml_run_id={ml_run_id}")
            raise typer.Exit(1)
        typer.echo(f"Loaded existing report: {ml_run_id}")
    else:
        from llm_pipeline.email_analytics.graph import build_email_analytics_graph

        typer.echo("Running ML analysis...")
        ml_graph = build_email_analytics_graph()
        ml_result = ml_graph.invoke({
            "input_path": str(path.resolve()),
            "json_format": json_format,
            "run_id": run_id,
        })
        report = ml_result.get("report")
        if not report:
            typer.echo("ML analysis produced no report.")
            raise typer.Exit(1)
        ml_run_id = run_id  # same execution produced both
        typer.echo(
            f"ML analysis complete: {len(report.anomalies)} anomalies, "
            f"{len(report.trends)} trends"
        )

    # Run the investigation cycle
    from llm_pipeline.agents.graph import build_investigation_graph

    typer.echo("\nStarting investigation cycle...")
    graph = build_investigation_graph()
    result = graph.invoke({
        "ml_report": report,
        "run_id": run_id,
        "ml_run_id": ml_run_id,
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

    # Compute run status
    if dry_run:
        run_status = "dry_run"
    elif findings and all(f.tool_use_failed for f in findings):
        run_status = "failed"
    elif any(f.tool_use_failed for f in findings):
        run_status = "partial"
    else:
        run_status = "success"

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
        )
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

            store_investigation_report(run_id=run_id, report=inv_report)
            json_path, rpt_md_path = write_investigation_report_files(
                run_id=run_id, report=inv_report
            )
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
        )
        filtered = counts.get('filtered', 0)
        parts = [
            f"Knowledge store: {counts['stored']} entries stored",
            f"{counts['merged']} merged",
        ]
        if filtered:
            parts.append(f"{filtered} filtered")
        typer.echo(", ".join(parts))
    except Exception as e:
        typer.echo(f"Warning: failed to store to knowledge hierarchy: {e}")

    typer.echo(f"\nLLM spend: {get_tracker().summary()}")


@app.command()
def summarize(
    run_id: Annotated[str, typer.Argument(help="Run ID of a previous email analytics run")],
) -> None:
    """Generate plain-language documents from a previous email analytics run."""
    summarize_run_id = str(uuid.uuid4())
    setup_logging(command="summarize", run_id=summarize_run_id)
    reset_tracker()
    reset_rate_limiter()

    from llm_pipeline.email_analytics.storage import init_db, load_report

    init_db()
    report = load_report(run_id)
    if not report:
        typer.echo(f"No analysis run found with run_id={run_id}")
        raise typer.Exit(1)

    typer.echo(f"Loaded report {run_id}: {len(report.aggregations)} aggregations, "
               f"{len(report.anomalies)} anomalies, {len(report.trends)} trends")
    _run_summarization(report)
    typer.echo(f"\nLLM spend: {get_tracker().summary()}")


def _run_summarization(report) -> None:
    """Shared helper to run summarization and print results."""
    from llm_pipeline.summarization.graph import build_summarization_graph

    typer.echo("\nGenerating plain-language documents...")
    graph = build_summarization_graph()
    result = graph.invoke({"report": report, "run_id": report.run_id})

    summ_result = result.get("result")
    if summ_result:
        typer.echo("\nSummarization complete:")
        typer.echo(f"  Documents generated: {summ_result.documents_generated}")
        typer.echo(f"  Chunks stored:       {summ_result.chunks_stored}")
        if summ_result.errors:
            typer.echo(f"  Errors ({len(summ_result.errors)}):")
            for err in summ_result.errors:
                typer.echo(f"    - {err}")
    else:
        typer.echo("Summarization produced no result.")


@app.command()
def knowledge(
    query: Annotated[str, typer.Argument(help="Search query for the knowledge store")],
    scope: Annotated[
        str, typer.Option("--scope", "-s", help="Scope: 'community' or 'account'")
    ] = "community",
    account_id: Annotated[
        str, typer.Option("--account-id", "-a", help="Account ID (required for account scope)")
    ] = "",
    top_k: Annotated[int, typer.Option("--top-k", "-k", help="Number of results")] = 10,
) -> None:
    """Search the knowledge store for findings, hypotheses, and truths."""
    setup_logging(command="knowledge")

    from llm_pipeline.knowledge.models import KnowledgeScope
    from llm_pipeline.knowledge.retrieval import retrieve_knowledge

    scope_enum = KnowledgeScope.ACCOUNT if scope == "account" else KnowledgeScope.COMMUNITY
    results = retrieve_knowledge(
        query=query, scope=scope_enum, account_id=account_id, top_k=top_k,
    )

    if not results:
        typer.echo("No results found.")
        raise typer.Exit()

    for i, r in enumerate(results, 1):
        tier = r.tier.value.upper()
        conf = f"{r.confidence:.0%}"
        status = f" [{r.finding_status}]" if r.finding_status else ""
        topic = f" ({r.topic})" if r.topic else ""
        typer.echo(
            f"[{i}] {tier}{status} confidence={conf}{topic} "
            f"score={r.weighted_score:.3f} obs={r.observation_count}"
        )
        typer.echo(f"    {r.statement}")
        typer.echo()


@app.command()
def knowledge_stats() -> None:
    """Show entry counts by tier, scope, and status in the knowledge store."""
    setup_logging(command="knowledge_stats")

    from llm_pipeline.knowledge.models import KnowledgeTier
    from llm_pipeline.knowledge.weaviate_schema import TIER_COLLECTIONS

    try:
        from llm_pipeline.knowledge.store import get_weaviate_client

        client = get_weaviate_client()
    except Exception as e:
        typer.echo(f"Cannot connect to Weaviate: {e}")
        raise typer.Exit(1)

    for tier in KnowledgeTier:
        collection_name = TIER_COLLECTIONS[tier]
        try:
            collection = client.collections.get(collection_name)
            tenants = collection.tenants.get()
            total = 0
            for tenant_name in tenants:
                tenant_coll = collection.with_tenant(tenant_name)
                agg = tenant_coll.aggregate.over_all(total_count=True)
                total += agg.total_count or 0
            typer.echo(f"  {tier.value:12s}: {total:5d} entries across {len(tenants)} tenants")
        except Exception as e:
            typer.echo(f"  {tier.value:12s}: error ({e})")


@app.command()
def knowledge_reset(
    yes: Annotated[
        bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")
    ] = False,
) -> None:
    """Wipe all entries from the knowledge store (hypothesis, finding, truth tiers).

    Does NOT touch the grounded tier. Use this to clear test/junk data and rebuild
    from a fresh investigation run.
    """
    reset_run_id = str(uuid.uuid4())
    setup_logging(command="knowledge_reset", run_id=reset_run_id)

    from llm_pipeline.knowledge.models import KnowledgeTier
    from llm_pipeline.knowledge.weaviate_schema import TIER_COLLECTIONS

    # Grounded tier is excluded — it's imported from external corpus
    tiers_to_clear = [KnowledgeTier.HYPOTHESIS, KnowledgeTier.FINDING, KnowledgeTier.TRUTH]

    if not yes:
        tier_names = ", ".join(t.value for t in tiers_to_clear)
        if not typer.confirm(f"This will delete ALL entries in: {tier_names}. Continue?"):
            typer.echo("Aborted.")
            raise typer.Exit()

    try:
        from llm_pipeline.knowledge.store import get_weaviate_client

        client = get_weaviate_client()
    except Exception as e:
        typer.echo(f"Cannot connect to Weaviate: {e}")
        raise typer.Exit(1)

    for tier in tiers_to_clear:
        collection_name = TIER_COLLECTIONS[tier]
        try:
            collection = client.collections.get(collection_name)
            tenants = collection.tenants.get()
            total = 0
            for tenant_name in tenants:
                tenant_coll = collection.with_tenant(tenant_name)
                # Delete all objects in this tenant
                from weaviate.classes.query import Filter

                result = tenant_coll.data.delete_many(
                    where=Filter.by_property("entry_id").like("*"),
                )
                total += result.successful if hasattr(result, "successful") else 0
            typer.echo(f"  {tier.value}: cleared {total} entries")
        except Exception as e:
            typer.echo(f"  {tier.value}: error ({e})")

    typer.echo("Knowledge store reset complete.")


@app.command()
def import_grounded(
    directory: Annotated[Path, typer.Argument(help="Directory containing markdown files")],
    chunk_size: Annotated[int, typer.Option("--chunk-size", help="Max chunk size in chars")] = 800,
    chunk_overlap: Annotated[int, typer.Option("--chunk-overlap", help="Overlap between chunks")] = 200,
) -> None:
    """Import a grounding corpus directory into the Weaviate Grounded tier."""
    import_run_id = str(uuid.uuid4())
    setup_logging(command="import_grounded", run_id=import_run_id)

    from llm_pipeline.knowledge.import_grounded import import_grounded_directory

    if not directory.is_dir():
        typer.echo(f"Not a directory: {directory}")
        raise typer.Exit(1)

    typer.echo(f"Importing grounding corpus from {directory}...")
    result = import_grounded_directory(
        path=directory,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    typer.echo(
        f"Done: {result['files']} files, "
        f"{result['chunks_stored']} chunks stored, "
        f"{result['chunks_merged']} chunks merged"
    )


@app.command()
def compare_runs(
    run_id_a: Annotated[str, typer.Argument(help="First run ID")],
    run_id_b: Annotated[str, typer.Argument(help="Second run ID (can be same as A when using labels)")],
    label_a: Annotated[str, typer.Option("--label-a", help="Label for run A")] = "",
    label_b: Annotated[str, typer.Option("--label-b", help="Label for run B")] = "",
) -> None:
    """Compare two investigation runs side-by-side."""
    setup_logging(command="compare_runs")

    from llm_pipeline.agents.storage import load_investigation

    a = load_investigation(run_id_a, label=label_a or None)
    b = load_investigation(run_id_b, label=label_b or None)

    if not a:
        typer.echo(f"Run not found: {run_id_a}")
        raise typer.Exit(1)
    if not b:
        typer.echo(f"Run not found: {run_id_b}")
        raise typer.Exit(1)

    typer.echo(_format_comparison(a, b))


def _format_comparison(a: dict, b: dict) -> str:
    """Format a side-by-side comparison of two investigation runs."""
    from llm_pipeline.agents.models import FindingStatus

    lines: list[str] = []

    # --- Warnings about comparability ---
    warnings: list[str] = []
    if a.get("is_dry_run") or b.get("is_dry_run"):
        warnings.append("WARNING: one or both runs are dry-runs")
    if a.get("status") in ("failed", "partial") or b.get("status") in ("failed", "partial"):
        warnings.append(
            f"WARNING: one or both runs have issues "
            f"(A={a.get('status', 'unknown')}, B={b.get('status', 'unknown')})"
        )
    a_ml = a.get("ml_run_id")
    b_ml = b.get("ml_run_id")
    if a_ml and b_ml and a_ml != b_ml:
        warnings.append(f"WARNING: runs used different ML reports (A={a_ml}, B={b_ml})")

    if warnings:
        lines.append("!" * 60)
        lines.append("WARNINGS")
        lines.append("!" * 60)
        for w in warnings:
            lines.append(f"  {w}")
        lines.append("")

    # --- Metadata ---
    lines.append("=" * 60)
    lines.append("INVESTIGATION RUN COMPARISON")
    lines.append("=" * 60)

    for label_key, run in [("A", a), ("B", b)]:
        run_label = run.get("label") or "(no label)"
        run_status = run.get("status", "unknown")
        lines.append(
            f"  Run {label_key}: {run['run_id']}  label={run_label}  "
            f"status={run_status}  iterations={run['iteration_count']}"
        )
    lines.append("")

    # --- Finding counts by status ---
    lines.append("FINDING COUNTS")
    lines.append("-" * 40)

    for status in FindingStatus:
        count_a = sum(1 for f in a["findings"] if f.status == status)
        count_b = sum(1 for f in b["findings"] if f.status == status)
        lines.append(f"  {status.value:14s}  A={count_a:3d}  B={count_b:3d}")

    lines.append(f"  {'TOTAL':14s}  A={len(a['findings']):3d}  B={len(b['findings']):3d}")
    lines.append("")

    # --- Matched findings (by topic_title) ---
    topics_a = {f.topic_title: f for f in a["findings"]}
    topics_b = {f.topic_title: f for f in b["findings"]}
    shared = set(topics_a.keys()) & set(topics_b.keys())
    only_a = set(topics_a.keys()) - shared
    only_b = set(topics_b.keys()) - shared

    if shared:
        lines.append("MATCHED FINDINGS (same topic)")
        lines.append("-" * 40)
        for topic in sorted(shared):
            fa, fb = topics_a[topic], topics_b[topic]
            lines.append(f"  Topic: {topic}")
            lines.append(f"    A [{fa.status.value}]: {fa.statement[:120]}")
            lines.append(f"    B [{fb.status.value}]: {fb.statement[:120]}")
            lines.append("")

    if only_a:
        lines.append("FINDINGS UNIQUE TO A")
        lines.append("-" * 40)
        for topic in sorted(only_a):
            f = topics_a[topic]
            lines.append(f"  [{f.status.value}] {topic}: {f.statement[:120]}")
        lines.append("")

    if only_b:
        lines.append("FINDINGS UNIQUE TO B")
        lines.append("-" * 40)
        for topic in sorted(only_b):
            f = topics_b[topic]
            lines.append(f"  [{f.status.value}] {topic}: {f.statement[:120]}")
        lines.append("")

    # --- Hypothesis counts ---
    lines.append("HYPOTHESIS COUNTS")
    lines.append("-" * 40)
    lines.append(f"  A={len(a['hypotheses']):3d}  B={len(b['hypotheses']):3d}")

    return "\n".join(lines)


@app.command()
def list_investigations(
    run_id: Annotated[
        str | None,
        typer.Option("--run-id", "-r", help="Filter by run ID"),
    ] = None,
) -> None:
    """List investigation runs with key metadata."""
    setup_logging(command="list_investigations")

    from llm_pipeline.agents.storage import list_investigations as _list_investigations
    from llm_pipeline.email_analytics.storage import init_db

    init_db()
    runs = _list_investigations(run_id)

    if not runs:
        typer.echo("No investigation runs found.")
        raise typer.Exit()

    header = (
        f"{'CREATED AT':<20s} {'RUN ID':<38s} {'LABEL':<16s} {'STATUS':<10s} "
        f"{'F':>3s} {'H':>3s} {'ITER':>4s}"
    )
    typer.echo(header)
    typer.echo("-" * 95)
    for r in runs:
        label = r["label"] or "-"
        created = r["created_at"].strftime("%Y-%m-%d %H:%M:%S") if r["created_at"] else "-"
        dry = " [DRY]" if r["is_dry_run"] else ""
        typer.echo(
            f"{created:<20s} {r['run_id']:<38s} {label:<16s} {r['status'] + dry:<10s} "
            f"{r['finding_count']:>3d} {r['hypothesis_count']:>3d} "
            f"{r['iteration_count']:>4d}"
        )


@app.command()
def regenerate_report(
    run_id: Annotated[str, typer.Argument(help="ML/investigation run ID")],
    label: Annotated[
        str,
        typer.Option("--label", "-l", help="Regenerate report for a specific labeled run"),
    ] = "",
    all_labels: Annotated[
        bool,
        typer.Option("--all-labels", help="Regenerate for ALL investigations with this run_id"),
    ] = False,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", "-o", help="Output dir (default output/investigations/)"),
    ] = None,
) -> None:
    """Regenerate structured reports from stored investigation + ML data (no LLM calls)."""
    regen_run_id = str(uuid.uuid4())
    setup_logging(command="regenerate_report", run_id=regen_run_id)

    from llm_pipeline.agents.report_builder import assemble_full_report
    from llm_pipeline.agents.storage import (
        list_investigations as _list_investigations,
    )
    from llm_pipeline.agents.storage import (
        load_investigation,
        store_investigation_report,
        write_investigation_report_files,
    )
    from llm_pipeline.email_analytics.storage import init_db, load_report

    init_db()

    # Determine which investigations to process
    if all_labels:
        investigations = []
        for inv_meta in _list_investigations(run_id):
            inv = load_investigation(run_id, label=inv_meta["label"] or None)
            if inv:
                investigations.append(inv)
        if not investigations:
            typer.echo(f"No investigations found for run_id={run_id}")
            raise typer.Exit(1)
    else:
        inv = load_investigation(run_id, label=label or None)
        if not inv:
            label_msg = f" label={label}" if label else ""
            typer.echo(f"No investigation found for run_id={run_id}{label_msg}")
            raise typer.Exit(1)
        investigations = [inv]

    generated = 0
    for inv in investigations:
        inv_label = inv.get("label", "")
        ml_run_id = inv.get("ml_run_id") or run_id

        # Load ML report
        ml_report = load_report(ml_run_id)
        if not ml_report:
            typer.echo(f"  Skipping label={inv_label or '(none)'}: ML report {ml_run_id} not found")
            continue

        # Parse digest into lines
        digest = inv.get("checkpoint_digest", "")
        digest_lines = digest.splitlines() if digest else None

        # Assemble report
        report = assemble_full_report(
            run_id=run_id,
            ml_run_id=ml_run_id,
            ml_report=ml_report,
            findings=inv["findings"],
            hypotheses=inv["hypotheses"],
            digest_lines=digest_lines,
        )

        # Write files
        json_path, md_path = write_investigation_report_files(
            run_id=run_id,
            report=report,
            output_dir=output_dir,
            label=inv_label,
        )

        # Persist to Postgres
        try:
            store_investigation_report(run_id=run_id, report=report)
        except Exception as e:
            typer.echo(f"  Warning: failed to persist report to Postgres: {e}")

        label_display = f" [{inv_label}]" if inv_label else ""
        typer.echo(f"  Generated{label_display}: {json_path}")
        typer.echo(f"  Generated{label_display}: {md_path}")
        generated += 1

    typer.echo(f"\n{generated} report(s) regenerated.")


if __name__ == "__main__":
    app()
