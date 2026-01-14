from __future__ import annotations

import asyncio
from typing import Any, Dict, Iterable, List, Optional, Set

import httpx
from langchain_deepseek import ChatDeepSeek
from langchain_groq import ChatGroq
from langchain_nvidia_ai_endpoints import ChatNVIDIA

# Updated import path to core
from src.agent_service.core.config import (
    GROQ_KEY_CYCLE,
    GROQ_API_KEYS,
    GROQ_BASE_URL,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    NVIDIA_API_KEY,
    NVIDIA_BASE_URL,
    MODEL_NAME,
    GROQ_PARAMETER_SPECS_PAYLOAD,
)

# -----------------------------
# LLM factory
# -----------------------------

def get_llm(
    model_name: str = None,  # type: ignore
    openrouter_api_key: str = None,  # type: ignore
    nvidia_api_key: str = None,  # type: ignore
    reasoning_effort: str = None,  # type: ignore
):
    target_model = model_name or MODEL_NAME
    mid = target_model.lower()

    # Resolve Keys
    effective_nvidia_key = nvidia_api_key or NVIDIA_API_KEY
    effective_openrouter_key = openrouter_api_key or OPENROUTER_API_KEY

    # Flags
    has_nv_key = bool(effective_nvidia_key)
    
    # --- DECISION LOGIC ---
    use_nvidia = False
    use_groq = False

    # 1. Check NVIDIA Priority
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

    # 2. Check Groq (Only if not routed to NVIDIA)
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
            temperature=0.0,
            max_tokens=4096,
            streaming=True,
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
            streaming=True,
            temperature=0.0,
            reasoning_format=r_format,
            reasoning_effort=r_effort,
        )

    # 3. Fallback to OpenRouter
    if not effective_openrouter_key:
        raise ValueError("OpenRouter API Key required (Fallthrough)")

    extra_body: Dict[str, Any] = {}
    is_native_reasoning = any(x in mid for x in ["openai/o1", "openai/o3"])
    
    if is_native_reasoning:
        if reasoning_effort:
            extra_body["reasoning_effort"] = reasoning_effort
    else:
        extra_body["reasoning"] = {"enabled": True}

    return ChatDeepSeek(
        model=target_model,
        api_key=effective_openrouter_key,  # type: ignore
        api_base=OPENROUTER_BASE_URL,
        temperature=0.0,
        streaming=True,
        extra_body=extra_body,
    )