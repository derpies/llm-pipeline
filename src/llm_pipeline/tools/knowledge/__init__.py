"""Agent tool for querying the knowledge store."""

from llm_pipeline.config import settings
from llm_pipeline.tools.knowledge.retrieve_knowledge import retrieve_knowledge

# --- Tool role declarations for auto-discovery ---
# Conditional: only available to investigators when knowledge store is enabled
TOOL_ROLES = [
    (retrieve_knowledge, ["investigator", "reviewer"] if settings.investigator_use_knowledge_store else []),
]

__all__ = ["retrieve_knowledge", "TOOL_ROLES"]
