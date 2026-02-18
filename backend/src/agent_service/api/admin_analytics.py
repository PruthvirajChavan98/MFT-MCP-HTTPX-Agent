from __future__ import annotations

import json
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
async def conversations(limit: int = Query(default=120, ge=1, le=1000)):
    rows = await _neo4j_read(
        """
        MATCH (t:EvalTrace)
        WHERE t.started_at IS NOT NULL
        RETURN
          t.trace_id AS trace_id,
          t.session_id AS session_id,
          t.provider AS provider,
          t.model AS model,
          t.endpoint AS endpoint,
          t.started_at AS started_at,
          t.latency_ms AS latency_ms,
          t.status AS status,
          t.error AS error,
          t.inputs_json AS inputs_json,
          t.final_output AS final_output
        ORDER BY t.started_at DESC
        LIMIT $limit
        """,
        {"limit": limit},
    )

    items = []
    for row in rows:
        row["inputs_json"] = _json_load_maybe(row.get("inputs_json"))
        items.append(row)

    return {"items": items, "count": len(items), "limit": limit}


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
