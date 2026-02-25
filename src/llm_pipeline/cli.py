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


if __name__ == "__main__":
    app()
