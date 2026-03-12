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
    from llm_pipeline.models.db import init_db

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


# ---------------------------------------------------------------------------
# Auto-register commands from plugins and domain manifests
# ---------------------------------------------------------------------------


def _register_plugin_commands() -> None:
    """Auto-register CLI commands from pipeline agent plugins."""
    try:
        from llm_pipeline.agents.registry import get_pipeline_agents

        for name, manifest in get_pipeline_agents().items():
            if manifest.cli_command and manifest.cli_handler:
                app.command(name=manifest.cli_command)(manifest.cli_handler)
    except Exception:
        # Don't crash CLI startup if plugin discovery fails
        pass


def _register_domain_commands() -> None:
    """Auto-register CLI commands from discovered domain manifests."""
    try:
        from llm_pipeline.agents.domain_registry import get_all_domains

        for domain_name, manifest in get_all_domains().items():
            if manifest.cli_commands:
                for cmd_fn in manifest.cli_commands:
                    app.command()(cmd_fn)
    except Exception:
        # Don't crash CLI startup if domain discovery fails
        pass

    # Directly register domain CLI commands
    _domain_cli_modules = [
        "llm_pipeline.domains.email_delivery.cli",
        "llm_pipeline.domains.http_analytics.cli",
    ]
    import importlib

    for mod_path in _domain_cli_modules:
        try:
            mod = importlib.import_module(mod_path)
            for cmd_name, cmd_fn in getattr(mod, "DOMAIN_CLI_COMMANDS", []):
                app.command(name=cmd_name)(cmd_fn)
        except Exception:
            pass


_register_plugin_commands()
_register_domain_commands()


if __name__ == "__main__":
    app()
