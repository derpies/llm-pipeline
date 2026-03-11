"""Postgres backend — production delivery database access."""

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool(name="postgres__ping")
    def ping() -> str:
        """Check connectivity to the production Postgres database."""
        return "[OK] connected (stub)"
