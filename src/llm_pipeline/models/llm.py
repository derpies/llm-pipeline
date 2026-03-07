"""LLM provider factory — returns a LangChain chat model based on config."""

from langchain_core.language_models.chat_models import BaseChatModel

from llm_pipeline.config import settings

# Maps agent roles to config field names
_ROLE_MODEL_MAP = {
    "orchestrator": "model_orchestrator",
    "investigator": "model_investigator",
    "investigator_deep": "model_investigator_deep",
    "synthesizer": "model_synthesizer",
    "curator": "model_curator",
}


def get_llm(
    provider: str | None = None,
    model: str | None = None,
    role: str | None = None,
    **kwargs,
) -> BaseChatModel:
    """Create a chat model instance.

    Args:
        provider: "anthropic" or "openai". Defaults to config.
        model: Model name override. Defaults to config.
        role: Agent role for model selection (e.g. "orchestrator", "investigator").
              Overridden by explicit model parameter.
        **kwargs: Passed through to the model constructor.
    """
    provider = provider or settings.llm_provider

    # Resolve model: explicit > role-based > default
    if model is None and role and role in _ROLE_MODEL_MAP:
        model = getattr(settings, _ROLE_MODEL_MAP[role], None)
    model = model or settings.llm_model

    if provider == "dry-run":
        from llm_pipeline.models.dry_run import DryRunChatModel

        return DryRunChatModel(model_name=model, role=role or "")

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
