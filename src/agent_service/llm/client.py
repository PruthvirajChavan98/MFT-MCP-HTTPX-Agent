from __future__ import annotations

from typing import Any, Dict, Optional

from langchain_deepseek import ChatDeepSeek
from langchain_groq import ChatGroq
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_openai import OpenAIEmbeddings

from src.agent_service.core.config import (
    GROQ_KEY_CYCLE,
    GROQ_API_KEYS,
    GROQ_BASE_URL,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_SITE_URL,
    OPENROUTER_APP_TITLE,
    OPENROUTER_EMBED_MODEL_DEFAULT,
    NVIDIA_API_KEY,
    NVIDIA_BASE_URL,
    MODEL_NAME,
)


def _openrouter_headers() -> Optional[Dict[str, str]]:
    h: Dict[str, str] = {}
    if OPENROUTER_SITE_URL:
        h["HTTP-Referer"] = OPENROUTER_SITE_URL
    if OPENROUTER_APP_TITLE:
        h["X-Title"] = OPENROUTER_APP_TITLE
    return h or None


def get_openrouter_embeddings(
    openrouter_api_key: Optional[str] = None,
    *,
    model: Optional[str] = None,
) -> OpenAIEmbeddings:
    """
    OpenRouter embeddings live at POST /embeddings under base_url=https://openrouter.ai/api/v1.
    """
    key = (openrouter_api_key or OPENROUTER_API_KEY or "").strip()
    if not key:
        raise ValueError("OpenRouter API Key required for embeddings")

    return OpenAIEmbeddings(
        model=(model or OPENROUTER_EMBED_MODEL_DEFAULT),
        api_key=key,  # type: ignore
        base_url=OPENROUTER_BASE_URL,
        default_headers=_openrouter_headers(),
        check_embedding_ctx_length=False,
    )


def get_llm(
    model_name: str = None,  # type: ignore
    openrouter_api_key: str = None,  # type: ignore
    nvidia_api_key: str = None,  # type: ignore
    reasoning_effort: str = None,  # type: ignore
    *,
    streaming: bool = True,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    timeout: int = 60,
):
    target_model = model_name or MODEL_NAME
    mid = target_model.lower()

    # Resolve Keys
    effective_nvidia_key = (nvidia_api_key or NVIDIA_API_KEY or "").strip() or None
    effective_openrouter_key = (openrouter_api_key or OPENROUTER_API_KEY or "").strip() or None

    # Flags
    has_nv_key = bool(effective_nvidia_key)

    # --- DECISION LOGIC ---
    use_nvidia = False
    use_groq = False

    # 1) NVIDIA priority
    if has_nv_key:
        if mid.startswith("nvidia/"):
            use_nvidia = True
        elif "moonshot" in mid:
            use_nvidia = True
        elif "gpt-oss" in mid:
            use_nvidia = True
        elif "deepseek" in mid and "r1" in mid:
            use_nvidia = True
        elif "llama" in mid and "nvidia" in mid:
            use_nvidia = True
        elif nvidia_api_key:
            use_nvidia = True

    # 2) Groq if not NVIDIA
    if not use_nvidia:
        if "/" not in target_model:
            use_groq = True
        elif target_model.startswith("groq/"):
            use_groq = True
        elif not effective_openrouter_key and GROQ_KEY_CYCLE:
            use_groq = True

    # --- INSTANTIATION ---

    if use_nvidia:
        if not effective_nvidia_key:
            raise ValueError("NVIDIA API Key required (BYOK or Server)")

        model_kwargs: Dict[str, Any] = {}
        if reasoning_effort and reasoning_effort not in ["default", "none"]:
            model_kwargs["reasoning_effort"] = reasoning_effort

        return ChatNVIDIA(
            model=target_model,
            api_key=effective_nvidia_key,
            base_url=NVIDIA_BASE_URL,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
            model_kwargs=model_kwargs,
        )

    if use_groq:
        if not GROQ_KEY_CYCLE:
            raise ValueError("No Groq API Keys configured")

        current_api_key = next(GROQ_KEY_CYCLE)

        r_format = None
        r_effort = None
        if "gpt-oss" in mid:
            r_format = "parsed"
            r_effort = reasoning_effort or "medium"
        elif "qwen" in mid:
            r_format = "parsed"
            r_effort = reasoning_effort or "default"
        elif "deepseek" in mid:
            r_format = "raw"

        return ChatGroq(
            api_key=current_api_key,  # type: ignore
            base_url=GROQ_BASE_URL,
            model=target_model,
            streaming=streaming,
            temperature=temperature,
            reasoning_format=r_format,
            reasoning_effort=r_effort,
        )

    # 3) OpenRouter fallback
    if not effective_openrouter_key:
        raise ValueError("OpenRouter API Key required (Fallthrough)")

    extra_body: Dict[str, Any] = {}
    is_native_reasoning = any(x in mid for x in ["openai/o1", "openai/o3"])
    if is_native_reasoning:
        if reasoning_effort:
            extra_body["reasoning_effort"] = reasoning_effort
    else:
        # OpenRouter supports reasoning tokens; enable when streaming UX wants it
        extra_body["reasoning"] = {"enabled": True} if streaming else {"enabled": False}

    return ChatDeepSeek(
        model=target_model,
        api_key=effective_openrouter_key,  # type: ignore
        api_base=OPENROUTER_BASE_URL,
        default_headers=_openrouter_headers(),
        temperature=temperature,
        streaming=streaming,
        timeout=timeout,
        max_retries=2,
        extra_body=extra_body,
    )