"""Smoke tests for the chat agent graph."""

from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage


def _mock_llm_response(*args, **kwargs):
    """Return a simple AI message without tool calls."""
    return AIMessage(content="Hello! I'm a test response.")


def test_graph_compiles():
    """The chat agent graph should compile without errors."""
    from llm_pipeline.agents.chat import build_chat_graph

    with patch("llm_pipeline.agents.chat.get_llm") as mock_get_llm:
        mock_model = mock_get_llm.return_value
        mock_model.bind_tools.return_value = mock_model
        mock_model.invoke.return_value = AIMessage(content="test")

        graph = build_chat_graph()
        assert graph is not None


def test_graph_invoke():
    """The chat agent graph should handle a basic message and return a response."""
    from llm_pipeline.agents.chat import build_chat_graph

    with patch("llm_pipeline.agents.chat.get_llm") as mock_get_llm:
        mock_model = mock_get_llm.return_value
        mock_model.bind_tools.return_value = mock_model
        mock_model.invoke.return_value = AIMessage(content="Hi there!")

        graph = build_chat_graph()
        result = graph.invoke(
            {"messages": [HumanMessage(content="Hello")]},
            {"configurable": {"thread_id": "test-thread"}},
        )

        assert len(result["messages"]) == 2
        assert result["messages"][-1].content == "Hi there!"
