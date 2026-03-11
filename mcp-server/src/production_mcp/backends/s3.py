"""S3 backend — production log file and artifact access."""

from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP) -> None:
    @mcp.tool(name="s3__list_buckets")
    def list_buckets() -> str:
        """List available S3 buckets for log and artifact access."""
        return "[OK] [] (stub)"
