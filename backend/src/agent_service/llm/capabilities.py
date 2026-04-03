from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Optional

_TOOL_PARAMETER_MARKERS = {
    "tool_calling_enabled",
    "tool_choice",
    "tools",
    "parallel_tool_calls",
}

_REASONING_EFFORT_FAMILY_PATTERNS = (
    re.compile(r"(^|/)gpt-oss", re.IGNORECASE),
    re.compile(r"(^|/)o[134](?:-mini)?(?:$|[^a-z0-9])", re.IGNORECASE),
    re.compile(r"deepseek-r1", re.IGNORECASE),
    re.compile(r"(^|/)qwq", re.IGNORECASE),
    re.compile(r"(^|/)qwen(?:[-_/]|\d)", re.IGNORECASE),
    re.compile(r"reasoner", re.IGNORECASE),
)

_REASONING_MODEL_PATTERNS = _REASONING_EFFORT_FAMILY_PATTERNS + (
    re.compile(r"reasoning", re.IGNORECASE),
)


def _normalized_names(values: Iterable[Any]) -> set[str]:
    out: set[str] = set()
    for value in values:
        if value is None:
            continue
        name = str(value).strip().lower()
        if name:
            out.add(name)
    return out


def _parameter_names(parameter_specs: Iterable[dict[str, Any]] | None) -> set[str]:
    if not parameter_specs:
        return set()
    return _normalized_names(spec.get("name") for spec in parameter_specs if isinstance(spec, dict))


def infer_model_capabilities(
    *,
    model_id: str,
    provider: Optional[str] = None,
    supported_parameters: Iterable[Any] | None = None,
    parameter_specs: Iterable[dict[str, Any]] | None = None,
    model_type: Optional[str] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    supported = _normalized_names(supported_parameters or [])
    spec_names = _parameter_names(parameter_specs)
    combined = supported | spec_names
    target = " ".join(
        part
        for part in (
            str(provider or "").strip(),
            str(model_id or "").strip(),
            str(name or "").strip(),
            str(model_type or "").strip(),
        )
        if part
    )

    supports_reasoning_effort = "reasoning_effort" in combined or any(
        pattern.search(target) for pattern in _REASONING_EFFORT_FAMILY_PATTERNS
    )
    is_reasoning_model = (
        supports_reasoning_effort
        or str(model_type or "").strip().lower() == "reasoning"
        or any(name.startswith("reasoning") for name in combined)
        or any(pattern.search(target) for pattern in _REASONING_MODEL_PATTERNS)
    )
    supports_tools = any(marker in combined for marker in _TOOL_PARAMETER_MARKERS)

    if is_reasoning_model and supports_tools:
        emoji = "🧠🛠️"
    elif is_reasoning_model:
        emoji = "🧠"
    elif supports_tools:
        emoji = "🛠️"
    else:
        emoji = "💬"

    return {
        "is_reasoning_model": is_reasoning_model,
        "supports_reasoning_effort": supports_reasoning_effort,
        "supports_tools": supports_tools,
        "emoji": emoji,
    }


def decorate_model_name(base_name: str, capabilities: Dict[str, Any]) -> str:
    name = (base_name or "").strip()
    emoji = str(capabilities.get("emoji") or "").strip()
    if not emoji:
        return name
    return f"{emoji} {name}".strip()


def model_supports_reasoning_effort(
    model_name: str,
    *,
    provider: Optional[str] = None,
) -> bool:
    return bool(
        infer_model_capabilities(model_id=model_name, provider=provider).get(
            "supports_reasoning_effort"
        )
    )
