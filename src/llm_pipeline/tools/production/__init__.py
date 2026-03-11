"""MCP client adapter — bridges production MCP server tools into the tool registry.

Disabled by default (production_mcp_enabled=False). When enabled, connects to
the MCP server at startup via streamable-HTTP, fetches the tool list, and
declares TOOL_ROLES for auto-discovery.
"""

from llm_pipeline.config import settings

TOOL_ROLES: list = []  # default: disabled, no production tools

if settings.production_mcp_enabled:
    import asyncio

    from langchain_mcp_adapters.client import MultiServerMCPClient

    async def _init():
        async with MultiServerMCPClient(
            {
                "production": {
                    "transport": "streamable_http",
                    "url": settings.production_mcp_url,
                }
            }
        ) as client:
            return await client.get_tools()

    _tools = asyncio.run(_init())
    _by_name = {t.name: t for t in _tools}

    def _get(name):
        return _by_name.get(name)

    TOOL_ROLES = [
        entry
        for entry in [
            (_get("redis__ping"), ["investigator"]),
            (_get("postgres__ping"), ["investigator", "reviewer"]),
            (_get("opensearch__ping"), ["investigator"]),
            (_get("s3__list_buckets"), ["investigator"]),
        ]
        if entry[0] is not None
    ]
