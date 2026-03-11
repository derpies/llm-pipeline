# tools/production/

MCP-backed tools that give investigators access to production systems (Redis,
Postgres, OpenSearch, S3) without exposing credentials to the pipeline.

## How it works

The production MCP server (`mcp-server/`) holds all credentials and exposes
narrow, constrained operations as MCP tools. This package is a thin client
adapter that:

1. Connects to the MCP server via streamable-HTTP at import time
2. Fetches the available tool list
3. Wraps each tool as a LangChain `StructuredTool`
4. Declares `TOOL_ROLES` so `registry.py` auto-discovers them

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | MCP client init, TOOL_ROLES declaration |
| `README.md` | This file |

## Configuration

In `.env`:

```
PRODUCTION_MCP_ENABLED=true
PRODUCTION_MCP_URL=http://production-mcp:8000/mcp
```

Disabled by default (`production_mcp_enabled=False`). When disabled, `TOOL_ROLES`
is an empty list and no connection is attempted.

## Adding new production tools

1. Add the tool to the MCP server (`mcp-server/src/production_mcp/backends/`)
2. Add the tool name and role mapping to `TOOL_ROLES` in `__init__.py`
3. The tool naming convention is `backend__verb_noun` (e.g., `redis__get_cache`,
   `postgres__query_delivery_stats`)

## Tool naming convention

`backend__verb_noun` — the double-underscore prefix makes audit logs scannable
by backend and prevents name collisions with pipeline-internal tools.
