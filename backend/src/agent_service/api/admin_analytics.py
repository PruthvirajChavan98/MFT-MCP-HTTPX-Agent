from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from starlette.concurrency import run_in_threadpool

from src.agent_service.api.admin_auth import require_admin_key
from src.common.neo4j_mgr import Neo4jManager

router = APIRouter(
    prefix="/agent/admin/analytics",
    tags=["admin-analytics"],
    dependencies=[Depends(require_admin_key)],
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


async def _neo4j_read(query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        return await run_in_threadpool(Neo4jManager.execute_read, query, params)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Neo4j unavailable: {exc}") from exc


@router.get("/overview")
async def overview():
    rows = await _neo4j_read(
        """
        MATCH (t:EvalTrace)
        WITH
          count(t) AS traces,
          sum(CASE WHEN t.status = 'success' THEN 1 ELSE 0 END) AS success_count,
          avg(toFloat(coalesce(t.latency_ms, 0))) AS avg_latency_ms,
          max(t.started_at) AS last_active
        RETURN traces, success_count, avg_latency_ms, last_active
        """,
        {},
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
async def conversations(request: Request, limit: int = Query(default=120, ge=1, le=1000)):
    """List all sessions from the LangGraph Redis Checkpointer.
    
    Uses the public checkpointer.alist() API — no private attributes,
    no Redis key parsing, no fragile patterns.
    """
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

            items.append({
                "session_id": tid,
                "started_at": last_ts,
                "model": model,
                "provider": provider,
                "message_count": len(messages),
                "first_question": first_question,
            })
        except Exception:
            continue

        if len(items) >= limit:
            break

    # Sort by most recent first
    items.sort(key=lambda x: x.get("started_at") or "", reverse=True)

    return {"items": items, "count": len(items), "limit": limit}


@router.get("/session/{session_id}")
async def session_traces(request: Request, session_id: str, limit: int = Query(default=500, ge=1, le=2000)):
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
            role = "user" if msg_type == "human" else ("assistant" if msg_type == "ai" else msg_type)

            created = resp_meta.get("created")
            timestamp = int(created * 1000) if created else 0

            reasoning = (
                add_kwargs.get("reasoning", "") or
                add_kwargs.get("reasoning_content", "") or
                resp_meta.get("reasoning", "")
            )

            seq_id = f"{session_id}~{idx}"

            items.append({
                "id": seq_id,
                "role": role,
                "content": content,
                "reasoning": reasoning,
                "timestamp": timestamp,
                "status": "done",
                "traceId": seq_id,
            })

    items = items[:limit]
    return {"items": items, "count": len(items)}


@router.get("/traces")
async def traces(request: Request, limit: int = Query(default=200, ge=1, le=2000)):
    """Flat list of all AI turns across all sessions — powers the /admin/traces UI.

    Each trace is one AI response within a session, identified by
    {session_id}~N where N is the 1-indexed message position.
    """
    checkpointer = getattr(request.app.state, "checkpointer", None)
    if not checkpointer:
        raise HTTPException(status_code=503, detail="Checkpointer unavailable")

    seen_threads: set[str] = set()
    all_traces: list[dict] = []

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

            current_question = ""
            for idx, msg in enumerate(messages, start=1):
                msg_type = getattr(msg, "type", "")
                if msg_type == "human":
                    current_question = getattr(msg, "content", "")
                elif msg_type == "ai":
                    resp_meta = getattr(msg, "response_metadata", {})
                    add_kwargs = getattr(msg, "additional_kwargs", {})
                    model = resp_meta.get("model_name", "unknown")
                    provider = resp_meta.get("model_provider", "unknown")
                    created = resp_meta.get("created")
                    started_at = (
                        datetime.fromtimestamp(created, tz=timezone.utc).isoformat()
                        if created else checkpoint.get("ts")
                    )
                    reasoning = (
                        add_kwargs.get("reasoning", "") or
                        add_kwargs.get("reasoning_content", "") or
                        resp_meta.get("reasoning", "")
                    )

                    seq_id = f"{tid}~{idx}"
                    all_traces.append({
                        "trace_id": seq_id,
                        "session_id": tid,
                        "model": model,
                        "provider": provider,
                        "started_at": started_at,
                        "status": "success",
                        "inputs_json": {"question": current_question},
                        "final_output": getattr(msg, "content", ""),
                        "reasoning": reasoning,
                    })
                    current_question = ""
        except Exception:
            continue

        if len(all_traces) >= limit:
            break

    # Sort by most recent first
    all_traces.sort(key=lambda x: x.get("started_at") or "", reverse=True)
    all_traces = all_traces[:limit]

    return {"items": all_traces, "count": len(all_traces)}


@router.get("/trace/{trace_id:path}")
async def trace_detail(request: Request, trace_id: str):
    """Resolve a {session_id}~N trace ID from the Checkpointer.

    Returns the same TraceDetail shape the frontend inspector expects:
    { trace: {...}, events: [...], evals: [] }
    """
    checkpointer = getattr(request.app.state, "checkpointer", None)
    if not checkpointer:
        raise HTTPException(status_code=503, detail="Checkpointer unavailable")

    # Parse {session_id}~N
    if "~" not in trace_id:
        raise HTTPException(status_code=400, detail=f"Invalid trace_id format: expected '{{session_id}}~N', got '{trace_id}'")

    session_id, idx_str = trace_id.rsplit("~", 1)
    try:
        target_idx = int(idx_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid index in trace_id: '{idx_str}'")

    config = {"configurable": {"thread_id": session_id}}
    ckp = await checkpointer.aget_tuple(config)
    if not ckp or not ckp.checkpoint:
        raise HTTPException(status_code=404, detail="Session not found")

    state = ckp.checkpoint.get("channel_values", {})
    messages = state.get("messages", [])

    if target_idx < 1 or target_idx > len(messages):
        raise HTTPException(status_code=404, detail=f"Message #{target_idx} not found in session '{session_id}' (has {len(messages)} messages)")

    msg = messages[target_idx - 1]
    msg_type = getattr(msg, "type", "")
    content = getattr(msg, "content", "")
    add_kwargs = getattr(msg, "additional_kwargs", {})
    resp_meta = getattr(msg, "response_metadata", {})
    model = resp_meta.get("model_name", "unknown")

    # Find the preceding human message as input
    question = ""
    for i in range(target_idx - 2, -1, -1):
        prev = messages[i]
        if getattr(prev, "type", "") == "human":
            question = getattr(prev, "content", "")
            break

    reasoning = (
        add_kwargs.get("reasoning", "") or
        add_kwargs.get("reasoning_content", "") or
        resp_meta.get("reasoning", "")
    )

    # Build events for the trace tree (reasoning block + output block)
    events = []
    if reasoning:
        events.append({
            "event_type": "reasoning",
            "name": "reasoning",
            "text": reasoning,
        })
    if content:
        events.append({
            "event_type": "token",
            "name": "token",
            "text": content,
        })

    created = resp_meta.get("created")
    started_at = (
        datetime.fromtimestamp(created, tz=timezone.utc).isoformat()
        if created else None
    )

    usage = resp_meta.get("token_usage") or {}

    return {
        "trace": {
            "trace_id": trace_id,
            "session_id": session_id,
            "name": f"Agent Turn #{target_idx}",
            "model": model,
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


@router.get("/users")
async def users(limit: int = Query(default=120, ge=1, le=1000)):
    rows = await _neo4j_read(
        """
        MATCH (t:EvalTrace)
        WHERE t.session_id IS NOT NULL
        WITH
          t.session_id AS session_id,
          count(t) AS trace_count,
          sum(CASE WHEN t.status = 'success' THEN 1 ELSE 0 END) AS success_count,
          sum(CASE WHEN t.status = 'error' THEN 1 ELSE 0 END) AS error_count,
          avg(toFloat(coalesce(t.latency_ms, 0))) AS avg_latency_ms,
          max(t.started_at) AS last_active
        RETURN session_id, trace_count, success_count, error_count, avg_latency_ms, last_active
        ORDER BY trace_count DESC
        LIMIT $limit
        """,
        {"limit": limit},
    )

    return {"items": rows, "count": len(rows), "limit": limit}


@router.get("/guardrails")
async def guardrails(request: Request, limit: int = Query(default=120, ge=1, le=1000)):
    pool_manager = getattr(request.app.state, "postgres_pool", None)
    pool = getattr(pool_manager, "pool", None) if pool_manager else None

    if pool is None:
        raise HTTPException(
            status_code=503,
            detail="PostgreSQL pool unavailable for guardrail analytics",
        )

    rows = await pool.fetch(
        """
        SELECT
          event_time,
          session_id,
          risk_score,
          risk_decision,
          request_path,
          risk_reasons
        FROM security.session_ip_events
        ORDER BY event_time DESC
        LIMIT $1
        """,
        limit,
    )

    items = []
    for row in rows:
        reasons = row["risk_reasons"] if isinstance(row["risk_reasons"], list) else []
        items.append(
            {
                "event_time": row["event_time"].isoformat() if row["event_time"] else None,
                "session_id": row["session_id"],
                "risk_score": float(row["risk_score"]),
                "risk_decision": row["risk_decision"],
                "request_path": row["request_path"],
                "reasons": [str(reason) for reason in reasons],
            }
        )

    return {"items": items, "count": len(items), "limit": limit}
