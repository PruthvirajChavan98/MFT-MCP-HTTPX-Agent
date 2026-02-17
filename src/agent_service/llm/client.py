from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel

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

    api_key = None
    actual_provider = None

    # If provider explicitly specified, use that
    if provider:
        if provider == "openrouter":
            if not openrouter_api_key:
                raise ValueError("OpenRouter provider requires openrouter_api_key")
            api_key = openrouter_api_key
            actual_provider = "openai"  # OpenRouter uses OpenAI compatibility
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
            actual_provider = "openai"
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
    if reasoning_effort and reasoning_effort.lower() not in ("none", "default"):
        kwargs["reasoning_effort"] = reasoning_effort

    # OpenRouter-specific config
    if actual_provider == "openai" and openrouter_api_key:
        kwargs["base_url"] = "https://openrouter.ai/api/v1"

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
    base_url: str = "https://openrouter.ai/api/v1",
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
