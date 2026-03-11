"""OpenSearch backend — production log search and analytics."""

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool(name="opensearch__ping")
    def ping() -> str:
        """Check connectivity to the production OpenSearch cluster."""
        return "[OK] cluster green (stub)"
