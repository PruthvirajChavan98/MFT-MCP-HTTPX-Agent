from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolExecutionPolicy:
    same_turn_dedupe: bool = False
    allow_transport_retry: bool = True


_DEFAULT_POLICY = ToolExecutionPolicy()

_TOOL_POLICIES: dict[str, ToolExecutionPolicy] = {
    "generate_otp": ToolExecutionPolicy(same_turn_dedupe=True, allow_transport_retry=False),
    "validate_otp": ToolExecutionPolicy(same_turn_dedupe=True, allow_transport_retry=False),
    "select_loan": ToolExecutionPolicy(same_turn_dedupe=True, allow_transport_retry=False),
    "download_welcome_letter": ToolExecutionPolicy(
        same_turn_dedupe=True, allow_transport_retry=False
    ),
    "download_soa": ToolExecutionPolicy(same_turn_dedupe=True, allow_transport_retry=False),
    "logout": ToolExecutionPolicy(same_turn_dedupe=True, allow_transport_retry=False),
}


def get_tool_execution_policy(tool_name: str) -> ToolExecutionPolicy:
    return _TOOL_POLICIES.get(tool_name, _DEFAULT_POLICY)


def build_same_turn_dedupe_key(tool_name: str, tool_args: Any) -> str:
    return f"{tool_name}:{_canonicalize_tool_args(tool_args)}"


def _canonicalize_tool_args(tool_args: Any) -> str:
    try:
        return json.dumps(tool_args, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except TypeError:
        normalized = _normalize_for_json(tool_args)
        return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normalize_for_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize_for_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize_for_json(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
