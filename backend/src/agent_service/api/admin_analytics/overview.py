"""Overview analytics endpoints: dashboard overview and users summary."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from src.agent_service.api.admin_auth import require_admin_key

from .utils import _pg_rows

router = APIRouter(
    prefix="/agent/admin/analytics",
    tags=["admin-analytics"],
    dependencies=[Depends(require_admin_key)],
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
