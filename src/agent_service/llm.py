import httpx
import re
import asyncio
from typing import Optional
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from .config import (
    GROQ_API_KEY, GROQ_BASE_URL, 
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
    MODEL_NAME
)

def get_llm(model_name: str = None, openrouter_api_key: str = None, reasoning_effort: str = None): # type: ignore
    """
    Returns an LLM instance.
    """
    target_model = model_name or MODEL_NAME
    
    # Heuristic: OpenRouter models contain '/' and are not from Groq
    is_openrouter = "/" in target_model and "groq" not in target_model.lower()
    
    if is_openrouter:
        effective_key = openrouter_api_key or OPENROUTER_API_KEY
        if not effective_key:
            raise ValueError(f"OpenRouter API Key required for model {target_model}")

        # Check for OpenAI O-series (o1, o3) which use 'reasoning_effort'
        is_openai_reasoning = any(x in target_model.lower() for x in ["openai/o", "o1-", "o3-"])
        
        extra_body = {}
        
        # LOGIC FIX: Mutually exclusive parameters
        if is_openai_reasoning:
            # OpenAI models: Use standard 'reasoning_effort' param, DO NOT send 'reasoning' toggle
            pass 
        else:
            # DeepSeek R1 / Others: Use OpenRouter-specific toggle
            extra_body["reasoning"] = {"enabled": True}

        return ChatOpenAI(
            api_key=effective_key, # type: ignore
            base_url=OPENROUTER_BASE_URL,
            model=target_model,
            streaming=True,
            temperature=0.0,
            # Only pass reasoning_effort if it's an OpenAI reasoning model
            reasoning_effort=reasoning_effort if is_openai_reasoning else None,
            model_kwargs={
                "extra_body": extra_body
            }
        )
    else:
        return ChatGroq(
            api_key=GROQ_API_KEY, # type: ignore
            base_url=GROQ_BASE_URL,
            model=target_model,
            streaming=True,
            temperature=0.0,
            reasoning_format="parsed" 
        )

# Initialize Default LLM instance (Safety: won't crash if env vars missing, just fails at runtime)
# llm = get_llm() 

async def fetch_groq_models() -> dict:
    if not GROQ_API_KEY: return {"data": [], "provider": "groq"}
    url = f"{GROQ_BASE_URL}/openai/v1/models"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                models = []
                for m in data:
                    if "whisper" not in m.get("id", "").lower():
                        models.append({
                            "id": m.get("id"),
                            "name": m.get("id"),
                            "provider": "groq",
                            "context_length": m.get("context_window"),
                            "pricing": {
                                "prompt": "0.00",
                                "completion": "0.00",
                                "unit": "1M tokens (Approx/Free)"
                            }
                        })
                return {"data": models, "count": len(models)}
        except Exception: pass
    return {"data": [], "count": 0}

async def fetch_openrouter_models() -> dict:
    url = "https://openrouter.ai/api/v1/models"
    target_params = {"reasoning", "reasoning_effort", "include_reasoning"}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                
                filtered_models = []
                for m in data:
                    supported = set(m.get("supported_parameters", []))
                    matches = target_params.intersection(supported)
                    
                    if matches:
                        pricing = m.get("pricing", {})
                        try:
                            prompt_price = float(pricing.get("prompt", "0")) * 1_000_000
                            completion_price = float(pricing.get("completion", "0")) * 1_000_000
                        except (ValueError, TypeError):
                            prompt_price = 0.0
                            completion_price = 0.0

                        filtered_models.append({
                            "id": m["id"],
                            "name": m.get("name", m["id"]),
                            "provider": "openrouter",
                            "context_length": m.get("context_length"),
                            "pricing": {
                                "prompt": f"{prompt_price:.2f}",
                                "completion": f"{completion_price:.2f}",
                                "unit": "1M tokens"
                            },
                            "supported_params": list(matches)
                        })
                
                filtered_models.sort(key=lambda x: float(x["pricing"]["prompt"]))
                return {"data": filtered_models, "count": len(filtered_models)}
        except Exception as e:
            print(f"OpenRouter Fetch Error: {e}")
            pass
    return {"data": [], "count": 0}

async def get_available_models() -> dict:
    groq_task = asyncio.create_task(fetch_groq_models())
    or_task = asyncio.create_task(fetch_openrouter_models())
    g_res, o_res = await asyncio.gather(groq_task, or_task)
    combined = g_res.get("data", []) + o_res.get("data", [])
    return {"data": combined, "count": len(combined)}
