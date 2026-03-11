"""FastMCP server — registers all backend tools and serves over streamable-HTTP."""

from mcp.server.fastmcp import FastMCP

from production_mcp.backends import opensearch, postgres, redis, s3

mcp = FastMCP("production-data")

redis.register(mcp)
postgres.register(mcp)
opensearch.register(mcp)
s3.register(mcp)


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
