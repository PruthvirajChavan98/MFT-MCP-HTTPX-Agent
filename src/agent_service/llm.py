# ===== llm.py =====
from __future__ import annotations

import asyncio
from typing import Any, Dict, Iterable, List, Optional, Set

import httpx
from langchain_deepseek import ChatDeepSeek
from langchain_groq import ChatGroq
from langchain_nvidia_ai_endpoints import ChatNVIDIA

from .config import (
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
# LLM factory (unchanged)
# -----------------------------

def get_llm(
    model_name: str = None,  # type: ignore
    openrouter_api_key: str = None,  # type: ignore
    nvidia_api_key: str = None,  # type: ignore
    reasoning_effort: str = None,  # type: ignore
):
    target_model = model_name or MODEL_NAME

    effective_nvidia_key = nvidia_api_key or NVIDIA_API_KEY
    effective_openrouter_key = openrouter_api_key or OPENROUTER_API_KEY

    has_user_nvidia_key = bool(nvidia_api_key)
    has_user_or_key = bool(openrouter_api_key)

    use_nvidia = False
    use_groq = False

    if effective_nvidia_key and not has_user_or_key:
        mid = target_model.lower()
        if has_user_nvidia_key:
            use_nvidia = True
        elif mid.startswith("nvidia/") or "gpt-oss" in mid:
            use_nvidia = True
        elif "deepseek" in mid and "r1" in mid:
            use_nvidia = True
        elif "openai" in mid and ("o1" in mid or "o3" in mid):
            use_nvidia = True

    if not use_nvidia:
        is_legacy_groq = "/" not in target_model
        if is_legacy_groq:
            use_groq = True
        elif not has_user_or_key and GROQ_KEY_CYCLE and target_model.lower().startswith("groq/"):
            use_groq = True

    if use_nvidia:
        if not effective_nvidia_key:
            raise ValueError("NVIDIA API Key required (BYOK or Server)")

        model_kwargs: Dict[str, Any] = {}
        mid = target_model.lower()
        is_reasoning = any(x in mid for x in ["r1", "o1", "o3", "gpt-oss"])
        if reasoning_effort and is_reasoning:
            model_kwargs["reasoning_effort"] = reasoning_effort

        return ChatNVIDIA(
            model=target_model,
            api_key=effective_nvidia_key,
            base_url=NVIDIA_BASE_URL,
            temperature=0.6,
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
        if "gpt-oss" in target_model:
            r_format = "parsed"
            r_effort = reasoning_effort or "medium"
        elif "qwen" in target_model:
            r_format = "parsed"
            r_effort = reasoning_effort or "default"
        elif "deepseek" in target_model:
            r_format = "raw"

        return ChatGroq(
            api_key=current_api_key,  # type: ignore
            base_url=GROQ_BASE_URL,
            model=target_model,
            streaming=True,
            temperature=0.6,
            reasoning_format=r_format,
            reasoning_effort=r_effort,
        )

    if not effective_openrouter_key:
        raise ValueError("OpenRouter API Key required")

    is_native = any(x in target_model.lower() for x in ["openai/o1", "openai/o3"])
    extra_body: Dict[str, Any] = {}

    if is_native:
        if reasoning_effort:
            extra_body["reasoning_effort"] = reasoning_effort
    else:
        extra_body["reasoning"] = {"enabled": True}

    return ChatDeepSeek(
        model=target_model,
        api_key=effective_openrouter_key,  # type: ignore
        api_base=OPENROUTER_BASE_URL,
        temperature=0.6,
        streaming=True,
        extra_body=extra_body,
    )

# -----------------------------
# Model fetching & caching utilities
# -----------------------------

def _uniq(seq: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for v in seq or []:
        s = str(v).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out

def _get_std_params() -> List[Dict[str, Any]]:
    return [
        {"name": "temperature", "type": "float", "min": 0.0, "max": 2.0, "default": 0.7},
        {"name": "max_tokens", "type": "int", "min": 1, "max": 32000, "default": 4096},
    ]

def _build_groq_override_map(payload: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    root = (payload or {}).get("data", {}) or {}
    providers = root.get("models", []) or []
    for p in providers:
        if str(p.get("name") or "").strip().lower() != "groq":
            continue
        for m in (p.get("models") or []):
            mid = str(m.get("id") or "").strip()
            specs = m.get("parameterSpecs") or []
            if mid and isinstance(specs, list):
                out[mid] = specs
    return out

def _default_for_enum(name: str, options: List[str]) -> Optional[str]:
    name = (name or "").strip().lower()
    opts = [str(o).strip().lower() for o in (options or []) if str(o).strip()]
    s = set(opts)

    if name == "reasoning_effort":
        if s == {"low", "medium", "high"}:
            return "medium"
        if s == {"default", "none"}:
            return "default"

    if name == "tool_choice":
        return "auto" if "auto" in s else (opts[0] if opts else None)

    return opts[0] if opts else None

def _normalize_param_specs_from_overlay(
    overlay_specs: List[Dict[str, Any]],
    *,
    std_specs: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    std_specs = std_specs or []
    std_map = {str(p.get("name")): dict(p) for p in std_specs if isinstance(p, dict) and p.get("name")}

    out: List[Dict[str, Any]] = []
    for p in overlay_specs or []:
        name = str(p.get("name") or "").strip()
        if not name:
            continue
        options = p.get("options", None)

        if isinstance(options, list) and options:
            default = _default_for_enum(name, options)
            out.append({"name": name, "type": "enum", "options": options, "default": default})
            continue

        if name in std_map:
            out.append(std_map[name])
            continue

        if name == "temperature":
            out.append({"name": "temperature", "type": "float", "min": 0.0, "max": 2.0, "default": 0.7})
        elif name == "max_tokens":
            out.append({"name": "max_tokens", "type": "int", "min": 1, "max": 32000, "default": 4096})
        else:
            out.append({"name": name, "type": "string", "default": None})

    return out

def _ensure_tool_specs(specs: List[Dict[str, Any]], *, provider: str) -> List[Dict[str, Any]]:
    names = {str(s.get("name") or "").strip() for s in (specs or []) if isinstance(s, dict)}

    if "tool_calling_enabled" not in names:
        specs.append({"name": "tool_calling_enabled", "type": "boolean", "default": "true"})
    if "tool_choice" not in names:
        specs.append({"name": "tool_choice", "type": "enum", "options": ["auto", "none"], "default": "auto"})
    if provider == "groq" and "disable_tool_validation" not in names:
        specs.append({"name": "disable_tool_validation", "type": "boolean", "default": "false"})

    return specs

_GROQ_OVERRIDE_MAP = _build_groq_override_map(GROQ_PARAMETER_SPECS_PAYLOAD)

async def fetch_groq_models() -> dict:
    if not GROQ_API_KEYS:
        return {"data": [], "count": 0}

    maintenance_key = GROQ_API_KEYS[0]
    url = f"{GROQ_BASE_URL}/openai/v1/models"
    headers = {"Authorization": f"Bearer {maintenance_key}"}

    std_specs = _get_std_params()

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers, timeout=10.0)
            if resp.status_code != 200:
                return {"data": [], "count": 0}

            data = resp.json().get("data", []) or []
            models: List[Dict[str, Any]] = []

            for m in data:
                mid = str(m.get("id") or "").strip()
                if not mid or "whisper" in mid.lower():
                    continue

                specs = list(std_specs)
                low = mid.lower()

                if "gpt-oss" in low:
                    specs.append({"name": "reasoning_effort", "type": "enum", "options": ["low", "medium", "high"], "default": "medium"})
                elif "qwen" in low:
                    specs.append({"name": "reasoning_effort", "type": "enum", "options": ["default", "none"], "default": "default"})
                    specs.append({"name": "reasoning_format", "type": "enum", "options": ["parsed", "raw", "hidden"], "default": "parsed"})
                elif "deepseek" in low:
                    specs.append({"name": "reasoning_format", "type": "enum", "options": ["raw"], "default": "raw"})

                ov = _GROQ_OVERRIDE_MAP.get(mid)
                if ov:
                    specs = _normalize_param_specs_from_overlay(ov, std_specs=std_specs)

                specs = _ensure_tool_specs(specs, provider="groq")
                supported = _uniq([s["name"] for s in specs if isinstance(s, dict) and s.get("name")] + ["stream"])

                models.append({
                    "id": mid,
                    "name": mid,
                    "provider": "groq",
                    "context_length": int(m.get("context_window") or 0),
                    "pricing": {"prompt": 0.0, "completion": 0.0, "unit": "1M tokens"},
                    "supported_parameters": supported,
                    "parameter_specs": specs,
                })

            return {"data": models, "count": len(models)}
        except Exception:
            return {"data": [], "count": 0}

async def fetch_nvidia_models() -> dict:
    if not NVIDIA_API_KEY:
        return {"data": [], "count": 0}

    url = f"{NVIDIA_BASE_URL}/models"
    headers = {"Authorization": f"Bearer {NVIDIA_API_KEY}", "Accept": "application/json"}

    std_specs = _get_std_params()

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers, timeout=10.0)
            if resp.status_code != 200:
                return {"data": [], "count": 0}

            data = resp.json().get("data", []) or []
            models: List[Dict[str, Any]] = []

            for m in data:
                mid = str(m.get("id") or "").strip()
                if not mid:
                    continue

                specs = list(std_specs)

                low = mid.lower()
                is_r1 = ("deepseek" in low and "r1" in low)
                is_o = ("openai" in low and ("o1" in low or "o3" in low))
                is_oss = ("gpt-oss" in low)

                if is_r1 or is_o or is_oss:
                    specs.append({"name": "reasoning_effort", "type": "enum", "options": ["low", "medium", "high"], "default": "high" if is_r1 else "medium"})

                specs = _ensure_tool_specs(specs, provider="nvidia")
                supported = _uniq([s["name"] for s in specs if isinstance(s, dict) and s.get("name")] + ["stream"])

                name = mid.split("/")[-1] if "/" in mid else mid

                models.append({
                    "id": mid,
                    "name": f"NVIDIA {name}",
                    "provider": "nvidia",
                    "context_length": int(m.get("context_window", 32768) or 0),
                    "pricing": {"prompt": 0.0, "completion": 0.0, "unit": "1M tokens"},
                    "supported_parameters": supported,
                    "parameter_specs": specs,
                })

            return {"data": models, "count": len(models)}
        except Exception:
            return {"data": [], "count": 0}

async def fetch_openrouter_models() -> dict:
    url = "https://openrouter.ai/api/v1/models"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=15.0)
            if resp.status_code != 200:
                return {"data": [], "count": 0}

            data = resp.json().get("data", []) or []
            results: List[Dict[str, Any]] = []
            specs = _get_std_params()

            for m in data:
                pricing = m.get("pricing", {}) or {}
                try:
                    p = float(pricing.get("prompt", "0")) * 1_000_000
                    c = float(pricing.get("completion", "0")) * 1_000_000
                except Exception:
                    p = c = 0.0

                results.append({
                    "id": m["id"],
                    "name": m.get("name", m["id"]),
                    "provider": "openrouter",
                    "context_length": int(m.get("context_length", 0) or 0),
                    "pricing": {"prompt": float(p), "completion": float(c), "unit": "1M tokens"},
                    "supported_parameters": (m.get("supported_parameters", []) or []) + ["temperature", "max_tokens", "stream"],
                    "parameter_specs": specs,
                })

            results.sort(key=lambda x: float(x["pricing"]["prompt"]))
            return {"data": results, "count": len(results)}
        except Exception:
            return {"data": [], "count": 0}

async def get_available_models() -> dict:
    g_res, n_res, o_res = await asyncio.gather(
        fetch_groq_models(),
        fetch_nvidia_models(),
        fetch_openrouter_models(),
    )
    combined = g_res.get("data", []) + n_res.get("data", []) + o_res.get("data", [])
    return {"data": combined, "count": len(combined)}
