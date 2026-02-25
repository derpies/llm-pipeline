"""LangGraph agent — the core reasoning loop."""

from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from llm_pipeline.agent.memory import checkpointer
from llm_pipeline.agent.prompts import SYSTEM_PROMPT
from llm_pipeline.agent.tools import TOOLS
from llm_pipeline.models.llm import get_llm


def _should_continue(state: MessagesState) -> str:
    """Route: if the last message has tool calls, execute them; otherwise end."""
    last = state["messages"][-1]
    if last.tool_calls:
        return "tools"
    return END


def _call_model(state: MessagesState) -> dict:
    """Invoke the LLM with the current message history."""
    llm = get_llm().bind_tools(TOOLS)
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}


def build_graph() -> StateGraph:
    """Construct and compile the agent graph."""
    graph = StateGraph(MessagesState)

    graph.add_node("agent", _call_model)
    graph.add_node("tools", ToolNode(TOOLS))

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=checkpointer)


# Singleton compiled graph
agent = build_graph()
