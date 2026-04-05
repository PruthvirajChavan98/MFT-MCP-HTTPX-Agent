"""Overview analytics endpoints: dashboard overview and users summary."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from src.agent_service.api.admin_auth import require_admin_key

from .repo import analytics_repo

router = APIRouter(
    prefix="/agent/admin/analytics",
    tags=["admin-analytics"],
    dependencies=[Depends(require_admin_key)],
)


@router.get("/overview")
async def overview(request: Request):
    pool = request.app.state.pool
    rows = await analytics_repo.fetch_overview_stats(pool)
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
    rows = await analytics_repo.fetch_users(pool, limit=limit)
    return {"items": rows, "count": len(rows), "limit": limit}
