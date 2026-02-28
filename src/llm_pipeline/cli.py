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
    from llm_pipeline.agent.graph import agent

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


if __name__ == "__main__":
    app()
