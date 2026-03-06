"""CLI entry point — interactive chat and document ingestion."""

import uuid
from pathlib import Path
from typing import Annotated

import typer
from langchain_core.messages import HumanMessage

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
    setup_logging()

    # Lazy import so startup is fast and config errors surface at use-time
    from llm_pipeline.agents.chat import build_chat_graph

    agent = build_chat_graph()

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

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
    setup_logging()

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
    setup_logging()

    from llm_pipeline.email_analytics.graph import build_email_analytics_graph

    graph = build_email_analytics_graph()
    result = graph.invoke({"input_path": str(path.resolve()), "json_format": json_format})

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
    run_id: Annotated[
        str | None,
        typer.Option("--run-id", "-r", help="Use a previous ML run instead of re-analyzing"),
    ] = None,
) -> None:
    """Run the investigation cycle — ML analysis → agent investigation → findings."""
    setup_logging()

    from llm_pipeline.email_analytics.storage import init_db, load_report

    init_db()

    # Either load existing report or run ML analysis first
    if run_id:
        report = load_report(run_id)
        if not report:
            typer.echo(f"No analysis run found with run_id={run_id}")
            raise typer.Exit(1)
        typer.echo(f"Loaded existing report: {run_id}")
    else:
        from llm_pipeline.email_analytics.graph import build_email_analytics_graph

        typer.echo("Running ML analysis...")
        ml_graph = build_email_analytics_graph()
        ml_result = ml_graph.invoke({
            "input_path": str(path.resolve()),
            "json_format": json_format,
        })
        report = ml_result.get("report")
        if not report:
            typer.echo("ML analysis produced no report.")
            raise typer.Exit(1)
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
        "run_id": report.run_id,
    })

    # Print checkpoint digest
    digest = result.get("checkpoint_digest", "")
    if digest:
        typer.echo(f"\n{digest}")
    else:
        typer.echo("\nInvestigation complete (no digest produced).")

    # Persist results
    from llm_pipeline.agents.storage import store_investigation_results

    findings = result.get("findings", [])
    hypotheses = result.get("hypotheses", [])
    try:
        store_investigation_results(
            run_id=report.run_id,
            findings=findings,
            hypotheses=hypotheses,
            checkpoint_digest=digest,
            iteration_count=result.get("iteration_count", 0),
            started_at=result.get("started_at", report.started_at),
            completed_at=result.get("completed_at"),
        )
        typer.echo(
            f"\nPersisted: {len(findings)} findings, {len(hypotheses)} hypotheses"
        )
    except Exception as e:
        typer.echo(f"\nWarning: failed to persist results: {e}")

    # Store to knowledge hierarchy
    try:
        from llm_pipeline.knowledge.store import store_investigation_to_knowledge

        counts = store_investigation_to_knowledge(
            findings=findings,
            hypotheses=hypotheses,
            run_id=report.run_id,
        )
        typer.echo(
            f"Knowledge store: {counts['stored']} entries stored, "
            f"{counts['merged']} merged"
        )
    except Exception as e:
        typer.echo(f"Warning: failed to store to knowledge hierarchy: {e}")


@app.command()
def summarize(
    run_id: Annotated[str, typer.Argument(help="Run ID of a previous email analytics run")],
) -> None:
    """Generate plain-language documents from a previous email analytics run."""
    setup_logging()

    from llm_pipeline.email_analytics.storage import init_db, load_report

    init_db()
    report = load_report(run_id)
    if not report:
        typer.echo(f"No analysis run found with run_id={run_id}")
        raise typer.Exit(1)

    typer.echo(f"Loaded report {run_id}: {len(report.aggregations)} aggregations, "
               f"{len(report.anomalies)} anomalies, {len(report.trends)} trends")
    _run_summarization(report)


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
    setup_logging()

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
    setup_logging()

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


if __name__ == "__main__":
    app()
