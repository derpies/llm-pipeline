"""Backward-compatibility stub — re-exports from the investigator plugin.

All logic has moved to agents/plugins/investigator/.
This module exists so existing imports continue to work during transition.
"""

from llm_pipeline.agents.plugins.investigator.agent import (  # noqa: F401
    _call_investigator,
    _count_consecutive_non_ok,
    _patch_ml_run_id,
    _should_continue,
    build_investigator_graph,
)
from llm_pipeline.agents.plugins.investigator.extract import (  # noqa: F401
    _extract_results,
)
from llm_pipeline.tools.registry import get_tools

# Legacy aliases for backward compatibility
INVESTIGATOR_BASE_TOOLS = get_tools("investigator")
INVESTIGATOR_TOOLS = INVESTIGATOR_BASE_TOOLS


def _get_investigator_tools() -> list:
    """Build the investigator tool list via the registry."""
    return get_tools("investigator")
