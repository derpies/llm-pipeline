"""Conversational chat agent — the user-facing interactive agent."""

from langchain_core.messages import SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from llm_pipeline.agents.prompts import CHAT_SYSTEM_PROMPT
from llm_pipeline.models.llm import get_llm
from llm_pipeline.models.token_tracker import get_tracker
from llm_pipeline.tools.common import CHAT_TOOLS


def _should_continue(state: MessagesState) -> str:
    """Route: if the last message has tool calls, execute them; otherwise end."""
    last = state["messages"][-1]
    if last.tool_calls:
        return "tools"
    return END


def _call_model(state: MessagesState) -> dict:
    """Invoke the LLM with the current message history."""
    llm = get_llm().bind_tools(CHAT_TOOLS)
    messages = [SystemMessage(content=CHAT_SYSTEM_PROMPT)] + state["messages"]
    response = llm.invoke(messages)
    get_tracker().record(response)
    return {"messages": [response]}


def build_chat_graph():
    """Construct and compile the chat agent graph."""
    graph = StateGraph(MessagesState)

    graph.add_node("agent", _call_model)
    graph.add_node("tools", ToolNode(CHAT_TOOLS))

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


# Backwards-compatible alias
build_graph = build_chat_graph
