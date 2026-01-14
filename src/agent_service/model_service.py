# ===== src/agent_service/model_service.py =====
from __future__ import annotations

import asyncio
import json
import logging
import re
from functools import partial
from typing import Any, Dict, List, Optional, Tuple

import httpx
from redis.asyncio import Redis
from langchain_nvidia_ai_endpoints import ChatNVIDIA

from .config import (
    GROQ_API_KEYS,
    GROQ_BASE_URL,
    NVIDIA_API_KEY,
    NVIDIA_BASE_URL,
    REDIS_URL,
)

log = logging.getLogger("model_service")

_PROVIDER_DISPLAY = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "meta": "Meta",
    "meta-llama": "Meta Llama",
    "mistralai": "Mistral",
    "cohere": "Cohere",
    "deepseek": "DeepSeek",
    "deepseek-ai": "DeepSeek",
    "qwen": "Qwen",
    "xai": "xAI",
    "perplexity": "Perplexity",
    "microsoft": "Microsoft",
    "amazon": "Amazon",
    "nvidia": "NVIDIA",
    "together": "Together",
    "01-ai": "01.AI",
    "ai21": "AI21",
    "nousresearch": "Nous",
    "moonshotai": "Moonshot",
}

def _titleish(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return s
    tokens = s.split()
    out: List[str] = []
    for t in tokens:
        tl = t.lower()
        if tl in {"gpt", "api", "r1", "v3", "v2", "v1"}:
            out.append(t.upper())
            continue
        if re.fullmatch(r"[oO]\d+", t):
            out.append(t.lower())
            continue
        if re.fullmatch(r"\d+o", t):
            out.append(t.lower())
            continue
        if re.fullmatch(r"\d+(?:\.\d+)?b", tl):
            out.append(t.upper())
            continue
        if tl.startswith("llama"):
            out.append("Llama" + t[5:])
            continue
        out.append(t[:1].upper() + t[1:])
    return " ".join(out)

def _humanize_slug(slug: str) -> str:
    s = (slug or "").strip().replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\bllama\s*(\d+)\s+(\d+)\b", r"llama \1.\2", s, flags=re.IGNORECASE)
    s = re.sub(r"\bllama\s*(\d+(?:\.\d+)?)\b", r"llama \1", s, flags=re.IGNORECASE)
    return _titleish(s)

def derive_display_name(
    model_id: str,
    *,
    provider: str,
    api_name: Optional[str] = None,
) -> str:
    mid = (model_id or "").strip()
    if not mid:
        return ""
    if api_name:
        nm = api_name.strip()
        if nm and nm.lower() != mid.lower():
            return nm
    if "/" in mid:
        prov, rest = mid.split("/", 1)
        prov_key = prov.strip().lower()
        prov_disp = _PROVIDER_DISPLAY.get(prov_key, _titleish(prov.strip()))
        model_disp = _humanize_slug(rest)
        if model_disp.lower().startswith(prov_disp.lower()):
            return model_disp
        return f"{prov_disp} {model_disp}".strip()
    if provider == "groq":
        return _humanize_slug(mid)
    return _humanize_slug(mid)

def _sort_models(models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def key(m: Dict[str, Any]) -> Tuple[str, str]:
        name = str(m.get("name") or "").casefold()
        mid = str(m.get("id") or "")
        return (name, mid)
    return sorted(models, key=key)

def _uniq(seq: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for x in seq or []:
        s = str(x).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out

class ModelService:
    """
    Caches model lists into Redis as provider buckets:
      - groq
      - nvidia
      - openrouter
    """

    OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

    def __init__(self):
        self.redis = Redis.from_url(REDIS_URL, decode_responses=True)
        self.CACHE_KEY = "agent:models:cache_all"
        self.REFRESH_INTERVAL = 1800  # 30 minutes

    # -------------------------
    # Parameter Specs (UI)
    # -------------------------

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

        if provider == "groq" and "disable_tool_validation" not in names:
            specs.append({"name": "disable_tool_validation", "type": "boolean", "default": "false"})

        return specs

    def _get_groq_specs(self, model_id: str) -> List[Dict[str, Any]]:
        specs = [
            {
                "name": "temperature",
                "type": "float",
                "min": 0.0,
                "max": 2.0,
                "default": 0.6 if "gpt-oss" in (model_id or "").lower() else 0.7,
            },
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

    def _classify_nvidia_model(self, model_id: str) -> dict:
        """
        Heuristics to determine model capabilities from the live ID 
        since the raw API response doesn't always provide metadata.
        """
        mid = model_id.lower()
        
        # Defaults
        info = {
            "type": "chat", 
            "modality": "text", 
            "supports_tools": False, 
            "supports_thinking": False
        }

        # 1. Detect Reasoning / Thinking Models
        # Covers: deepseek-r1, qwen-qwq, kimi-thinking, gpt-oss (supports reasoning_effort)
        if any(x in mid for x in ["r1", "thinking", "reasoning", "qwq", "gpt-oss"]):
            info["type"] = "reasoning"
            info["supports_thinking"] = True
            
            # FACT-BASED TOOL SUPPORT:
            # - "distill": Llama/Qwen distillations retain tool capabilities.
            # - "0528": Specific DeepSeek-R1 checkpoint upgraded for function calling.
            # - "terminus": DeepSeek V3.1 Terminus is explicitly tool-capable.
            # - "kimi": Moonshot Kimi K2 Thinking is designed for tools.
            # - "gpt-oss": OpenAI GPT-OSS supports tools.
            if any(x in mid for x in ["distill", "0528", "terminus", "kimi", "gpt-oss"]):
                info["supports_tools"] = True
        
        # 2. Detect Vision Models (VLM)
        elif any(x in mid for x in ["vision", "vlm", "ocr", "paligemma", "fuyu", "neva", "vila"]):
            info["type"] = "vision"
            info["modality"] = "vision"
            # Vision models usually support tools if they are Llama 3.2+, Phi, or Nemotron-VL
            if "llama-3.2" in mid or "phi" in mid or "nemotron" in mid:
                info["supports_tools"] = True

        # 3. Detect Standard Chat Models with Tool Support
        else:
            # Broad check for known tool-capable families
            if any(x in mid for x in [
                "llama-3.1", "llama-3.2", "llama-3.3", 
                "mistral-nemo", "mistral-large", "mistral-small",
                "qwen2.5", "nemotron", "command-r", 
                "deepseek-v3", "gpt-oss", "kimi", "moonshot"
            ]):
                info["supports_tools"] = True
        
        return info

    # -------------------------
    # Fetchers
    # -------------------------

    async def fetch_groq_data(self) -> List[Dict[str, Any]]:
        if not GROQ_API_KEYS:
            return []

        api_key = GROQ_API_KEYS[0]
        url = f"{GROQ_BASE_URL}/openai/v1/models"
        headers = {"Authorization": f"Bearer {api_key}"}

        timeout = httpx.Timeout(20.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    log.error("Groq models fetch failed: HTTP %s", resp.status_code)
                    return []

                data = resp.json().get("data", []) or []
                results: List[Dict[str, Any]] = []

                for m in data:
                    mid = (m.get("id") or "").strip()
                    if not mid or "whisper" in mid.lower():
                        continue

                    specs = self._get_groq_specs(mid)
                    supported_list = _uniq([s["name"] for s in specs] + ["stream"])
                    context_len = int(m.get("context_window") or 0)

                    results.append({
                        "id": mid,
                        "name": derive_display_name(mid, provider="groq"),
                        "provider": "groq",
                        "context_length": context_len,
                        "pricing": {"prompt": 0.0, "completion": 0.0, "unit": "1M tokens"},
                        "supported_parameters": supported_list,
                        "parameter_specs": specs,
                        "modality": "text",
                        "type": "chat",
                    })

                return _sort_models(results)
            except Exception as e:
                log.error("Groq Fetch Error: %s", e)
                return []

    async def fetch_nvidia_data(self) -> List[Dict[str, Any]]:
        if not NVIDIA_API_KEY:
            return []

        url = f"{NVIDIA_BASE_URL}/models"
        headers = {"Authorization": f"Bearer {NVIDIA_API_KEY}", "Accept": "application/json"}

        # Use a short timeout; the API is fast.
        timeout = httpx.Timeout(10.0, connect=5.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    log.error("[nvidia] fetch failed: HTTP %s", resp.status_code)
                    return []

                # API returns wrapper: { "data": [ { "id": "..." }, ... ] }
                raw_data = resp.json().get("data", []) or []
                results: List[Dict[str, Any]] = []

                for m in raw_data:
                    mid = str(m.get("id") or "").strip()
                    if not mid: continue

                    # Classify based on ID string
                    meta = self._classify_nvidia_model(mid)
                    
                    # Build Specs dynamically
                    specs = self._std_specs() # basic temp/max_tokens

                    if meta["supports_thinking"]:
                        specs.append({
                            "name": "reasoning_effort", 
                            "type": "enum", 
                            "options": ["low", "medium", "high"], 
                            "default": "medium"
                        })
                    
                    if meta["supports_tools"]:
                        specs = self._ensure_tool_specs(specs, provider="nvidia")

                    supported = _uniq([s["name"] for s in specs if isinstance(s, dict) and s.get("name")] + ["stream"])

                    # Context Length:
                    # Raw API often lacks this. We infer defaults or check if specific substring exists.
                    context_len = 32768
                    if "128k" in mid: context_len = 131072
                    elif "8k" in mid: context_len = 8192
                    elif "4k" in mid: context_len = 4096

                    results.append({
                        "id": mid,
                        "name": derive_display_name(mid, provider="nvidia"),
                        "provider": "nvidia",
                        "modality": meta["modality"],
                        "type": meta["type"],
                        "context_length": context_len,
                        "pricing": {"prompt": 0.0, "completion": 0.0, "unit": "1M tokens"},
                        "supported_parameters": supported,
                        "parameter_specs": specs,
                    })

                log.info(f"[nvidia] Successfully fetched {len(results)} live models via API.")
                return _sort_models(results)

            except Exception as e:
                log.error("[nvidia] API Error: %s", e)
                return []

    async def fetch_openrouter_data(self) -> List[Dict[str, Any]]:
        timeout = httpx.Timeout(25.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.get(self.OPENROUTER_MODELS_URL)
                if resp.status_code != 200:
                    log.error("OpenRouter models fetch failed: HTTP %s", resp.status_code)
                    return []

                data = resp.json().get("data", []) or []
                results: List[Dict[str, Any]] = []

                for m in data:
                    mid = (m.get("id") or "").strip()
                    if not mid:
                        continue

                    pricing = m.get("pricing", {}) or {}
                    try:
                        p = float(pricing.get("prompt", "0")) * 1_000_000
                        c = float(pricing.get("completion", "0")) * 1_000_000
                    except Exception:
                        p = c = 0.0

                    supported = list(m.get("supported_parameters", []) or []) + ["stream"]
                    specs = self._std_specs()

                    results.append({
                        "id": mid,
                        "name": derive_display_name(mid, provider="openrouter", api_name=m.get("name")),
                        "provider": "openrouter",
                        "context_length": int(m.get("context_length") or 0),
                        "pricing": {"prompt": float(p), "completion": float(c), "unit": "1M tokens"},
                        "supported_parameters": supported,
                        "parameter_specs": specs,
                        "architecture": m.get("architecture") or {},
                        "modality": str((m.get("architecture") or {}).get("modality") or "text").split("->", 1)[0],
                        "type": "chat",
                    })

                return _sort_models(results)
            except Exception as e:
                log.error("OpenRouter Fetch Error: %s", e)
                return []

    # -------------------------
    # Cache lifecycle
    # -------------------------

    async def refresh_cache(self) -> None:
        log.info("Refreshing model cache (providers: groq, nvidia, openrouter)...")

        groq_models, or_models, nvidia_models = await asyncio.gather(
            self.fetch_groq_data(),
            self.fetch_openrouter_data(),
            self.fetch_nvidia_data(),
        )

        structured_data = [
            {"name": "groq", "models": groq_models or []},
            {"name": "nvidia", "models": nvidia_models or []},
            {"name": "openrouter", "models": or_models or []},
        ]

        await self.redis.set(self.CACHE_KEY, json.dumps(structured_data))
        log.info(
            "Model cache updated: groq=%d nvidia=%d openrouter=%d",
            len(groq_models or []),
            len(nvidia_models or []),
            len(or_models or []),
        )

    async def get_cached_data(self) -> List[Dict[str, Any]]:
        raw = await self.redis.get(self.CACHE_KEY)
        if not raw:
            return []
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except Exception:
            pass
        return []

    async def start_background_loop(self) -> None:
        while True:
            try:
                await self.refresh_cache()
            except Exception as e:
                log.error("Model cache refresh failed: %s", e)
            await asyncio.sleep(self.REFRESH_INTERVAL)

    async def close(self) -> None:
        await self.redis.close()

model_service = ModelService()