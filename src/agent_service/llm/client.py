from __future__ import annotations

import logging
from typing import Optional, Dict, Any

from langchain.chat_models import init_chat_model
from langchain.embeddings import init_embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings

log = logging.getLogger("llm_client")

def get_llm(
    model_name: str,
    *,
    openrouter_api_key: Optional[str] = None,
    nvidia_api_key: Optional[str] = None,
    groq_api_key: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
) -> BaseChatModel:
    """
    Unified factory using init_chat_model.
    Supports OpenRouter, Nvidia, Groq, and standard providers via BYOK.
    """
    if not model_name:
        raise ValueError("Model name is required.")

    # Determine provider and key precedence
    provider = None
    api_key = None
    
    # 1. OpenRouter (Explicit or inferred from model name)
    if openrouter_api_key:
        provider = "openai" # OpenRouter is OpenAI-compatible
        api_key = openrouter_api_key
        # Ensure model has openai/ prefix if using OpenRouter
        if "/" not in model_name:
            model_name = f"openai/{model_name}"
    
    # 2. NVIDIA
    elif nvidia_api_key or model_name.startswith("nvidia/"):
        provider = "nvidia" 
        api_key = nvidia_api_key
    
    # 3. Groq
    elif groq_api_key or model_name.startswith("groq/"):
        provider = "groq"
        api_key = groq_api_key

    if not api_key:
        # Strict BYOK: Fail if no key is found for the inferred provider
        raise ValueError(f"No API key provided for model '{model_name}'.")

    # Configure kwargs
    kwargs: Dict[str, Any] = {
        "temperature": temperature,
    }
    
    if max_tokens:
        kwargs["max_tokens"] = max_tokens

    # Reasoning effort mapping
    if reasoning_effort and reasoning_effort.lower() not in ("none", "default"):
        kwargs["reasoning_effort"] = reasoning_effort

    # Specific base URLs if needed (using OpenAI compatibility layer for OpenRouter)
    if openrouter_api_key:
        kwargs["base_url"] = "https://openrouter.ai/api/v1"
        kwargs["model_provider"] = "openai" # Force OpenAI adapter for OpenRouter

    try:
        return init_chat_model(
            model=model_name,
            model_provider=provider,
            api_key=api_key,
            **kwargs
        )
    except Exception as e:
        log.error(f"Failed to init model {model_name}: {e}")
        raise

def get_embeddings(
    api_key: str,
    model: str = "openai/text-embedding-3-small",
    base_url: str = "https://openrouter.ai/api/v1"
) -> Embeddings:
    """
    Unified embeddings factory using init_embeddings.
    Defaults to OpenRouter (OpenAI-compatible).
    """
    if not api_key:
        raise ValueError("API Key required for embeddings.")

    # Detect provider logic
    provider = "openai" 
    
    return init_embeddings(
        model=model,
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        check_embedding_ctx_length=False
    )
