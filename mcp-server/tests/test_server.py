"""Tests for the MCP server — verify tool registration."""

import sys
from pathlib import Path

# Add src to path so production_mcp is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestServerToolRegistration:
    """Verify that all backend tools register on the FastMCP app."""

    def test_all_tools_registered(self):
        from production_mcp.server import mcp

        # FastMCP stores tools internally; list them via the _tool_manager
        tool_names = list(mcp._tool_manager._tools.keys())

        assert "redis__ping" in tool_names
        assert "postgres__ping" in tool_names
        assert "opensearch__ping" in tool_names
        assert "s3__list_buckets" in tool_names

    def test_expected_tool_count(self):
        from production_mcp.server import mcp

        tool_names = list(mcp._tool_manager._tools.keys())
        assert len(tool_names) == 4
