import httpx
import asyncio
from typing import List, Dict, Any, Optional

from langchain_groq import ChatGroq
# Ensure you have installed: pip install langchain-deepseek
from langchain_deepseek import ChatDeepSeek

from .config import (
    GROQ_API_KEY, GROQ_BASE_URL, 
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
    MODEL_NAME
)

def get_llm(model_name: str = None, openrouter_api_key: str = None, reasoning_effort: str = None): # type: ignore
    """
    Factory function to return the appropriate LLM client (Groq or OpenRouter).
    Handles specific parameter injection for Reasoning models.
    """
    target_model = model_name or MODEL_NAME
    
    # 1. Determine Provider
    # Heuristic: Groq models typically contain "groq" or are "gpt-oss" (special case)
    # OpenRouter models usually follow "provider/model-name" format.
    is_groq = (
        "groq" in target_model.lower() or 
        "gpt-oss" in target_model.lower() or 
        "/" not in target_model
    )
    
    if not is_groq:
        # --- OPENROUTER CONFIGURATION (via ChatDeepSeek) ---
        effective_key = openrouter_api_key or OPENROUTER_API_KEY
        if not effective_key:
            raise ValueError(f"OpenRouter API Key required for model {target_model}")

        # Check for native OpenAI reasoning models (o1, o3)
        # These support 'reasoning_effort' but NOT 'reasoning: {enabled: true}'
        is_openai_native = any(x in target_model.lower() for x in ["openai/o1", "openai/o3"])
        
        extra_body = {}
        
        if is_openai_native:
            # OpenAI o-series specific parameter
            if reasoning_effort:
                extra_body["reasoning_effort"] = reasoning_effort
        else:
            # For DeepSeek R1, Llama-3.1-Reasoning, etc.
            # They need this explicit toggle to return the reasoning text field.
            extra_body["reasoning"] = {"enabled": True}

        # Use ChatDeepSeek for OpenRouter connections.
        # It natively maps the 'reasoning' field (OpenRouter standard) to LangChain's
        # 'reasoning_content', solving the issue where ChatOpenAI dropped it.
        return ChatDeepSeek(
            model=target_model,
            api_key=effective_key, # type: ignore
            api_base=OPENROUTER_BASE_URL, # Note: ChatDeepSeek uses 'api_base', not 'base_url'
            temperature=0.0,
            streaming=True,
            model_kwargs={
                "extra_body": extra_body
            }
        )
    else:
        # --- GROQ CONFIGURATION ---
        if not GROQ_API_KEY:
             raise ValueError(f"Groq API Key is missing for model {target_model}")
             
        return ChatGroq(
            api_key=GROQ_API_KEY, # type: ignore
            base_url=GROQ_BASE_URL,
            model=target_model,
            streaming=True,
            temperature=0.0,
            stop_sequences=None 
        )

# --- MODEL FETCHING & CACHING UTILITIES ---

async def fetch_groq_models() -> dict:
    """Fetches available models from Groq API."""
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
                    # Filter out whisper (audio) models
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
                            },
                            "supported_parameters": [] # Groq API doesn't usually list these details
                        })
                return {"data": models, "count": len(models)}
        except Exception as e:
            print(f"Groq Fetch Error: {e}")
            pass
    return {"data": [], "count": 0}

async def fetch_openrouter_models() -> dict:
    """Fetches available models from OpenRouter API."""
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
                        # Convert pricing to per 1M tokens for readability
                        p_price = float(pricing.get("prompt", "0")) * 1_000_000
                        c_price = float(pricing.get("completion", "0")) * 1_000_000
                    except (ValueError, TypeError):
                        p_price = 0.0
                        c_price = 0.0

                    # Capture supported parameters (e.g., 'reasoning_effort')
                    # This allows the frontend to conditionally show UI elements.
                    supported = m.get("supported_parameters", [])

                    results.append({
                        "id": m["id"],
                        "name": m.get("name", m["id"]),
                        "provider": "openrouter",
                        "context_length": m.get("context_length", 0),
                        "pricing": {
                            "prompt": f"{p_price:.2f}",
                            "completion": f"{c_price:.2f}",
                            "unit": "1M tokens"
                        },
                        "supported_parameters": supported
                    })
                
                # Sort by price (cheapest first)
                results.sort(key=lambda x: float(x["pricing"]["prompt"]))
                return {"data": results, "count": len(results)}
        except Exception as e:
            print(f"OpenRouter Fetch Error: {e}")
            pass
    return {"data": [], "count": 0}

async def get_available_models() -> dict:
    """Aggregates models from all providers."""
    # Run fetches concurrently
    groq_task = asyncio.create_task(fetch_groq_models())
    or_task = asyncio.create_task(fetch_openrouter_models())
    
    g_res, o_res = await asyncio.gather(groq_task, or_task)
    
    combined = g_res.get("data", []) + o_res.get("data", [])
    return {"data": combined, "count": len(combined)}