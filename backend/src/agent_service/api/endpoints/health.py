"""Health checks and monitoring endpoints."""

from __future__ import annotations

import time

from fastapi import APIRouter, Request, Response

from src.agent_service.core.config import PROMETHEUS_METRICS_ENABLED
from src.agent_service.core.session_utils import get_redis
from src.agent_service.security.metrics import export_prometheus_metrics

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Backward-compatible health endpoint."""
    return {
        "status": "healthy",
        "service": "agent",
        "version": "2.0.0",
        "timestamp": int(time.time()),
    }


@router.get("/health/live")
async def liveness_check():
    """Liveness probe: process is up."""
    return {"status": "alive", "service": "agent"}


@router.get("/health/ready")
async def readiness_check(request: Request):
    """Readiness probe: dependencies are reachable."""
    checks: dict[str, object] = {}
    healthy = True

    try:
        redis = await get_redis()
        pong = await redis.ping()
        checks["redis"] = {"ok": bool(pong)}
    except Exception as exc:
        healthy = False
        checks["redis"] = {"ok": False, "error": str(exc)}

    postgres_pool = getattr(request.app.state, "postgres_pool", None)
    if postgres_pool:
        postgres_ok = await postgres_pool.ping()  # type: ignore[misc]
        checks["postgres"] = {
            "ok": postgres_ok,
            "pool_min": getattr(postgres_pool, "min_size", None),
            "pool_max": getattr(postgres_pool, "max_size", None),
        }
        if not postgres_ok:
            healthy = False

    runtime = getattr(request.app.state, "security_runtime", None)
    if runtime:
        staleness = runtime.tor_blocker.staleness_seconds()
        stale = runtime.tor_blocker.is_stale()
        checks["tor_exit_list"] = {
            "ok": not stale,
            "stale": stale,
            "stale_seconds": round(staleness, 2),
        }
        if stale:
            healthy = False

    return {
        "status": "ready" if healthy else "degraded",
        "healthy": healthy,
        "checks": checks,
        "timestamp": int(time.time()),
    }


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus scrape endpoint."""
    if not PROMETHEUS_METRICS_ENABLED:
        return Response(status_code=404, content=b"metrics disabled")

    body, content_type = export_prometheus_metrics()
    return Response(content=body, media_type=content_type)
