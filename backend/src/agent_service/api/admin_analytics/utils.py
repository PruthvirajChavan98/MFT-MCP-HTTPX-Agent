"""Shared helpers used across admin-analytics domain modules."""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def _json_load_maybe(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return value
    if (stripped.startswith("{") and stripped.endswith("}")) or (
        stripped.startswith("[") and stripped.endswith("]")
    ):
        try:
            return json.loads(stripped)
        except Exception as exc:
            logger.debug("_json_load_maybe parse fallback: %s", exc)
            return value
    return value


def _encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=True, default=str).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def _decode_cursor(cursor: str | None, *, operation: str) -> dict[str, Any] | None:
    if not cursor:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Cursor payload must be an object.")
        return parsed
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cursor for {operation}.",
        ) from exc


def _extract_question_preview(inputs_json: Any) -> str:
    parsed = _json_load_maybe(inputs_json)
    if isinstance(parsed, dict):
        question = parsed.get("question") or parsed.get("input")
        return str(question or "").strip()
    if isinstance(parsed, str):
        text = parsed.strip()
        return text
    return ""


async def _pg_rows(pool: Any, query: str, *args: Any) -> list[dict[str, Any]]:
    try:
        rows = await pool.fetch(query, *args)
        return [dict(r) for r in rows]
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc


def _coerce_guardrail_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_iso_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None
