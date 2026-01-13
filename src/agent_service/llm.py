import httpx
import asyncio
from typing import List, Dict, Any, Optional

from langchain_groq import ChatGroq
from langchain_deepseek import ChatDeepSeek

from .config import (
    GROQ_KEY_CYCLE,  # The Round-Robin Iterator
    GROQ_API_KEYS,   # The raw list (for fetching models)
    GROQ_BASE_URL, 
    OPENROUTER_API_KEY, 
    OPENROUTER_BASE_URL,
    MODEL_NAME
)

def get_llm(model_name: str = None, openrouter_api_key: str = None, reasoning_effort: str = None):  # type: ignore
    """
    Factory function to return the appropriate LLM client (Groq or OpenRouter).
    Passes reasoning parameters directly to the constructor.
    Implements Internal Sequential Load Balancing for Groq.
    """
    target_model = model_name or MODEL_NAME
    
    # --- PROVIDER SELECTION LOGIC ---
    
    # 1. Has the user provided an OpenRouter specific key?
    #    (Either passed in args or saved in their session config)
    user_provided_or_key = bool(openrouter_api_key)
    
    # 2. Is this definitely a Groq-only legacy ID? (e.g. "llama3-8b-8192")
    is_legacy_groq = "/" not in target_model
    
    # 3. Check if Groq keys are actually available in config
    has_groq_keys = GROQ_KEY_CYCLE is not None
    
    # 4. Decision Matrix
    use_groq = False
    if is_legacy_groq:
        use_groq = True
    elif not user_provided_or_key and has_groq_keys:
        # Assuming if no specific OR key is given, we prefer Groq infrastructure
        use_groq = True
    
    # --- CLIENT INITIALIZATION ---

    if not use_groq:
        # === OPENROUTER ===
        effective_key = openrouter_api_key or OPENROUTER_API_KEY
        if not effective_key:
            raise ValueError(f"OpenRouter API Key required for model {target_model}")

        # OpenRouter/DeepSeek Logic (ChatDeepSeek needs extra_body)
        is_openai_native = any(x in target_model.lower() for x in ["openai/o1", "openai/o3"])
        extra_body = {}
        
        if is_openai_native:
            if reasoning_effort:
                extra_body["reasoning_effort"] = reasoning_effort
        else:
            # For DeepSeek R1, Llama-3.1-Reasoning, etc. on OpenRouter
            # We enable reasoning by default if it's supported
            extra_body["reasoning"] = {"enabled": True}

        return ChatDeepSeek(
            model=target_model,
            api_key=effective_key, # type: ignore
            api_base=OPENROUTER_BASE_URL,
            temperature=0.0,
            streaming=True,
            extra_body=extra_body
        )
    else:
        # === GROQ (LOAD BALANCED) ===
        if not has_groq_keys:
             raise ValueError(f"No Groq API Keys configured for model {target_model}")

        # [CRITICAL] Load Balancing: Get the next key from the cycle
        current_api_key = next(GROQ_KEY_CYCLE) # type: ignore

        # Default values
        r_format = None
        r_effort = None

        # 1. GPT-OSS Logic
        if "gpt-oss" in target_model:
            r_format = "parsed"
            r_effort = reasoning_effort if reasoning_effort else "high"

        # 2. Qwen Logic
        elif "qwen" in target_model:
            r_format = "parsed"
            r_effort = "default"
        
        # 3. DeepSeek on Groq
        elif "deepseek" in target_model:
             r_format = "raw"
             r_effort = None

        return ChatGroq(
            api_key=current_api_key, # Use the rotated key # type: ignore
            base_url=GROQ_BASE_URL,
            model=target_model,
            streaming=True,
            temperature=0.0,
            stop_sequences=None,
            reasoning_format=r_format,
            reasoning_effort=r_effort
        )

# --- MODEL FETCHING & CACHING UTILITIES ---

def _get_std_params() -> List[Dict[str, Any]]:
    """Standard parameters for most models to populate GraphQL specs."""
    return [
        {"name": "temperature", "type": "float", "min": 0.0, "max": 2.0, "default": 0.7},
        {"name": "max_tokens", "type": "int", "min": 1, "max": 32000, "default": 4096}
    ]

async def fetch_groq_models() -> dict:
    # Use the LIST, not the CYCLE, for metadata checking to avoid burning logic
    if not GROQ_API_KEYS: 
        return {"data": [], "provider": "groq"}
    
    # Always use the first key for system maintenance tasks (fetching models)
    # This leaves the rotation pool intact for user queries.
    maintenance_key = GROQ_API_KEYS[0]

    url = f"{GROQ_BASE_URL}/openai/v1/models"
    headers = {"Authorization": f"Bearer {maintenance_key}"}
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                models = []
                for m in data:
                    mid = m.get("id")
                    if "whisper" not in mid.lower():
                        # Calculate Parameter Specs for Frontend
                        specs = _get_std_params()
                        
                        # 1. GPT-OSS
                        if "gpt-oss" in mid:
                            specs.append({
                                "name": "reasoning_effort", 
                                "type": "enum", 
                                "options": ["low", "medium", "high"], 
                                "default": "medium"
                            })
                        
                        # 2. Qwen (Supports Format AND Effort)
                        elif "qwen" in mid:
                            specs.append({
                                "name": "reasoning_effort", 
                                "type": "enum", 
                                "options": ["default", "none"], 
                                "default": "default"
                            })
                            specs.append({
                                "name": "reasoning_format", 
                                "type": "enum", 
                                "options": ["parsed", "raw", "hidden"], 
                                "default": "parsed"
                            })

                        # 3. DeepSeek (Raw only)
                        elif "deepseek" in mid:
                             specs.append({
                                "name": "reasoning_format", 
                                "type": "enum", 
                                "options": ["raw"], 
                                "default": "raw"
                            })

                        # Legacy supported list
                        supported = [s["name"] for s in specs]
                        if "stream" not in supported: supported.append("stream")

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

async def fetch_openrouter_models() -> dict:
    url = "https://openrouter.ai/api/v1/models"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                results = []
                for m in data:
                    pricing = m.get("pricing", {})
                    try:
                        p = float(pricing.get("prompt", "0")) * 1_000_000
                        c = float(pricing.get("completion", "0")) * 1_000_000
                    except: p = c = 0.0
                    
                    # Populate default specs for OpenRouter so frontend doesn't show empty
                    specs = _get_std_params()
                    
                    # Add reasoning check if OpenRouter tags it
                    # (OpenRouter API doesn't give us granular enum options easily, so we stay basic)
                    
                    results.append({
                        "id": m["id"],
                        "name": m.get("name", m["id"]),
                        "provider": "openrouter",
                        "context_length": m.get("context_length", 0),
                        "pricing": {"prompt": f"{p:.2f}", "completion": f"{c:.2f}", "unit": "1M tokens"},
                        "supported_parameters": m.get("supported_parameters", []) + ["temperature", "max_tokens"],
                        "parameter_specs": specs # Now populated!
                    })
                results.sort(key=lambda x: float(x["pricing"]["prompt"]))
                return {"data": results, "count": len(results)}
        except Exception: pass
    return {"data": [], "count": 0}

async def get_available_models() -> dict:
    g_res, o_res = await asyncio.gather(fetch_groq_models(), fetch_openrouter_models())
    combined = g_res.get("data", []) + o_res.get("data", [])
    return {"data": combined, "count": len(combined)}