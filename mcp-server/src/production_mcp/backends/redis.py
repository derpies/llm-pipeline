"""Redis backend — production cache and pub/sub access."""

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool(name="redis__ping")
    def ping() -> str:
        """Check connectivity to the production Redis cluster."""
        return "[OK] pong (stub)"
