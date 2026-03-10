"""Auto-discovery tool registry. Scans tools/ for modules with TOOL_ROLES dicts."""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Any

logger = logging.getLogger(__name__)

_registry: dict[str, list] | None = None


def _discover() -> dict[str, list]:
    """Import all modules in llm_pipeline.tools.*, collect TOOL_ROLES.

    Returns a dict mapping role names to lists of tool functions.
    The special role "*" means "available to all roles".
    """
    import llm_pipeline.tools as tools_pkg

    role_index: dict[str, list] = {}

    for module_info in pkgutil.iter_modules(tools_pkg.__path__):
        name = module_info.name
        if name.startswith("_") or name == "registry" or name == "result":
            continue

        try:
            mod = importlib.import_module(f"llm_pipeline.tools.{name}")
        except Exception:
            logger.warning("Failed to import tool module %s", name, exc_info=True)
            continue

        tool_roles: list[tuple[Any, list[str]]] | None = getattr(mod, "TOOL_ROLES", None)
        if tool_roles is None:
            continue

        for tool_fn, roles in tool_roles:
            for role in roles:
                role_index.setdefault(role, []).append(tool_fn)

    return role_index


def get_tools(role: str) -> list:
    """Get all tools for a role. Includes wildcard (*) tools. Deduplicates."""
    global _registry
    if _registry is None:
        _registry = _discover()

    seen_names: set[str] = set()
    result: list = []

    for tool_fn in _registry.get(role, []) + _registry.get("*", []):
        name = getattr(tool_fn, "name", id(tool_fn))
        if name not in seen_names:
            seen_names.add(name)
            result.append(tool_fn)

    return result


def reset_registry() -> None:
    """Force re-discovery (for testing)."""
    global _registry
    _registry = None
