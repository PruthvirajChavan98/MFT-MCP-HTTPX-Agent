import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import httpx
from redis.asyncio import Redis

from .config import (
    GROQ_API_KEY,
    GROQ_BASE_URL,
    REDIS_URL,
)

log = logging.getLogger("model_service")


# -------------------------
# Friendly naming helpers
# -------------------------

_PROVIDER_DISPLAY = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "meta": "Meta",
    "mistralai": "Mistral",
    "cohere": "Cohere",
    "deepseek": "DeepSeek",
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
    # basic titlecase while preserving common tokens
    tokens = s.split()
    out: List[str] = []
    for t in tokens:
        tl = t.lower()

        # preserve known acronyms / model families
        if tl in {"gpt", "api", "r1", "v3", "v2", "v1"}:
            out.append(t.upper())
            continue

        # preserve "4o", "o1", "o3" styles
        if re.fullmatch(r"[oO]\d+", t):
            out.append(t.lower())
            continue
        if re.fullmatch(r"\d+o", t):
            out.append(t.lower())
            continue

        # "70b", "8b", "405b"
        if re.fullmatch(r"\d+(?:\.\d+)?b", tl):
            out.append(t.upper())
            continue

        # llama family
        if tl.startswith("llama"):
            # llama3 / llama-3.1 handled elsewhere; keep fallback
            out.append("Llama" + t[5:])
            continue

        out.append(t[:1].upper() + t[1:])
    return " ".join(out)


def _humanize_slug(slug: str) -> str:
    # replace separators with spaces
    s = (slug or "").strip().replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()

    # normalize "llama 3 1" -> "Llama 3.1"
    s = re.sub(r"\bllama\s*(\d+)\s+(\d+)\b", r"llama \1.\2", s, flags=re.IGNORECASE)
    s = re.sub(r"\bllama\s*(\d+(?:\.\d+)?)\b", r"llama \1", s, flags=re.IGNORECASE)

    return _titleish(s)


def derive_display_name(
    model_id: str,
    *,
    provider: str,
    api_name: Optional[str] = None,
    canonical_slug: Optional[str] = None,
) -> str:
    """
    Goal: return a stable, human-friendly display name.
    - Keep `id` raw.
    - Put friendly name into `name`.
    """
    mid = (model_id or "").strip()
    if not mid:
        return ""

    # If OpenRouter already gives a decent name, prefer it.
    # Many entries are already "GPT-4o mini", "Claude 3.5 Sonnet", etc.
    if api_name:
        nm = api_name.strip()
        if nm and nm.lower() != mid.lower():
            return nm

    base = (canonical_slug or mid).strip()

    # OpenRouter IDs are typically "provider/model"
    if "/" in base:
        prov, rest = base.split("/", 1)
        prov_key = prov.strip().lower()
        prov_disp = _PROVIDER_DISPLAY.get(prov_key, _titleish(prov.strip()))
        model_disp = _humanize_slug(rest)
        # If model_disp already starts with provider name, avoid duplication
        if model_disp.lower().startswith(prov_disp.lower()):
            return model_disp
        return f"{prov_disp} {model_disp}".strip()

    # Groq legacy IDs / non-slashed IDs
    if provider == "groq":
        return _humanize_slug(base)

    # fallback
    return _humanize_slug(base)


def _sort_models(models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def key(m: Dict[str, Any]) -> Tuple[str, str]:
        name = str(m.get("name") or "").casefold()
        mid = str(m.get("id") or "")
        return (name, mid)

    return sorted(models, key=key)


class ModelService:
    """
    Caches model lists into Redis as EXACTLY TWO provider buckets:

      - groq
      - openrouter

    Redis value schema:
      [
        {"name": "groq", "models": [...]},
        {"name": "openrouter", "models": [...]}
      ]
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

    def _get_groq_specs(self, model_id: str) -> List[Dict[str, Any]]:
        specs = [
            {
                "name": "temperature",
                "type": "float",
                "min": 0.0,
                "max": 2.0,
                "default": 0.6 if "gpt-oss" in (model_id or "") else 0.7,
            },
            {"name": "max_tokens", "type": "int", "min": 1, "max": 32768},
        ]

        mid = (model_id or "").lower()

        # 1) GPT-OSS (low/medium/high)
        if "gpt-oss" in mid:
            specs.append(
                {
                    "name": "reasoning_effort",
                    "type": "enum",
                    "options": ["low", "medium", "high"],
                    "default": "medium",
                }
            )

        # 2) Qwen (default/none + format)
        elif "qwen" in mid:
            specs.append(
                {
                    "name": "reasoning_effort",
                    "type": "enum",
                    "options": ["default", "none"],
                    "default": "default",
                }
            )
            specs.append(
                {
                    "name": "reasoning_format",
                    "type": "enum",
                    "options": ["parsed", "raw", "hidden"],
                    "default": "parsed",
                }
            )

        # 3) DeepSeek (raw only)
        elif "deepseek" in mid:
            specs.append(
                {
                    "name": "reasoning_format",
                    "type": "enum",
                    "options": ["raw"],
                    "default": "raw",
                }
            )

        return specs

    def _get_openrouter_specs(self, model_id: str, supported_parameters: List[str]) -> List[Dict[str, Any]]:
        specs = self._std_specs()
        sp = set((supported_parameters or []))

        mid = (model_id or "").lower()
        if "reasoning_effort" in sp or "openai/o1" in mid or "openai/o3" in mid:
            specs.append(
                {
                    "name": "reasoning_effort",
                    "type": "enum",
                    "options": ["low", "medium", "high"],
                    "default": "medium",
                }
            )

        if "reasoning" in sp or "include_reasoning" in sp:
            specs.append(
                {
                    "name": "include_reasoning",
                    "type": "boolean",
                    "default": "true",
                }
            )

        return specs

    # -------------------------
    # Fetchers
    # -------------------------

    async def fetch_groq_data(self) -> List[Dict[str, Any]]:
        if not GROQ_API_KEY:
            return []

        url = f"{GROQ_BASE_URL}/openai/v1/models"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}

        timeout = httpx.Timeout(20.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    log.error(f"Groq models fetch failed: HTTP {resp.status_code}")
                    return []

                data = resp.json().get("data", [])
                results: List[Dict[str, Any]] = []

                for m in data:
                    mid = (m.get("id") or "").strip()
                    if not mid:
                        continue
                    if "whisper" in mid.lower():
                        continue

                    specs = self._get_groq_specs(mid)
                    supported_list = [s["name"] for s in specs]
                    if "stream" not in supported_list:
                        supported_list.append("stream")

                    context_len = m.get("context_window") or m.get("context_length") or 8192
                    try:
                        context_len = int(context_len)
                    except Exception:
                        context_len = 8192

                    friendly = derive_display_name(mid, provider="groq", api_name=None, canonical_slug=None)

                    results.append(
                        {
                            "id": mid,
                            "name": friendly,  # IMPORTANT: display name lives here
                            "context_length": context_len,
                            "pricing": {"prompt": 0.0, "completion": 0.0, "unit": "1M tokens"},
                            "supported_parameters": supported_list,
                            "parameter_specs": specs,
                        }
                    )

                return _sort_models(results)
            except Exception as e:
                log.error(f"Groq Fetch Error: {e}")
                return []

    async def fetch_openrouter_data(self) -> List[Dict[str, Any]]:
        timeout = httpx.Timeout(25.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.get(self.OPENROUTER_MODELS_URL)
                if resp.status_code != 200:
                    log.error(f"OpenRouter models fetch failed: HTTP {resp.status_code}")
                    return []

                data = resp.json().get("data", [])
                results: List[Dict[str, Any]] = []

                for m in data:
                    mid = (m.get("id") or "").strip()
                    if not mid:
                        continue

                    api_name = (m.get("name") or "").strip()
                    canonical = (m.get("canonical_slug") or "").strip() or None

                    context_len = m.get("context_length") or 0
                    try:
                        context_len = int(context_len)
                    except Exception:
                        context_len = 0

                    pricing = m.get("pricing", {}) or {}
                    try:
                        # OpenRouter pricing fields are commonly strings; values are per-token.
                        p = float(pricing.get("prompt", "0")) * 1_000_000
                        c = float(pricing.get("completion", "0")) * 1_000_000
                    except Exception:
                        p = 0.0
                        c = 0.0

                    supported = m.get("supported_parameters", []) or []
                    if not isinstance(supported, list):
                        supported = []

                    if "stream" not in supported:
                        supported = list(supported) + ["stream"]

                    specs = self._get_openrouter_specs(mid, supported)

                    friendly = derive_display_name(
                        mid,
                        provider="openrouter",
                        api_name=api_name,
                        canonical_slug=canonical,
                    )

                    results.append(
                        {
                            "id": mid,
                            "name": friendly,  # IMPORTANT: display name lives here
                            "context_length": context_len,
                            "pricing": {"prompt": float(p), "completion": float(c), "unit": "1M tokens"},
                            "supported_parameters": supported,
                            "parameter_specs": specs,
                        }
                    )

                return _sort_models(results)
            except Exception as e:
                log.error(f"OpenRouter Fetch Error: {e}")
                return []

    # -------------------------
    # Cache lifecycle
    # -------------------------

    async def refresh_cache(self) -> None:
        log.info("Refreshing model cache (providers: groq, openrouter)...")

        groq_task = asyncio.create_task(self.fetch_groq_data())
        or_task = asyncio.create_task(self.fetch_openrouter_data())
        groq_models, or_models = await asyncio.gather(groq_task, or_task)

        structured_data = [
            {"name": "groq", "models": groq_models or []},
            {"name": "openrouter", "models": or_models or []},
        ]

        await self.redis.set(self.CACHE_KEY, json.dumps(structured_data))

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
                log.error(f"Model cache refresh failed: {e}")
            await asyncio.sleep(self.REFRESH_INTERVAL)

    async def close(self) -> None:
        await self.redis.close()


model_service = ModelService()
