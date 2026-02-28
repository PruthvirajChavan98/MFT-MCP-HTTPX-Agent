"""Backward-compatible utility exports for legacy test/module imports."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import RemoveMessage

from src.agent_service.core.config import KEEP_LAST
from src.agent_service.core.session_utils import valid_session_id
from src.agent_service.core.utils import normalize_result as core_normalize_result


def keep_only_last_n_messages(state: dict, _config: dict) -> dict[str, list[RemoveMessage]]:
    """
    Legacy reducer: remove old messages while keeping the latest KEEP_LAST.

    Expects `state` to contain `messages`, each having a stable `id`.
    """
    messages = state.get("messages", [])
    if not isinstance(messages, list):
        return {"messages": []}

    excess = max(0, len(messages) - KEEP_LAST)
    to_remove: list[RemoveMessage] = []
    for msg in messages[:excess]:
        msg_id = getattr(msg, "id", None)
        if msg_id is not None:
            to_remove.append(RemoveMessage(id=str(msg_id)))
    return {"messages": to_remove}


def normalize_result_compat(result: Any) -> Any:
    """Compatibility wrapper for modules importing from src.agent_service.utils."""
    return core_normalize_result(result)


# Keep legacy import paths stable.
normalize_result = normalize_result_compat

__all__ = [
    "keep_only_last_n_messages",
    "normalize_result",
    "valid_session_id",
]
