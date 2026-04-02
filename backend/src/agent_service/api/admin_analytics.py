from __future__ import annotations

import base64
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from prometheus_client import Counter, Histogram

from src.agent_service.api.admin_auth import require_admin_key
from src.agent_service.core.config import (
    ADMIN_CURSOR_APIS_V2,
    SHADOW_TRACE_DLQ_KEY,
    SHADOW_TRACE_QUEUE_KEY,
)
from src.agent_service.core.session_utils import get_redis

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

ADMIN_GUARDRAILS_QUERY_DURATION_SECONDS = Histogram(
    "agent_admin_guardrails_query_duration_seconds",
    "Guardrails analytics query latency.",
    ["endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

ADMIN_GUARDRAILS_QUERY_TOTAL = Counter(
    "agent_admin_guardrails_query_total",
    "Guardrails analytics query outcomes.",
    ["endpoint", "status"],
)


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
        except Exception:
            return value
    return value


def _encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
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


def _risk_level(score: float) -> str:
    if score >= 0.8:
        return "critical"
    if score >= 0.5:
        return "high"
    if score >= 0.3:
        return "medium"
    return "low"


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


def _extract_inline_guard_fields(row: dict[str, Any]) -> tuple[str | None, str | None, float]:
    decision = str(row.get("inline_guard_decision") or "").strip() or None
    reason_code = str(row.get("inline_guard_reason_code") or "").strip() or None
    risk_score = _coerce_guardrail_float(row.get("inline_guard_risk_score"), 0.0)

    if decision:
        return decision, reason_code, risk_score

    meta_obj = _json_load_maybe(row.get("meta_json"))
    inline_guard = meta_obj.get("inline_guard") if isinstance(meta_obj, dict) else None
    if isinstance(inline_guard, dict):
        decision = str(inline_guard.get("decision") or "").strip() or None
        reason_code = str(inline_guard.get("reason_code") or "").strip() or None
        risk_score = _coerce_guardrail_float(inline_guard.get("risk_score"), risk_score)
    return decision, reason_code, risk_score


async def _load_guardrail_trace_rows(
    pool: Any,
    *,
    limit: int,
    tenant_id: str,
    session_id: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[dict[str, Any]]:
    return await _pg_rows(
        pool,
        """
        SELECT
            trace_id, session_id, endpoint, started_at, meta_json,
            inline_guard_decision, inline_guard_reason_code, inline_guard_risk_score
        FROM eval_traces
        WHERE started_at IS NOT NULL
          AND ($1::text IS NULL OR session_id = $1)
          AND ($2 = 'default' OR case_id = $2)
          AND ($3::timestamptz IS NULL OR started_at >= $3)
          AND ($4::timestamptz IS NULL OR started_at <= $4)
          AND (
            inline_guard_decision IS NOT NULL
            OR meta_json::text LIKE '%"inline_guard"%'
          )
        ORDER BY started_at DESC
        LIMIT $5
        """,
        session_id,
        tenant_id,
        start,
        end,
        limit,
    )


def _as_guardrail_event(row: dict[str, Any]) -> dict[str, Any] | None:
    decision, reason_code, risk_score = _extract_inline_guard_fields(row)
    if not decision:
        return None

    event_time = _parse_iso_timestamp(row.get("started_at"))
    event_time_iso = event_time.isoformat() if event_time else None

    reasons: list[str] = [reason_code] if reason_code else []
    return {
        "trace_id": row.get("trace_id"),
        "event_time": event_time_iso,
        "session_id": row.get("session_id"),
        "risk_score": risk_score,
        "risk_decision": decision,
        "severity": _risk_level(risk_score),
        "request_path": row.get("endpoint"),
        "reasons": reasons,
    }


def _log_guardrails_query_failure(
    *,
    endpoint: str,
    tenant_id: str,
    exc: Exception,
    hours: int | None = None,
) -> None:
    logger.exception(
        "Guardrails analytics query failed",
        extra={
            "endpoint": endpoint,
            "tenant_id": tenant_id,
            "hours": hours,
            "error_class": exc.__class__.__name__,
            "error": str(exc),
        },
    )


@router.get("/overview")
async def overview(request: Request):
    pool = request.app.state.pool
    rows = await _pg_rows(
        pool,
        """
        SELECT
            COUNT(*)                                              AS traces,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count,
            AVG(COALESCE(latency_ms, 0))                         AS avg_latency_ms,
            MAX(started_at)                                      AS last_active
        FROM eval_traces
        """,
    )
    row = rows[0] if rows else {}
    traces = int(row.get("traces") or 0)
    success = int(row.get("success_count") or 0)
    return {
        "traces": traces,
        "success_rate": (success / traces) if traces else 0.0,
        "avg_latency_ms": float(row.get("avg_latency_ms") or 0.0),
        "last_active": row.get("last_active"),
    }


@router.get("/conversations")
async def conversations(
    request: Request,
    limit: int = Query(default=120, ge=1, le=500),
    cursor: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
):
    """List all sessions from the LangGraph Redis Checkpointer.

    Uses the public checkpointer.alist() API — no private attributes,
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
        rows = await _pg_rows(
            pool,
            """
            SELECT
                t.session_id,
                MAX(t.started_at) AS started_at,
                COUNT(*) AS message_count,
                (array_agg(t.model    ORDER BY t.started_at DESC))[1] AS model,
                (array_agg(t.provider ORDER BY t.started_at DESC))[1] AS provider,
                (array_agg(t.inputs_json ORDER BY t.started_at DESC))[1] AS inputs_json
            FROM eval_traces t
            WHERE t.session_id IS NOT NULL
              AND t.started_at IS NOT NULL
              AND (
                $1::text IS NULL
                OR LOWER(t.session_id)  LIKE $1
                OR LOWER(COALESCE(t.inputs_json::text, '')) LIKE $1
                OR LOWER(COALESCE(t.final_output, '')) LIKE $1
              )
            GROUP BY t.session_id
            HAVING (
                $2::timestamptz IS NULL
                OR MAX(t.started_at) < $2
                OR (MAX(t.started_at) = $2 AND t.session_id < $3)
            )
            ORDER BY started_at DESC, t.session_id DESC
            LIMIT $4
            """,
            search_pat,
            cursor_started_at,
            cursor_session_id or "",
            limit + 1,
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
        except Exception:
            continue

        if len(items) >= limit:
            break

    # Sort by most recent first
    items.sort(key=lambda x: x.get("started_at") or "", reverse=True)

    return {"items": items, "count": len(items), "limit": limit, "next_cursor": None}


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

    if ckp and ckp.checkpoint:
        state = ckp.checkpoint.get("channel_values", {})
        messages = state.get("messages", [])

        for idx, msg in enumerate(messages, start=1):
            msg_type = getattr(msg, "type", "")
            content = getattr(msg, "content", "")
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
            follow_ups = add_kwargs.get("follow_ups")
            if not isinstance(follow_ups, list):
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

            items.append(
                {
                    "id": seq_id,
                    "role": role,
                    "content": content,
                    "reasoning": reasoning,
                    "timestamp": timestamp,
                    "status": "done",
                    "traceId": trace_id or seq_id,
                    "followUps": follow_ups[:8],
                    "cost": cost,
                    "provider": provider,
                    "model": model,
                    "totalTokens": total_tokens,
                }
            )

    if not items:
        # Fallback for sessions with missing checkpointer data: reconstruct from eval_traces.
        pool = request.app.state.pool
        rows = await _pg_rows(
            pool,
            """
            SELECT trace_id, started_at, inputs_json, final_output,
                   status, model, provider, meta_json
            FROM eval_traces
            WHERE session_id = $1
            ORDER BY started_at ASC
            LIMIT $2
            """,
            session_id,
            limit,
        )
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
            items.append(
                {
                    "id": f"{session_id}~{idx*2}",
                    "role": "assistant",
                    "content": row.get("final_output") or "",
                    "reasoning": inline_reason,
                    "timestamp": timestamp,
                    "status": (
                        "error" if str(row.get("status") or "").lower() == "error" else "done"
                    ),
                    "traceId": row.get("trace_id"),
                    "provider": row.get("provider"),
                    "model": row.get("model"),
                }
            )

    items = items[:limit]
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
        rows = await _pg_rows(
            pool,
            """
            SELECT
                trace_id, case_id, session_id, provider, model, endpoint,
                started_at, ended_at, latency_ms, status, error,
                inputs_json, final_output, meta_json
            FROM eval_traces
            WHERE started_at IS NOT NULL
              AND ($1::text IS NULL OR LOWER(COALESCE(status, '')) = $1)
              AND ($2::text IS NULL OR COALESCE(model, '') = $2)
              AND (
                $3::text IS NULL
                OR LOWER(trace_id) LIKE $3
                OR LOWER(COALESCE(session_id, '')) LIKE $3
                OR LOWER(COALESCE(inputs_json::text, '')) LIKE $3
                OR LOWER(COALESCE(final_output, '')) LIKE $3
              )
              AND (
                $4::timestamptz IS NULL
                OR started_at < $4
                OR (started_at = $4 AND trace_id < $5)
              )
            ORDER BY started_at DESC, trace_id DESC
            LIMIT $6
            """,
            normalized_status,
            normalized_model,
            search_pat,
            cursor_started_at,
            cursor_trace_id or "",
            limit + 1,
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
    }


async def _eval_trace_detail(pool: Any, trace_id: str) -> dict[str, Any] | None:
    trace_rows = await _pg_rows(
        pool,
        "SELECT * FROM eval_traces WHERE trace_id = $1",
        trace_id,
    )
    if not trace_rows:
        return None

    trace_obj = trace_rows[0]
    for key in ("inputs_json", "tags_json", "meta_json"):
        trace_obj[key] = _json_load_maybe(trace_obj.get(key))

    event_rows = await _pg_rows(
        pool,
        "SELECT * FROM eval_events WHERE trace_id = $1 ORDER BY seq ASC",
        trace_id,
    )
    for event in event_rows:
        event["payload_json"] = _json_load_maybe(event.get("payload_json"))
        event["meta_json"] = _json_load_maybe(event.get("meta_json"))

    eval_rows = await _pg_rows(
        pool,
        """
        SELECT r.*,
               ARRAY_AGG(ere.event_key) FILTER (WHERE ere.event_key IS NOT NULL)
                 AS evidence_event_keys
        FROM eval_results r
        LEFT JOIN eval_result_evidence ere ON ere.eval_id = r.eval_id
        WHERE r.trace_id = $1
        GROUP BY r.eval_id
        """,
        trace_id,
    )
    for eval_row in eval_rows:
        eval_row["meta_json"] = _json_load_maybe(eval_row.get("meta_json"))
        eval_row["evidence_json"] = _json_load_maybe(eval_row.get("evidence_json"))

    return {"trace": trace_obj, "events": event_rows, "evals": eval_rows}


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

            detail = await _eval_trace_detail(request.app.state.pool, trace_id)
            if detail:
                ADMIN_TRACE_RESOLVE_SOURCE_TOTAL.labels(source="eval").inc()
                return detail

            ADMIN_TRACE_RESOLVE_SOURCE_TOTAL.labels(source="not_found").inc()
            if checkpoint_error is not None:
                raise checkpoint_error
            raise HTTPException(status_code=404, detail="Trace not found")

        detail = await _eval_trace_detail(request.app.state.pool, trace_id)
        if detail:
            ADMIN_TRACE_RESOLVE_SOURCE_TOTAL.labels(source="eval").inc()
            return detail

        ADMIN_TRACE_RESOLVE_SOURCE_TOTAL.labels(source="not_found").inc()
        raise HTTPException(status_code=404, detail="Trace not found")
    finally:
        ADMIN_TRACE_QUERY_DURATION_SECONDS.labels(endpoint="trace_detail").observe(
            time.perf_counter() - started
        )


@router.get("/users")
async def users(request: Request, limit: int = Query(default=120, ge=1, le=1000)):
    pool = request.app.state.pool
    rows = await _pg_rows(
        pool,
        """
        SELECT
            session_id,
            COUNT(*) AS trace_count,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count,
            SUM(CASE WHEN status = 'error'   THEN 1 ELSE 0 END) AS error_count,
            AVG(COALESCE(latency_ms, 0))                         AS avg_latency_ms,
            MAX(started_at)                                      AS last_active
        FROM eval_traces
        WHERE session_id IS NOT NULL AND started_at IS NOT NULL
        GROUP BY session_id
        ORDER BY trace_count DESC
        LIMIT $1
        """,
        limit,
    )
    return {"items": rows, "count": len(rows), "limit": limit}


@router.get("/guardrails")
async def guardrails(
    request: Request,
    tenant_id: str = Query(default="default", description="Tenant ID to filter RLS policies"),
    decision: str | None = Query(default=None, description="Optional risk decision filter"),
    min_risk: float | None = Query(default=None, ge=0.0, le=1.0),
    session_id: str | None = Query(default=None),
    start: datetime | None = Query(default=None, description="ISO timestamp lower bound"),
    end: datetime | None = Query(default=None, description="ISO timestamp upper bound"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=120, ge=1, le=1000),
):
    endpoint = "guardrails_events"
    status = "success"
    started = time.perf_counter()

    try:
        pool = request.app.state.pool
        fetch_cap = min(max(offset + limit + 1000, 2000), 10000)
        rows = await _load_guardrail_trace_rows(
            pool,
            limit=fetch_cap,
            tenant_id=tenant_id,
            session_id=session_id.strip() if session_id else None,
            start=start,
            end=end,
        )
        events = [evt for row in rows if (evt := _as_guardrail_event(row)) is not None]

        decision_filter = (decision or "").strip().lower()
        if decision_filter and decision_filter != "all":
            events = [
                evt
                for evt in events
                if str(evt.get("risk_decision", "")).lower() == decision_filter
            ]

        if min_risk is not None:
            events = [
                evt for evt in events if _coerce_guardrail_float(evt.get("risk_score")) >= min_risk
            ]

        total = len(events)
        items = events[offset : offset + limit]
        return {
            "items": items,
            "count": len(items),
            "total": total,
            "offset": offset,
            "limit": limit,
        }
    except HTTPException:
        raise
    except Exception as exc:
        status = "error"
        _log_guardrails_query_failure(endpoint=endpoint, tenant_id=tenant_id, exc=exc)
        raise HTTPException(status_code=503, detail="Guardrail analytics unavailable") from exc
    finally:
        ADMIN_GUARDRAILS_QUERY_TOTAL.labels(endpoint=endpoint, status=status).inc()
        ADMIN_GUARDRAILS_QUERY_DURATION_SECONDS.labels(endpoint=endpoint).observe(
            time.perf_counter() - started
        )


@router.get("/guardrails/summary")
async def guardrails_summary(
    request: Request,
    tenant_id: str = Query(default="default"),
):
    endpoint = "guardrails_summary"
    status = "success"
    started = time.perf_counter()
    try:
        pool = request.app.state.pool
        rows = await _load_guardrail_trace_rows(pool, limit=20000, tenant_id=tenant_id)
        events = [evt for row in rows if (evt := _as_guardrail_event(row)) is not None]

        total_events = len(events)
        deny_events = sum(
            1
            for evt in events
            if any(
                token in str(evt.get("risk_decision", "")).lower() for token in ("deny", "block")
            )
        )
        avg_risk_score = (
            sum(_coerce_guardrail_float(evt.get("risk_score")) for evt in events) / total_events
            if total_events
            else 0.0
        )
        return {
            "total_events": total_events,
            "deny_events": deny_events,
            "allow_events": max(0, total_events - deny_events),
            "deny_rate": (deny_events / total_events) if total_events else 0.0,
            "avg_risk_score": avg_risk_score,
        }
    except HTTPException:
        raise
    except Exception as exc:
        status = "error"
        _log_guardrails_query_failure(endpoint=endpoint, tenant_id=tenant_id, exc=exc)
        raise HTTPException(status_code=503, detail="Guardrail analytics unavailable") from exc
    finally:
        ADMIN_GUARDRAILS_QUERY_TOTAL.labels(endpoint=endpoint, status=status).inc()
        ADMIN_GUARDRAILS_QUERY_DURATION_SECONDS.labels(endpoint=endpoint).observe(
            time.perf_counter() - started
        )


@router.get("/guardrails/trends")
async def guardrails_trends(
    request: Request,
    tenant_id: str = Query(default="default"),
    hours: int = Query(default=24, ge=1, le=24 * 14),
):
    endpoint = "guardrails_trends"
    status = "success"
    started = time.perf_counter()
    try:
        pool = request.app.state.pool
        start = datetime.now(timezone.utc) - timedelta(hours=hours)
        rows = await _load_guardrail_trace_rows(
            pool,
            limit=20000,
            tenant_id=tenant_id,
            start=start,
        )
        buckets: dict[str, dict[str, float | int]] = {}
        for row in rows:
            event = _as_guardrail_event(row)
            if not event:
                continue
            event_time = _parse_iso_timestamp(event.get("event_time"))
            if event_time is None:
                continue
            bucket_dt = event_time.astimezone(timezone.utc).replace(
                minute=0,
                second=0,
                microsecond=0,
            )
            bucket_key = bucket_dt.isoformat()
            agg = buckets.setdefault(
                bucket_key,
                {"total_events": 0, "deny_events": 0, "avg_risk_sum": 0.0},
            )
            agg["total_events"] = int(agg["total_events"]) + 1
            decision_text = str(event.get("risk_decision", "")).lower()
            if "deny" in decision_text or "block" in decision_text:
                agg["deny_events"] = int(agg["deny_events"]) + 1
            agg["avg_risk_sum"] = float(agg["avg_risk_sum"]) + _coerce_guardrail_float(
                event.get("risk_score")
            )

        items = []
        for bucket_key, agg in sorted(buckets.items(), key=lambda item: item[0]):
            total_events = int(agg["total_events"])
            avg_risk_score = (float(agg["avg_risk_sum"]) / total_events) if total_events else 0.0
            items.append(
                {
                    "bucket": bucket_key,
                    "total_events": total_events,
                    "deny_events": int(agg["deny_events"]),
                    "avg_risk_score": avg_risk_score,
                }
            )
        return {
            "items": items,
            "hours": hours,
        }
    except HTTPException:
        raise
    except Exception as exc:
        status = "error"
        _log_guardrails_query_failure(endpoint=endpoint, tenant_id=tenant_id, hours=hours, exc=exc)
        raise HTTPException(status_code=503, detail="Guardrail analytics unavailable") from exc
    finally:
        ADMIN_GUARDRAILS_QUERY_TOTAL.labels(endpoint=endpoint, status=status).inc()
        ADMIN_GUARDRAILS_QUERY_DURATION_SECONDS.labels(endpoint=endpoint).observe(
            time.perf_counter() - started
        )


@router.get("/guardrails/queue-health")
async def guardrails_queue_health():
    redis = await get_redis()
    depth = int(await redis.llen(SHADOW_TRACE_QUEUE_KEY))
    dead_letter_depth = int(await redis.llen(SHADOW_TRACE_DLQ_KEY))
    oldest = await redis.lindex(SHADOW_TRACE_QUEUE_KEY, -1)

    oldest_age_seconds: int | None = None
    if oldest:
        try:
            payload = json.loads(oldest)
            enqueued_at_raw = payload.get("enqueued_at")
            if isinstance(enqueued_at_raw, str) and enqueued_at_raw:
                normalized = enqueued_at_raw.replace("Z", "+00:00")
                enqueued_at = datetime.fromisoformat(normalized)
                oldest_age_seconds = max(
                    0, int((datetime.now(timezone.utc) - enqueued_at).total_seconds())
                )
        except Exception:
            oldest_age_seconds = None

    return {
        "queue_key": SHADOW_TRACE_QUEUE_KEY,
        "depth": depth,
        "dead_letter_queue_key": SHADOW_TRACE_DLQ_KEY,
        "dead_letter_depth": dead_letter_depth,
        "oldest_age_seconds": oldest_age_seconds,
    }


@router.get("/guardrails/judge-summary")
async def guardrails_judge_summary(
    request: Request,
    limit_failures: int = Query(default=20, ge=1, le=100),
):
    pool = request.app.state.pool
    aggregate_rows = await _pg_rows(
        pool,
        """
        SELECT
            COUNT(*) AS total_evals,
            AVG(COALESCE(helpfulness, 0))       AS avg_helpfulness,
            AVG(COALESCE(faithfulness, 0))       AS avg_faithfulness,
            AVG(COALESCE(policy_adherence, 0))   AS avg_policy_adherence
        FROM shadow_judge_evals
        """,
    )
    failure_rows = await _pg_rows(
        pool,
        """
        SELECT trace_id, session_id, model, summary,
               helpfulness, faithfulness, policy_adherence, evaluated_at
        FROM shadow_judge_evals
        WHERE policy_adherence < 0.5 OR faithfulness < 0.5 OR helpfulness < 0.5
        ORDER BY evaluated_at DESC
        LIMIT $1
        """,
        limit_failures,
    )

    row = aggregate_rows[0] if aggregate_rows else {}
    return {
        "total_evals": int(row.get("total_evals") or 0),
        "avg_helpfulness": float(row.get("avg_helpfulness") or 0.0),
        "avg_faithfulness": float(row.get("avg_faithfulness") or 0.0),
        "avg_policy_adherence": float(row.get("avg_policy_adherence") or 0.0),
        "recent_failures": failure_rows,
    }
