from __future__ import annotations

import json
import re
from typing import Any

_FOLLOW_UPS_RE = re.compile(r"\n?FOLLOW_UPS:\s*(\[.*?\])\s*$", re.DOTALL)


def extract_follow_ups(text: str, *, limit: int = 5) -> tuple[str, list[str]]:
    """Strip ``FOLLOW_UPS:[...]`` from text and return parsed questions."""
    match = _FOLLOW_UPS_RE.search(text)
    if not match:
        return text, []
    try:
        questions = json.loads(match.group(1))
        if isinstance(questions, list):
            clean = text[: match.start()].rstrip()
            normalized = [str(question).strip() for question in questions if str(question).strip()]
            return clean, normalized[:limit]
    except (json.JSONDecodeError, TypeError):
        pass
    return text, []


def normalize_follow_up_content(
    content: str | None,
    follow_ups: list[Any] | None = None,
    *,
    limit: int = 8,
) -> tuple[str, list[str]]:
    """Return stripped content plus canonical follow-up suggestions."""
    text = content if isinstance(content, str) else ("" if content is None else str(content))
    clean_text, derived_follow_ups = extract_follow_ups(text, limit=limit)

    explicit_follow_ups: list[str] = []
    if isinstance(follow_ups, list):
        explicit_follow_ups = [
            str(question).strip() for question in follow_ups if str(question).strip()
        ][:limit]

    return clean_text, explicit_follow_ups or derived_follow_ups
