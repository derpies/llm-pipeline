"""Memory management for the agent."""

from langgraph.checkpoint.memory import MemorySaver

# In-memory checkpointer for conversation state within a session.
# Swap for a persistent backend (e.g. PostgresSaver) for cross-session memory.
checkpointer = MemorySaver()
