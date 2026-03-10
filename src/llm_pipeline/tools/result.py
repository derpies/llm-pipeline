"""Structured tool result convention — tools self-declare their status."""

from __future__ import annotations

from enum import StrEnum


class ToolStatus(StrEnum):
    OK = "OK"
    EMPTY = "EMPTY"
    ERROR = "ERROR"


def tool_result(status: ToolStatus, content: str) -> str:
    """Prefix a tool return string with its structured status."""
    return f"[{status.value}] {content}"


def parse_tool_status(content: str) -> ToolStatus | None:
    """Extract the status prefix from a tool result string.

    Returns None for unprefixed strings (backward compatibility).
    """
    for s in ToolStatus:
        if content.startswith(f"[{s.value}] "):
            return s
    return None
