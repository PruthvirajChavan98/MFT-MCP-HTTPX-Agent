"""Conversations analytics endpoint: paginated session listing."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.agent_service.api.admin_auth import require_admin
from src.agent_service.core.config import ADMIN_CURSOR_APIS_V2

from .repo import analytics_repo
from .utils import _decode_cursor, _encode_cursor, _extract_question_preview

router = APIRouter(
    prefix="/agent/admin/analytics",
    tags=["admin-analytics"],
    dependencies=[Depends(require_admin)],
)
logger = logging.getLogger(__name__)


@router.get("/conversations")
async def conversations(
    request: Request,
    limit: int = Query(default=120, ge=1, le=500),
    cursor: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
):
    """List all sessions from the LangGraph Redis Checkpointer.

    Uses the public checkpointer.alist() API -- no private attributes,
    no Redis key parsing, no fragile patterns.
    """
    if ADMIN_CURSOR_APIS_V2:
        normalized_search = search.strip().lower() if search and search.strip() else None
        parsed_cursor = _decode_cursor(cursor, operation="admin_conversations")
        cursor_started_at = (
            str(parsed_cursor.get("started_at")).strip()
            if parsed_cursor and parsed_cursor.get("started_at")
            else None
        )
        cursor_session_id = (
            str(parsed_cursor.get("session_id")).strip()
            if parsed_cursor and parsed_cursor.get("session_id")
            else None
        )

        pool = request.app.state.pool
        search_pat = f"%{normalized_search}%" if normalized_search else None
        rows = await analytics_repo.fetch_conversations(
            pool,
            search_pat=search_pat,
            cursor_started_at=cursor_started_at,
            cursor_session_id=cursor_session_id or "",
            limit=limit + 1,
        )

        has_more = len(rows) > limit
        page_rows = rows[:limit]

        items = []
        for row in page_rows:
            items.append(
                {
                    "session_id": row.get("session_id"),
                    "started_at": row.get("started_at"),
                    "model": row.get("model"),
                    "provider": row.get("provider"),
                    "message_count": int(row.get("message_count") or 0),
                    "first_question": _extract_question_preview(row.get("inputs_json")),
                }
            )

        next_cursor: str | None = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = _encode_cursor(
                {
                    "started_at": last.get("started_at"),
                    "session_id": last.get("session_id"),
                }
            )

        return {
            "items": items,
            "count": len(items),
            "limit": limit,
            "next_cursor": next_cursor,
            "cursor_mode": "keyset",
        }

    checkpointer = getattr(request.app.state, "checkpointer", None)
    if not checkpointer:
        raise HTTPException(status_code=503, detail="Checkpointer unavailable")

    # alist(None) iterates ALL checkpoints across ALL threads (newest-first).
    # We deduplicate by thread_id so we only process the latest checkpoint per session.
    seen_threads: set[str] = set()
    items = []

    async for ckp_tuple in checkpointer.alist(None):
        tid = ckp_tuple.config.get("configurable", {}).get("thread_id", "")
        if not tid or tid in seen_threads:
            continue
        seen_threads.add(tid)

        try:
            checkpoint = ckp_tuple.checkpoint
            if not checkpoint:
                continue

            state = checkpoint.get("channel_values", {})
            messages = state.get("messages", [])
            if not messages:
                continue

            # Extract first user question as sidebar preview
            first_question = ""
            for msg in messages:
                if getattr(msg, "type", "") == "human":
                    first_question = getattr(msg, "content", "")
                    break

            # Extract model/provider from last AI message
            model = "unknown"
            provider = "unknown"
            last_ts = None
            for msg in reversed(messages):
                if getattr(msg, "type", "") == "ai":
                    resp_meta = getattr(msg, "response_metadata", {})
                    model = resp_meta.get("model_name", "unknown")
                    provider = resp_meta.get("model_provider", "unknown")
                    created = resp_meta.get("created")
                    if created:
                        last_ts = datetime.fromtimestamp(created, tz=timezone.utc).isoformat()
                    break

            # Use checkpoint timestamp as fallback
            if not last_ts:
                last_ts = checkpoint.get("ts")

            items.append(
                {
                    "session_id": tid,
                    "started_at": last_ts,
                    "model": model,
                    "provider": provider,
                    "message_count": len(messages),
                    "first_question": first_question,
                }
            )
        except Exception as exc:
            logger.debug("Skipping malformed checkpoint entry thread=%s: %s", tid, exc)
            continue

        if len(items) >= limit:
            break

    # Sort by most recent first
    items.sort(key=lambda x: x.get("started_at") or "", reverse=True)

    return {"items": items, "count": len(items), "limit": limit, "next_cursor": None}
