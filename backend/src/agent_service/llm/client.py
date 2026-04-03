from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel

from src.agent_service.core.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL
from src.agent_service.llm.capabilities import model_supports_reasoning_effort

try:
    from langchain_openrouter import ChatOpenRouter
except Exception:  # pragma: no cover - optional dependency fallback
    ChatOpenRouter = None

log = logging.getLogger("llm_client")


def get_llm(
    model_name: str,
    *,
    provider: Optional[str] = None,
    openrouter_api_key: Optional[str] = None,
    nvidia_api_key: Optional[str] = None,
    groq_api_key: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
) -> BaseChatModel:
    """
    Unified factory with explicit provider selection.
    Priority: explicit provider > key-based inference
    """
    if not model_name:
        raise ValueError("Model name is required.")

    api_key: Optional[str] = None
    actual_provider: Optional[str] = None

    # If provider explicitly specified, use that
    if provider:
        if provider == "openrouter":
            if not openrouter_api_key:
                raise ValueError("OpenRouter provider requires openrouter_api_key")
            api_key = openrouter_api_key
            actual_provider = "openrouter"
        elif provider == "nvidia":
            if not nvidia_api_key:
                raise ValueError("Nvidia provider requires nvidia_api_key")
            api_key = nvidia_api_key
            actual_provider = "nvidia"
        elif provider == "groq":
            if not groq_api_key:
                raise ValueError("Groq provider requires groq_api_key")
            api_key = groq_api_key
            actual_provider = "groq"
        else:
            raise ValueError(f"Unknown provider: {provider}")
    else:
        # Fallback: Priority-based selection from API keys
        if openrouter_api_key and openrouter_api_key.startswith("sk-or-"):
            actual_provider = "openrouter"
            api_key = openrouter_api_key
            log.info("Auto-detected OpenRouter from API key")
        elif nvidia_api_key and nvidia_api_key.startswith("nvapi-"):
            actual_provider = "nvidia"
            api_key = nvidia_api_key
            log.info("Auto-detected Nvidia from API key")
        elif groq_api_key and groq_api_key.startswith("gsk_"):
            actual_provider = "groq"
            api_key = groq_api_key
            log.info("Auto-detected Groq from API key")
        else:
            raise ValueError(
                "No valid API key provided. Required formats:\n"
                "- Groq: gsk_xxx\n"
                "- OpenRouter: sk-or-xxx\n"
                "- Nvidia: nvapi-xxx"
            )

    # Configure kwargs
    kwargs: Dict[str, Any] = {"temperature": temperature}

    if max_tokens:
        kwargs["max_tokens"] = max_tokens

    normalized_reasoning_effort = None
    if reasoning_effort:
        normalized_reasoning_effort = reasoning_effort.strip().lower()

    supports_reasoning_effort = model_supports_reasoning_effort(
        model_name, provider=actual_provider
    )
    has_reasoning = bool(
        supports_reasoning_effort
        and normalized_reasoning_effort
        and normalized_reasoning_effort not in ("none", "default")
    )
    if normalized_reasoning_effort and not supports_reasoning_effort:
        log.info(
            "Ignoring reasoning_effort for model=%s provider=%s because the model does not support it",
            model_name,
            actual_provider,
        )

    # OpenRouter path: prefer ChatOpenRouter when available.
    if actual_provider == "openrouter":
        if ChatOpenRouter is not None:
            openrouter_kwargs: Dict[str, Any] = dict(kwargs)
            if has_reasoning:
                openrouter_kwargs["reasoning"] = {"effort": normalized_reasoning_effort}

            log.info(f"Initializing openrouter with model: {model_name} (ChatOpenRouter)")
            return ChatOpenRouter(
                model=model_name,
                api_key=api_key,
                **openrouter_kwargs,
            )

        # Compatibility fallback for environments missing langchain-openrouter.
        log.warning(
            "langchain-openrouter not available; falling back to OpenAI-compatible adapter."
        )
        actual_provider = "openai"
        kwargs["base_url"] = "https://openrouter.ai/api/v1"
        if has_reasoning:
            model_kwargs: Dict[str, Any] = dict(kwargs.get("model_kwargs") or {})
            model_kwargs.setdefault("reasoning", {"effort": normalized_reasoning_effort})
            kwargs["model_kwargs"] = model_kwargs

    if has_reasoning and actual_provider != "openai":
        kwargs["reasoning_effort"] = normalized_reasoning_effort

    log.info(f"Initializing {actual_provider} with model: {model_name}")

    try:
        return init_chat_model(
            model=model_name, model_provider=actual_provider, api_key=api_key, **kwargs
        )
    except Exception as e:
        log.error(f"Failed to init model {model_name} with provider {actual_provider}: {e}")
        raise


def get_embeddings(
    api_key: str,
    model: str = "openai/text-embedding-3-small",
    base_url: str = OPENROUTER_BASE_URL,
) -> Embeddings:
    """
    Unified embeddings factory using init_embeddings.
    Defaults to OpenRouter (OpenAI-compatible).
    """
    if not api_key:
        raise ValueError("API Key required for embeddings.")

    provider = "openai"

    return init_embeddings(
        model=model,
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        check_embedding_ctx_length=False,
    )


def get_owner_embeddings(
    model: str = "openai/text-embedding-3-small",
    base_url: str = OPENROUTER_BASE_URL,
) -> Embeddings:
    """
    Owner-managed embeddings factory.
    Embedding-backed subsystems intentionally do not honor session/request BYOK keys.
    """
    if not OPENROUTER_API_KEY:
        raise ValueError("Server OpenRouter API key required for embeddings.")
    return get_embeddings(api_key=OPENROUTER_API_KEY, model=model, base_url=base_url)
