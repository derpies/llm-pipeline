"""Domain registry — auto-discovers domain manifests.

Parallel to the agent registry pattern. Scans domains/*/manifest.py
for DomainManifest instances.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil

from llm_pipeline.agents.contracts import DomainManifest, RoleDefinition

logger = logging.getLogger(__name__)

_cached_manifests: dict[str, DomainManifest] | None = None


def _discover_domains() -> dict[str, DomainManifest]:
    """Scan llm_pipeline.domains.*/manifest.py for DomainManifest instances."""
    manifests: dict[str, DomainManifest] = {}

    try:
        import llm_pipeline.domains as domains_pkg
    except ImportError:
        logger.debug("No llm_pipeline.domains package found")
        return manifests

    for importer, modname, ispkg in pkgutil.iter_modules(
        domains_pkg.__path__, prefix="llm_pipeline.domains."
    ):
        if not ispkg:
            continue
        manifest_mod_name = f"{modname}.manifest"
        try:
            mod = importlib.import_module(manifest_mod_name)
        except ImportError:
            logger.debug("No manifest in %s", modname)
            continue

        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if isinstance(obj, DomainManifest):
                manifests[obj.name] = obj
                logger.info("Discovered domain: %s", obj.name)

    return manifests


def get_all_domains() -> dict[str, DomainManifest]:
    """Return all discovered domain manifests (cached)."""
    global _cached_manifests
    if _cached_manifests is None:
        _cached_manifests = _discover_domains()
    return _cached_manifests


def get_active_domain() -> DomainManifest | None:
    """Return the active domain manifest.

    For now returns the single discovered domain. When multiple domains
    exist, this will be config-selectable.
    """
    domains = get_all_domains()
    if not domains:
        return None
    # Return the first (and currently only) domain
    return next(iter(domains.values()))


def get_domain_roles() -> dict[str, RoleDefinition]:
    """Convenience: return roles from the active domain as a dict keyed by name."""
    domain = get_active_domain()
    if domain is None:
        return {}
    return {r.name: r for r in domain.roles}
