"""Auto-discovery agent registry. Scans agents/plugins/ for manifest.py files."""

from __future__ import annotations

import importlib
import logging
import pkgutil

from llm_pipeline.agents.contracts import AgentManifest

logger = logging.getLogger(__name__)

_registry: dict[str, AgentManifest] | None = None


def _discover() -> dict[str, AgentManifest]:
    """Scan agents/plugins/*/manifest.py for AgentManifest instances."""
    import llm_pipeline.agents.plugins as plugins_pkg

    agents: dict[str, AgentManifest] = {}

    for module_info in pkgutil.iter_modules(plugins_pkg.__path__):
        if not module_info.ispkg:
            continue

        name = module_info.name
        try:
            mod = importlib.import_module(f"llm_pipeline.agents.plugins.{name}.manifest")
        except Exception:
            logger.warning("Failed to import agent plugin %s", name, exc_info=True)
            continue

        manifest: AgentManifest | None = getattr(mod, "manifest", None)
        if manifest is None:
            logger.warning("Agent plugin %s has no 'manifest' attribute", name)
            continue

        if not isinstance(manifest, AgentManifest):
            logger.warning("Agent plugin %s manifest is not an AgentManifest", name)
            continue

        agents[manifest.name] = manifest

    return agents


def get_agent(name: str) -> AgentManifest | None:
    """Get a specific agent manifest by name."""
    global _registry
    if _registry is None:
        _registry = _discover()
    return _registry.get(name)


def get_investigation_agents() -> dict[str, AgentManifest]:
    """Get all investigation-type agent manifests."""
    global _registry
    if _registry is None:
        _registry = _discover()
    return {k: v for k, v in _registry.items() if v.agent_type == "investigation"}


def get_pipeline_agents() -> dict[str, AgentManifest]:
    """Get all pipeline-type agent manifests."""
    global _registry
    if _registry is None:
        _registry = _discover()
    return {k: v for k, v in _registry.items() if v.agent_type == "pipeline"}


def list_agents() -> dict[str, AgentManifest]:
    """Get all registered agents."""
    global _registry
    if _registry is None:
        _registry = _discover()
    return dict(_registry)


def reset_registry() -> None:
    """Force re-discovery (for testing)."""
    global _registry
    _registry = None
