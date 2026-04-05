"""Trace analytics endpoints: traces list, trace detail, session traces."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from prometheus_client import Counter, Histogram

from src.agent_service.api.admin_auth import require_admin_key
from src.agent_service.core.follow_ups import normalize_follow_up_content
from src.agent_service.eval_store.status import build_eval_status_payload

from .repo import analytics_repo
from .utils import (
    _decode_cursor,
    _encode_cursor,
    _extract_question_preview,
    _json_load_maybe,
    _parse_iso_timestamp,
)

router = APIRouter(
    prefix="/agent/admin/analytics",
    tags=["admin-analytics"],
    dependencies=[Depends(require_admin_key)],
)
logger = logging.getLogger(__name__)

ADMIN_TRACE_QUERY_DURATION_SECONDS = Histogram(
    "agent_admin_trace_query_duration_seconds",
    "Admin trace query latency.",
    ["endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

ADMIN_TRACE_RESOLVE_SOURCE_TOTAL = Counter(
    "agent_admin_trace_resolve_source_total",
    "Admin trace detail resolver source usage.",
    ["source"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_text_content(content: Any) -> str:
    """Extract plain text from LangChain message content.

    AI messages with tool calls may store content as a list of typed blocks,
    e.g. ``[{"type": "text", "text": "..."}, {"type": "tool_use", ...}]``.
    This helper normalises both the ``str`` and ``list[dict]`` forms into a
    single text string, discarding non-text blocks so that raw tool-call
    JSON never leaks into the rendered message content.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            # skip tool_use / image / other non-text blocks
        return "\n".join(parts)
    return str(content)


def _build_tool_call_lookup(
    messages: list[Any],
) -> dict[int, list[dict[str, str]]]:
    """Build a mapping from AI-message index to resolved ``toolCalls``.

    Iterates the checkpoint message list once and pairs each ``ToolMessage``
    with the tool-call request on the preceding ``AIMessage`` using
    ``tool_call_id``.  The returned dict is keyed by the *enumerate index*
    (1-based, matching the serialisation loop) so the caller can cheaply look
    up whether a given AI message has tool calls.

    Each entry in the list matches the frontend ``ToolCallEvent`` shape::

        {"name": str, "output": str, "tool_call_id": str}
    """
    # Phase 1: index AI-message tool-call requests by tool_call_id.
    # Each value is (ai_message_enumerate_index, tool_call_name).
    request_index: dict[str, tuple[int, str]] = {}
    for idx, msg in enumerate(messages, start=1):
        if getattr(msg, "type", "") != "ai":
            continue
        # LangChain stores parsed tool calls on the ``tool_calls`` attribute
        # (preferred) and also mirrors them in ``additional_kwargs["tool_calls"]``.
        raw_tool_calls: list[dict[str, Any]] = getattr(msg, "tool_calls", []) or []
        if not raw_tool_calls:
            raw_tool_calls = getattr(msg, "additional_kwargs", {}).get("tool_calls") or []
        for tc in raw_tool_calls:
            tc_id = str(tc.get("id") or "").strip()
            tc_name = str(tc.get("name") or "tool").strip()
            if tc_id:
                request_index[tc_id] = (idx, tc_name)

    if not request_index:
        return {}

    # Phase 2: walk ToolMessages and resolve outputs.
    result: dict[int, list[dict[str, str]]] = {}
    for msg in messages:
        if getattr(msg, "type", "") != "tool":
            continue
        tc_id = str(getattr(msg, "tool_call_id", "") or "").strip()
        if not tc_id or tc_id not in request_index:
            continue
        ai_idx, tc_name = request_index[tc_id]
        raw_output = getattr(msg, "content", "")
        output_str = (
            raw_output
            if isinstance(raw_output, str)
            else json.dumps(raw_output, ensure_ascii=False, default=str)
        )
        result.setdefault(ai_idx, []).append(
            {"name": tc_name, "output": output_str, "tool_call_id": tc_id}
        )
    return result


def _to_admin_eval_status(payload: dict[str, Any]) -> dict[str, Any]:
    inline_evals = payload.get("inline_evals") or {}
    return {
        "status": payload["status"],
        "reason": payload.get("reason"),
        "passed": inline_evals.get("passed"),
        "failed": inline_evals.get("failed"),
        "shadowJudge": payload.get("shadow_judge"),
    }


async def _load_session_eval_statuses(
    pool: Any, items: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    trace_ids = [
        str(item.get("traceId")).strip()
        for item in items
        if item.get("role") == "assistant" and str(item.get("traceId") or "").strip()
    ]
    unique_trace_ids = list(dict.fromkeys(trace_ids))
    if not unique_trace_ids:
        return {}

    trace_rows = await analytics_repo.fetch_session_eval_traces(pool, unique_trace_ids)
    inline_rows = await analytics_repo.fetch_session_eval_results(pool, unique_trace_ids)
    shadow_rows = await analytics_repo.fetch_session_shadow_judges(pool, unique_trace_ids)

    trace_by_id = {str(row["trace_id"]): row for row in trace_rows}
    shadow_by_id = {str(row["trace_id"]): row for row in shadow_rows}
    inline_by_id: dict[str, list[dict[str, Any]]] = {}
    for row in inline_rows:
        inline_by_id.setdefault(str(row["trace_id"]), []).append(row)

    return {
        trace_id: _to_admin_eval_status(
            build_eval_status_payload(
                trace_id=trace_id,
                trace_row=trace_by_id.get(trace_id),
                result_rows=inline_by_id.get(trace_id, []),
                shadow_row=shadow_by_id.get(trace_id),
            )
        )
        for trace_id in unique_trace_ids
    }


async def _checkpoint_trace_detail(request: Request, trace_id: str) -> dict[str, Any]:
    checkpointer = getattr(request.app.state, "checkpointer", None)
    if not checkpointer:
        raise HTTPException(status_code=503, detail="Checkpointer unavailable")

    if "~" not in trace_id:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid trace_id format: expected '{{session_id}}~N', got '{trace_id}'",
        )

    session_id, idx_str = trace_id.rsplit("~", 1)
    try:
        target_idx = int(idx_str)
    except ValueError as err:
        raise HTTPException(
            status_code=400, detail=f"Invalid index in trace_id: '{idx_str}'"
        ) from err

    config = {"configurable": {"thread_id": session_id}}
    ckp = await checkpointer.aget_tuple(config)
    if not ckp or not ckp.checkpoint:
        raise HTTPException(status_code=404, detail="Session not found")

    state = ckp.checkpoint.get("channel_values", {})
    messages = state.get("messages", [])
    if target_idx < 1 or target_idx > len(messages):
        raise HTTPException(
            status_code=404,
            detail=f"Message #{target_idx} not found in session '{session_id}' (has {len(messages)} messages)",
        )

    msg = messages[target_idx - 1]
    msg_type = getattr(msg, "type", "")
    content = getattr(msg, "content", "")
    add_kwargs = getattr(msg, "additional_kwargs", {})
    resp_meta = getattr(msg, "response_metadata", {})

    question = ""
    for i in range(target_idx - 2, -1, -1):
        prev = messages[i]
        if getattr(prev, "type", "") == "human":
            question = getattr(prev, "content", "")
            break

    reasoning = (
        add_kwargs.get("reasoning", "")
        or add_kwargs.get("reasoning_content", "")
        or resp_meta.get("reasoning", "")
    )
    content, _ = normalize_follow_up_content(content, add_kwargs.get("follow_ups"))

    events = []
    if reasoning:
        events.append({"event_type": "reasoning", "name": "reasoning", "text": reasoning})
    if content:
        events.append({"event_type": "token", "name": "token", "text": content})

    created = resp_meta.get("created")
    started_at = datetime.fromtimestamp(created, tz=timezone.utc).isoformat() if created else None
    return {
        "trace": {
            "trace_id": trace_id,
            "session_id": session_id,
            "name": f"Agent Turn #{target_idx}",
            "model": resp_meta.get("model_name", "unknown"),
            "provider": resp_meta.get("model_provider", "unknown"),
            "status": "success" if msg_type == "ai" else msg_type,
            "started_at": started_at,
            "latency_ms": 0,
            "inputs_json": {"question": question},
            "final_output": content,
        },
        "events": events,
        "evals": [],
        "shadow_judge": None,
    }


async def _eval_trace_detail(pool: Any, trace_id: str) -> dict[str, Any] | None:
    trace_rows = await analytics_repo.fetch_trace_by_id(pool, trace_id)
    if not trace_rows:
        return None

    trace_obj = trace_rows[0]
    for key in ("inputs_json", "tags_json", "meta_json"):
        trace_obj[key] = _json_load_maybe(trace_obj.get(key))

    event_rows = await analytics_repo.fetch_trace_events(pool, trace_id)
    for event in event_rows:
        event["payload_json"] = _json_load_maybe(event.get("payload_json"))
        event["meta_json"] = _json_load_maybe(event.get("meta_json"))

    eval_rows = await analytics_repo.fetch_trace_eval_results(pool, trace_id)
    for eval_row in eval_rows:
        eval_row["meta_json"] = _json_load_maybe(eval_row.get("meta_json"))
        eval_row["evidence_json"] = _json_load_maybe(eval_row.get("evidence_json"))

    shadow_rows = await analytics_repo.fetch_trace_shadow_judge(pool, trace_id)
    shadow_judge = dict(shadow_rows[0]) if shadow_rows else None
    if shadow_judge and shadow_judge.get("evaluated_at"):
        evaluated_at = shadow_judge["evaluated_at"]
        shadow_judge["evaluated_at"] = (
            evaluated_at.isoformat() if hasattr(evaluated_at, "isoformat") else str(evaluated_at)
        )

    return {
        "trace": trace_obj,
        "events": event_rows,
        "evals": eval_rows,
        "shadow_judge": shadow_judge,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/session/{session_id}")
async def session_traces(
    request: Request, session_id: str, limit: int = Query(default=500, ge=1, le=2000)
):
    """Return all messages for a session with sequential trace IDs."""
    checkpointer = getattr(request.app.state, "checkpointer", None)
    if not checkpointer:
        raise HTTPException(status_code=503, detail="Checkpointer unavailable")

    config = {"configurable": {"thread_id": session_id}}
    ckp = await checkpointer.aget_tuple(config)

    items = []
    pool = getattr(request.app.state, "pool", None)

    if ckp and ckp.checkpoint:
        state = ckp.checkpoint.get("channel_values", {})
        messages = state.get("messages", [])

        # Pre-compute tool-call lookup so AI messages include resolved outputs.
        tool_call_lookup = _build_tool_call_lookup(messages)

        for idx, msg in enumerate(messages, start=1):
            msg_type = getattr(msg, "type", "")

            # Skip ToolMessages -- their output is attached to the preceding
            # AI message via the ``toolCalls`` field.
            if msg_type == "tool":
                continue

            content = _extract_text_content(getattr(msg, "content", ""))
            add_kwargs = getattr(msg, "additional_kwargs", {})
            resp_meta = getattr(msg, "response_metadata", {})
            role = (
                "user" if msg_type == "human" else ("assistant" if msg_type == "ai" else msg_type)
            )

            created = resp_meta.get("created")
            timestamp = int(created * 1000) if created else 0

            reasoning = (
                add_kwargs.get("reasoning", "")
                or add_kwargs.get("reasoning_content", "")
                or resp_meta.get("reasoning", "")
            )
            if msg_type == "ai":
                content, follow_ups = normalize_follow_up_content(
                    content,
                    add_kwargs.get("follow_ups"),
                    limit=8,
                )
            else:
                follow_ups = []

            cost = add_kwargs.get("cost")
            if not isinstance(cost, dict):
                cost = None

            trace_id = str(add_kwargs.get("trace_id") or "").strip() or None
            provider = (
                str(add_kwargs.get("provider") or resp_meta.get("model_provider") or "").strip()
                or None
            )
            model = (
                str(add_kwargs.get("model") or resp_meta.get("model_name") or "").strip() or None
            )
            total_tokens_raw = add_kwargs.get("total_tokens")
            try:
                total_tokens = int(total_tokens_raw) if total_tokens_raw is not None else None
            except (TypeError, ValueError):
                total_tokens = None

            seq_id = f"{session_id}~{idx}"

            # Resolved tool calls for this AI message (empty list for non-AI).
            tool_calls = tool_call_lookup.get(idx, []) if msg_type == "ai" else []

            item: dict[str, Any] = {
                "id": seq_id,
                "role": role,
                "content": content,
                "reasoning": reasoning,
                "timestamp": timestamp,
                "status": "done",
                "followUps": follow_ups[:8],
                "cost": cost,
                "provider": provider,
                "model": model,
                "totalTokens": total_tokens,
            }
            if trace_id:
                item["traceId"] = trace_id
            if tool_calls:
                item["toolCalls"] = tool_calls
            items.append(item)

        # Merge consecutive assistant messages produced by LangGraph's ReAct loop.
        # A tool-using turn produces: AIMessage(tool_calls) → ToolMessage → AIMessage(text).
        # After skipping ToolMessages above, this leaves two adjacent assistant items:
        #   [i]   has toolCalls but empty content (the tool-call request)
        #   [i+1] has content but no toolCalls  (the final text response)
        # Merge them into a single item so the frontend renders one bubble.
        merged: list[dict[str, Any]] = []
        i = 0
        while i < len(items):
            cur = items[i]
            nxt = items[i + 1] if i + 1 < len(items) else None
            if (
                nxt is not None
                and cur.get("role") == "assistant"
                and nxt.get("role") == "assistant"
                and cur.get("toolCalls")
            ):
                # Merge: keep the second item (final response) as base,
                # attach toolCalls from the first (tool-calling step).
                nxt["toolCalls"] = cur["toolCalls"]
                # Preserve reasoning from tool-call step if response has none.
                if cur.get("reasoning") and not nxt.get("reasoning", "").strip():
                    nxt["reasoning"] = cur["reasoning"]
                merged.append(nxt)
                i += 2
            else:
                merged.append(cur)
                i += 1
        items = merged

    if not items:
        # Fallback for sessions with missing checkpointer data: reconstruct from eval_traces.
        rows = await analytics_repo.fetch_session_traces_fallback(pool, session_id, limit)
        for idx, row in enumerate(rows, start=1):
            started_at = _parse_iso_timestamp(row.get("started_at"))
            timestamp = int(started_at.timestamp() * 1000) if started_at else 0
            question = _extract_question_preview(row.get("inputs_json"))
            if question:
                items.append(
                    {
                        "id": f"{session_id}~{idx*2-1}",
                        "role": "user",
                        "content": question,
                        "reasoning": "",
                        "timestamp": timestamp,
                        "status": "done",
                        "traceId": row.get("trace_id"),
                    }
                )
            meta_obj = _json_load_maybe(row.get("meta_json"))
            inline_guard = meta_obj.get("inline_guard") if isinstance(meta_obj, dict) else None
            inline_reason = ""
            if isinstance(inline_guard, dict):
                inline_reason = str(inline_guard.get("reason_code") or "")
            final_output, fallback_follow_ups = normalize_follow_up_content(
                row.get("final_output") or "",
                None,
                limit=8,
            )
            items.append(
                {
                    "id": f"{session_id}~{idx*2}",
                    "role": "assistant",
                    "content": final_output,
                    "reasoning": inline_reason,
                    "timestamp": timestamp,
                    "status": (
                        "error" if str(row.get("status") or "").lower() == "error" else "done"
                    ),
                    "traceId": row.get("trace_id"),
                    "followUps": fallback_follow_ups,
                    "provider": row.get("provider"),
                    "model": row.get("model"),
                }
            )

    items = items[:limit]
    if pool:
        eval_statuses = await _load_session_eval_statuses(pool, items)
        for item in items:
            trace_id = str(item.get("traceId") or "").strip()
            if item.get("role") == "assistant" and trace_id in eval_statuses:
                item["evalStatus"] = eval_statuses[trace_id]
    return {"items": items, "count": len(items), "next_cursor": None}


@router.get("/traces")
async def traces(
    request: Request,
    limit: int = Query(default=200, ge=1, le=500),
    cursor: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None),
    model: str | None = Query(default=None),
):
    """Canonical flat list of traces from Eval store for /admin/traces."""
    started = time.perf_counter()
    try:
        parsed_cursor = _decode_cursor(cursor, operation="admin_traces")
        cursor_started_at = (
            str(parsed_cursor.get("started_at")).strip()
            if parsed_cursor and parsed_cursor.get("started_at")
            else None
        )
        cursor_trace_id = (
            str(parsed_cursor.get("trace_id")).strip()
            if parsed_cursor and parsed_cursor.get("trace_id")
            else None
        )
        normalized_search = search.strip().lower() if search and search.strip() else None
        normalized_status = status.strip().lower() if status and status.strip() else None
        normalized_model = model.strip() if model and model.strip() else None

        pool = request.app.state.pool
        search_pat = f"%{normalized_search}%" if normalized_search else None
        rows = await analytics_repo.fetch_traces_page(
            pool,
            status=normalized_status,
            model=normalized_model,
            search_pat=search_pat,
            cursor_started_at=cursor_started_at,
            cursor_trace_id=cursor_trace_id or "",
            limit=limit + 1,
        )

        has_more = len(rows) > limit
        page_rows = rows[:limit]
        items = []
        for row in page_rows:
            meta_obj = _json_load_maybe(row.get("meta_json"))
            reasoning = ""
            if isinstance(meta_obj, dict):
                reasoning = str(meta_obj.get("reasoning") or "")

            items.append(
                {
                    "trace_id": row.get("trace_id"),
                    "case_id": row.get("case_id"),
                    "session_id": row.get("session_id"),
                    "provider": row.get("provider"),
                    "model": row.get("model"),
                    "endpoint": row.get("endpoint"),
                    "started_at": row.get("started_at"),
                    "ended_at": row.get("ended_at"),
                    "latency_ms": row.get("latency_ms"),
                    "status": row.get("status") or ("error" if row.get("error") else "success"),
                    "error": row.get("error"),
                    "inputs_json": _json_load_maybe(row.get("inputs_json")),
                    "final_output": row.get("final_output"),
                    "reasoning": reasoning,
                }
            )

        next_cursor: str | None = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = _encode_cursor(
                {
                    "started_at": last.get("started_at"),
                    "trace_id": last.get("trace_id"),
                }
            )

        return {"items": items, "count": len(items), "limit": limit, "next_cursor": next_cursor}
    finally:
        ADMIN_TRACE_QUERY_DURATION_SECONDS.labels(endpoint="traces").observe(
            time.perf_counter() - started
        )


@router.get("/trace/{trace_id:path}")
async def trace_detail(request: Request, trace_id: str):
    """Resolve canonical eval trace IDs and legacy checkpoint trace IDs."""
    started = time.perf_counter()
    try:
        if "~" in trace_id:
            checkpoint_error: HTTPException | None = None
            try:
                detail = await _checkpoint_trace_detail(request, trace_id)
                ADMIN_TRACE_RESOLVE_SOURCE_TOTAL.labels(source="checkpoint").inc()
                return detail
            except HTTPException as exc:
                checkpoint_error = exc

            eval_detail = await _eval_trace_detail(request.app.state.pool, trace_id)
            if eval_detail:
                ADMIN_TRACE_RESOLVE_SOURCE_TOTAL.labels(source="eval").inc()
                return eval_detail

            ADMIN_TRACE_RESOLVE_SOURCE_TOTAL.labels(source="not_found").inc()
            if checkpoint_error is not None:
                raise checkpoint_error
            raise HTTPException(status_code=404, detail="Trace not found")

        eval_detail = await _eval_trace_detail(request.app.state.pool, trace_id)
        if eval_detail:
            ADMIN_TRACE_RESOLVE_SOURCE_TOTAL.labels(source="eval").inc()
            return eval_detail

        ADMIN_TRACE_RESOLVE_SOURCE_TOTAL.labels(source="not_found").inc()
        raise HTTPException(status_code=404, detail="Trace not found")
    finally:
        ADMIN_TRACE_QUERY_DURATION_SECONDS.labels(endpoint="trace_detail").observe(
            time.perf_counter() - started
        )
