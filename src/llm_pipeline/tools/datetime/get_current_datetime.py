"""get_current_datetime tool."""

from datetime import UTC, datetime

from langchain_core.tools import tool

from llm_pipeline.tools.result import ToolStatus, tool_result


@tool
def get_current_datetime() -> str:
    """Get the current date and time in UTC."""
    return tool_result(ToolStatus.OK, datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"))
