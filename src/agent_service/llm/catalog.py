from __future__ import annotations

import asyncio
import json
import logging
import re
import os
from typing import Any, Dict, List, Optional, Set, Tuple, Iterable

import httpx
from redis.asyncio import Redis

from src.agent_service.core.config import (
    GROQ_BASE_URL,
    NVIDIA_BASE_URL,
    REDIS_URL,
)

log = logging.getLogger("model_service")

_PROVIDER_DISPLAY = {
    "openai": "OpenAI", "anthropic": "Anthropic", "google": "Google", "meta": "Meta",
    "meta-llama": "Meta Llama", "mistralai": "Mistral", "cohere": "Cohere",
    "deepseek": "DeepSeek", "deepseek-ai": "DeepSeek", "qwen": "Qwen", "xai": "xAI",
    "perplexity": "Perplexity", "microsoft": "Microsoft", "amazon": "Amazon",
    "nvidia": "NVIDIA", "together": "Together", "01-ai": "01.AI", "ai21": "AI21",
    "nousresearch": "Nous", "moonshotai": "Moonshot",
}

def _titleish(s: str) -> str:
    s = (s or "").strip()
    if not s: return s
    tokens = s.split()
    out = []
    for t in tokens:
        tl = t.lower()
        if tl in {"gpt", "api", "r1", "v3", "v2", "v1"}: out.append(t.upper()); continue
        if re.fullmatch(r"[oO]\d+", t): out.append(t.lower()); continue
        if re.fullmatch(r"\d+o", t): out.append(t.lower()); continue
        if re.fullmatch(r"\d+(?:\.\d+)?b", tl): out.append(t.upper()); continue
        if tl.startswith("llama"): out.append("Llama" + t[5:]); continue
        out.append(t[:1].upper() + t[1:])
    return " ".join(out)

def _humanize_slug(slug: str) -> str:
    s = (slug or "").strip().replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\bllama\s*(\d+)\s+(\d+)\b", r"llama \1.\2", s, flags=re.IGNORECASE)
    s = re.sub(r"\bllama\s*(\d+(?:\.\d+)?)\b", r"llama \1", s, flags=re.IGNORECASE)
    return _titleish(s)

def derive_display_name(model_id: str, *, provider: str, api_name: Optional[str] = None) -> str:
    mid = (model_id or "").strip()
    if not mid: return ""
    if api_name:
        nm = api_name.strip()
        if nm and nm.lower() != mid.lower(): return nm
    if "/" in mid:
        prov, rest = mid.split("/", 1)
        prov_key = prov.strip().lower()
        prov_disp = _PROVIDER_DISPLAY.get(prov_key, _titleish(prov.strip()))
        model_disp = _humanize_slug(rest)
        if model_disp.lower().startswith(prov_disp.lower()): return model_disp
        return f"{prov_disp} {model_disp}".strip()
    return _humanize_slug(mid)

def _sort_models(models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(models, key=lambda m: (str(m.get("name") or "").casefold(), str(m.get("id") or "")))

def _uniq(seq: Iterable[str]) -> List[str]:
    seen = set()
    return [x for x in seq if not (x in seen or seen.add(x))]

class ModelService:
    OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

    def __init__(self):
        self.redis = Redis.from_url(REDIS_URL, decode_responses=True)
        self.CACHE_KEY = "agent:models:cache_all"
        self.PRICING_KEY = "agent:models:pricing"
        self.REFRESH_INTERVAL = 1800 

    def _std_specs(self) -> List[Dict[str, Any]]:
        return [
            {"name": "temperature", "type": "float", "min": 0.0, "max": 2.0, "default": 0.7},
            {"name": "max_tokens", "type": "int", "min": 1, "max": 32768},
        ]

    def _ensure_tool_specs(self, specs: List[Dict[str, Any]], provider: str) -> List[Dict[str, Any]]:
        names = {str(s.get("name") or "").strip() for s in (specs or []) if isinstance(s, dict)}
        if "tool_calling_enabled" not in names:
            specs.append({"name": "tool_calling_enabled", "type": "boolean", "default": "true"})
        if "tool_choice" not in names:
            specs.append({"name": "tool_choice", "type": "enum", "options": ["auto", "none"], "default": "auto"})
        return specs

    def _get_groq_specs(self, model_id: str) -> List[Dict[str, Any]]:
        specs = [
            {"name": "temperature", "type": "float", "min": 0.0, "max": 2.0, "default": 0.6 if "gpt-oss" in (model_id or "").lower() else 0.7},
            {"name": "max_tokens", "type": "int", "min": 1, "max": 32768},
        ]
        mid = (model_id or "").lower()
        if "gpt-oss" in mid:
            specs.append({"name": "reasoning_effort", "type": "enum", "options": ["low", "medium", "high"], "default": "medium"})
        elif "qwen" in mid:
            specs.append({"name": "reasoning_effort", "type": "enum", "options": ["default", "none"], "default": "default"})
            specs.append({"name": "reasoning_format", "type": "enum", "options": ["parsed", "raw", "hidden"], "default": "parsed"})
        elif "deepseek" in mid:
            specs.append({"name": "reasoning_format", "type": "enum", "options": ["raw"], "default": "raw"})
        return self._ensure_tool_specs(specs, provider="groq")

    async def fetch_groq_data(self) -> List[Dict[str, Any]]:
        # In BYOK mode, we don't have a server key to fetch the catalog.
        # We can try to grab one from env if available, otherwise skip.
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key: return []
        
        try:
            url = f"{GROQ_BASE_URL}/openai/v1/models"
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url, headers={"Authorization": f"Bearer {api_key}"})
                if resp.status_code != 200: return []
                data = resp.json().get("data", [])
                results = []
                for m in data:
                    mid = (m.get("id") or "").strip()
                    if not mid or "whisper" in mid.lower(): continue
                    results.append({
                        "id": mid,
                        "name": derive_display_name(mid, provider="groq"),
                        "provider": "groq",
                        "context_length": int(m.get("context_window") or 0),
                        "pricing": {"prompt": 0.0, "completion": 0.0, "unit": "1M tokens"},
                        "supported_parameters": _uniq([s["name"] for s in self._get_groq_specs(mid)] + ["stream"]),
                        "parameter_specs": self._get_groq_specs(mid),
                        "modality": "text",
                        "type": "chat",
                    })
                return _sort_models(results)
        except Exception as e:
            log.error(f"Groq Fetch Error: {e}")
            return []

    async def fetch_openrouter_data(self) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, float]]]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(self.OPENROUTER_MODELS_URL)
                if resp.status_code != 200: return [], {}
                
                data = resp.json().get("data", [])
                results = []
                pricing_map = {}

                for m in data:
                    mid = (m.get("id") or "").strip()
                    if not mid: continue
                    
                    # Pricing normalization
                    raw_p = m.get("pricing", {})
                    try:
                        p_float = float(raw_p.get("prompt", "0"))
                        c_float = float(raw_p.get("completion", "0"))
                    except:
                        p_float = c_float = 0.0
                    
                    pricing_map[mid] = {"prompt": p_float, "completion": c_float}

                    # For UI display, we multiply by 1M
                    ui_p = p_float * 1_000_000
                    ui_c = c_float * 1_000_000

                    specs = self._std_specs()
                    supported = list(m.get("supported_parameters", []) or []) + ["stream"]
                    
                    results.append({
                        "id": mid,
                        "name": derive_display_name(mid, provider="openrouter", api_name=m.get("name")),
                        "provider": "openrouter",
                        "context_length": int(m.get("context_length") or 0),
                        "pricing": {"prompt": ui_p, "completion": ui_c, "unit": "1M tokens"},
                        "supported_parameters": supported,
                        "parameter_specs": specs,
                        "architecture": m.get("architecture") or {},
                        "modality": str((m.get("architecture") or {}).get("modality") or "text").split("->")[0],
                        "type": "chat"
                    })
                
                return _sort_models(results), pricing_map
        except Exception as e:
            log.error(f"OpenRouter Fetch Error: {e}")
            return [], {}

    async def fetch_nvidia_data(self) -> List[Dict[str, Any]]:
        # BYOK Check
        api_key = os.getenv("NVIDIA_API_KEY")
        if not api_key: return []
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{NVIDIA_BASE_URL}/models", headers={"Authorization": f"Bearer {api_key}"})
                if resp.status_code != 200: return []
                # Simple implementation for now
                return [] 
        except: return []

    async def refresh_cache(self) -> None:
        log.info("Refreshing model cache...")
        groq, (or_models, or_pricing), nvidia = await asyncio.gather(
            self.fetch_groq_data(),
            self.fetch_openrouter_data(),
            self.fetch_nvidia_data()
        )
        
        all_models = [
            {"name": "groq", "models": groq},
            {"name": "nvidia", "models": nvidia},
            {"name": "openrouter", "models": or_models}
        ]
        
        async with self.redis.pipeline() as pipe:
            pipe.set(self.CACHE_KEY, json.dumps(all_models))
            if or_pricing:
                pipe.set(self.PRICING_KEY, json.dumps(or_pricing))
            await pipe.execute()
            
        log.info(f"Cache updated. Pricing Keys: {len(or_pricing)}")

    async def get_cached_data(self) -> List[Dict[str, Any]]:
        raw = await self.redis.get(self.CACHE_KEY)
        return json.loads(raw) if raw else []

    async def get_price(self, model_id: str) -> Optional[Dict[str, float]]:
        """
        Efficiently looks up pricing for a model ID.
        Returns dict with 'prompt' and 'completion' rates (per token).
        """
        raw = await self.redis.get(self.PRICING_KEY)
        if raw:
            data = json.loads(raw)
            if model_id in data:
                return data[model_id]
        return None

    async def start_background_loop(self):
        while True:
            try: await self.refresh_cache()
            except Exception as e: log.error(f"Refresh failed: {e}")
            await asyncio.sleep(self.REFRESH_INTERVAL)

    async def close(self):
        await self.redis.close()

model_service = ModelService()
