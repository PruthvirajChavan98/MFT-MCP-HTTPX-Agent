import httpx
import asyncio
from typing import List, Dict, Any, Optional

from langchain_groq import ChatGroq
from langchain_deepseek import ChatDeepSeek
from langchain_nvidia_ai_endpoints import ChatNVIDIA

from .config import (
    GROQ_KEY_CYCLE,  # The Round-Robin Iterator
    GROQ_API_KEYS,   # The raw list (for fetching models)
    GROQ_BASE_URL, 
    OPENROUTER_API_KEY, 
    OPENROUTER_BASE_URL,
    NVIDIA_API_KEY,      # <--- NEW
    NVIDIA_BASE_URL,     # <--- NEW
    MODEL_NAME
)

import httpx
from typing import Optional, Any, Dict

from langchain_groq import ChatGroq
from langchain_deepseek import ChatDeepSeek
from langchain_nvidia_ai_endpoints import ChatNVIDIA

from .config import (
    GROQ_KEY_CYCLE, 
    GROQ_BASE_URL, 
    OPENROUTER_API_KEY, 
    OPENROUTER_BASE_URL,
    NVIDIA_API_KEY,      # Server Key
    NVIDIA_BASE_URL,
    MODEL_NAME
)

def get_llm(
    model_name: str = None, # type: ignore
    openrouter_api_key: str = None, # type: ignore
    nvidia_api_key: str = None,  # <--- NEW ARG # type: ignore
    reasoning_effort: str = None # type: ignore
):
    target_model = model_name or MODEL_NAME
    
    # --- 1. KEY RESOLUTION ---
    # User's key takes precedence over Server's key
    effective_nvidia_key = nvidia_api_key or NVIDIA_API_KEY
    effective_openrouter_key = openrouter_api_key or OPENROUTER_API_KEY

    # Flags to determine intent
    has_user_nvidia_key = bool(nvidia_api_key)
    has_user_or_key = bool(openrouter_api_key)
    
    # --- 2. PROVIDER SELECTION ---
    use_nvidia = False
    use_groq = False
    
    # NVIDIA Logic:
    # Use if:
    # A. We have a valid key (User OR Server)
    # B. AND the user isn't explicitly forcing OpenRouter (via a custom OR key)
    # C. AND the model ID looks like an NVIDIA model
    if effective_nvidia_key and not has_user_or_key:
        mid = target_model.lower()
        # Explicit intent (User provided NVIDIA key) -> Trust them
        if has_user_nvidia_key:
             use_nvidia = True
        # Implicit intent (Server key available) -> Check model signature
        elif mid.startswith("nvidia/") or "gpt-oss" in mid:
            use_nvidia = True
        elif "deepseek" in mid and "r1" in mid:
            use_nvidia = True
        elif "openai" in mid and ("o1" in mid or "o3" in mid):
            use_nvidia = True

    # Groq Logic (Fallback if NVIDIA isn't selected)
    if not use_nvidia:
        is_legacy_groq = "/" not in target_model
        if is_legacy_groq:
            use_groq = True
        elif not has_user_or_key and GROQ_KEY_CYCLE and "groq" in target_model.lower():
            use_groq = True

    # --- 3. CLIENT INSTANTIATION ---

    # === OPTION A: NVIDIA ===
    if use_nvidia:
        if not effective_nvidia_key:
             raise ValueError("NVIDIA API Key required (BYOK or Server)")

        model_kwargs = {}
        mid = target_model.lower()
        
        is_reasoning = any(x in mid for x in ["r1", "o1", "o3", "gpt-oss"])
        if reasoning_effort and is_reasoning:
            model_kwargs["reasoning_effort"] = reasoning_effort

        return ChatNVIDIA(
            model=target_model,
            api_key=effective_nvidia_key, # <--- Uses resolved key
            base_url=NVIDIA_BASE_URL,
            temperature=0.6,
            max_tokens=4096,
            streaming=True,
            model_kwargs=model_kwargs
        )

    # === OPTION B: GROQ ===
    elif use_groq:
        if not GROQ_KEY_CYCLE:
             raise ValueError(f"No Groq API Keys configured")

        current_api_key = next(GROQ_KEY_CYCLE)
        
        r_format = None
        r_effort = None
        if "gpt-oss" in target_model:
            r_format = "parsed"
            r_effort = reasoning_effort or "medium"
        elif "qwen" in target_model:
            r_format = "parsed"
            r_effort = "default"
        elif "deepseek" in target_model:
             r_format = "raw"

        return ChatGroq(
            api_key=current_api_key, # type: ignore
            base_url=GROQ_BASE_URL,
            model=target_model,
            streaming=True,
            temperature=0.6,
            reasoning_format=r_format,
            reasoning_effort=r_effort
        )

    # === OPTION C: OPENROUTER ===
    else:
        if not effective_openrouter_key:
            raise ValueError(f"OpenRouter API Key required")

        is_native = any(x in target_model.lower() for x in ["openai/o1", "openai/o3"])
        extra_body = {}
        if is_native:
            if reasoning_effort: extra_body["reasoning_effort"] = reasoning_effort
        else:
            extra_body["reasoning"] = {"enabled": True}

        return ChatDeepSeek(
            model=target_model,
            api_key=effective_openrouter_key, # type: ignore
            api_base=OPENROUTER_BASE_URL,
            temperature=0.6,
            streaming=True,
            extra_body=extra_body
        )

# --- MODEL FETCHING & CACHING UTILITIES ---

def _get_std_params() -> List[Dict[str, Any]]:
    """Standard parameters for most models to populate GraphQL specs."""
    return [
        {"name": "temperature", "type": "float", "min": 0.0, "max": 2.0, "default": 0.7},
        {"name": "max_tokens", "type": "int", "min": 1, "max": 32000, "default": 4096}
    ]

async def fetch_groq_models() -> dict:
    if not GROQ_API_KEYS: 
        return {"data": [], "provider": "groq"}
    
    maintenance_key = GROQ_API_KEYS[0]
    url = f"{GROQ_BASE_URL}/openai/v1/models"
    headers = {"Authorization": f"Bearer {maintenance_key}"}
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                models = []
                for m in data:
                    mid = m.get("id")
                    if "whisper" not in mid.lower():
                        specs = _get_std_params()
                        
                        # Parameter Logic
                        if "gpt-oss" in mid:
                            specs.append({"name": "reasoning_effort", "type": "enum", "options": ["low", "medium", "high"], "default": "medium"})
                        elif "qwen" in mid:
                            specs.append({"name": "reasoning_effort", "type": "enum", "options": ["default", "none"], "default": "default"})
                            specs.append({"name": "reasoning_format", "type": "enum", "options": ["parsed", "raw", "hidden"], "default": "parsed"})
                        elif "deepseek" in mid:
                             specs.append({"name": "reasoning_format", "type": "enum", "options": ["raw"], "default": "raw"})

                        supported = [s["name"] for s in specs] + ["stream"]

                        models.append({
                            "id": mid,
                            "name": mid,
                            "provider": "groq",
                            "context_length": m.get("context_window"),
                            "pricing": {"prompt": 0.0, "completion": 0.0, "unit": "1M tokens"},
                            "supported_parameters": supported,
                            "parameter_specs": specs
                        })
                return {"data": models, "count": len(models)}
        except Exception: pass
    return {"data": [], "count": 0}

async def fetch_nvidia_models() -> dict:
    if not NVIDIA_API_KEY:
        return {"data": [], "provider": "nvidia"}

    url = f"{NVIDIA_BASE_URL}/models"
    headers = {"Authorization": f"Bearer {NVIDIA_API_KEY}", "Accept": "application/json"}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                models = []
                for m in data:
                    mid = m.get("id")
                    if not mid: continue
                    
                    specs = _get_std_params()
                    
                    # Logic for Reasoning Slider on NVIDIA
                    is_r1 = "deepseek" in mid.lower() and "r1" in mid.lower()
                    is_o = "openai" in mid.lower() and ("o1" in mid.lower() or "o3" in mid.lower())
                    is_oss = "gpt-oss" in mid.lower()

                    if is_r1 or is_o or is_oss:
                        specs.append({
                            "name": "reasoning_effort", 
                            "type": "enum", 
                            "options": ["low", "medium", "high"], 
                            "default": "high" if is_r1 else "medium"
                        })

                    supported = [s["name"] for s in specs] + ["stream"]
                    
                    # Basic name clean up (heuristic)
                    name = mid.split("/")[-1] if "/" in mid else mid

                    models.append({
                        "id": mid,
                        "name": f"NVIDIA {name}", # Tag visuals
                        "provider": "nvidia",
                        "context_length": m.get("context_window", 32768),
                        "pricing": {"prompt": 0.0, "completion": 0.0, "unit": "1M tokens"},
                        "supported_parameters": supported,
                        "parameter_specs": specs
                    })
                return {"data": models, "count": len(models)}
        except Exception: pass
    return {"data": [], "count": 0}

async def fetch_openrouter_models() -> dict:
    url = "https://openrouter.ai/api/v1/models"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=15.0)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                results = []
                for m in data:
                    pricing = m.get("pricing", {})
                    try:
                        p = float(pricing.get("prompt", "0")) * 1_000_000
                        c = float(pricing.get("completion", "0")) * 1_000_000
                    except: p = c = 0.0
                    
                    specs = _get_std_params()
                    
                    results.append({
                        "id": m["id"],
                        "name": m.get("name", m["id"]),
                        "provider": "openrouter",
                        "context_length": m.get("context_length", 0),
                        "pricing": {"prompt": f"{p:.2f}", "completion": f"{c:.2f}", "unit": "1M tokens"},
                        "supported_parameters": m.get("supported_parameters", []) + ["temperature", "max_tokens"],
                        "parameter_specs": specs
                    })
                results.sort(key=lambda x: float(x["pricing"]["prompt"]))
                return {"data": results, "count": len(results)}
        except Exception: pass
    return {"data": [], "count": 0}

async def get_available_models() -> dict:
    # Gather from all 3 providers
    g_res, n_res, o_res = await asyncio.gather(
        fetch_groq_models(), 
        fetch_nvidia_models(), 
        fetch_openrouter_models()
    )
    combined = g_res.get("data", []) + n_res.get("data", []) + o_res.get("data", [])
    return {"data": combined, "count": len(combined)}