"""LLM provider factory — returns a LangChain chat model based on config."""

from langchain_core.language_models.chat_models import BaseChatModel

from llm_pipeline.config import settings


def get_llm(
    provider: str | None = None,
    model: str | None = None,
    **kwargs,
) -> BaseChatModel:
    """Create a chat model instance.

    Args:
        provider: "anthropic" or "openai". Defaults to config.
        model: Model name override. Defaults to config.
        **kwargs: Passed through to the model constructor.
    """
    provider = provider or settings.llm_provider
    model = model or settings.llm_model

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            api_key=settings.anthropic_api_key,
            **kwargs,
        )
    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=settings.openai_api_key,
            **kwargs,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
