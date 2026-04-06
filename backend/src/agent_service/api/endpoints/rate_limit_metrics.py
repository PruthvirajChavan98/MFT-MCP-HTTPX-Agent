"""
Rate Limiting Metrics and Monitoring Endpoints.

Provides:
- Real-time metrics for all rate limiters
- Health checks for rate limiting infrastructure
- Admin operations (reset limits, view status)
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.agent_service.api.admin_auth import require_admin_key
from src.agent_service.core.config import RATE_LIMIT_ENABLED
from src.agent_service.core.rate_limiter_manager import (
    enforce_rate_limit,
    get_rate_limiter_manager,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/rate-limit", tags=["rate-limiting"])


@router.get("/metrics")
async def get_rate_limit_metrics(http_request: Request) -> Dict[str, Any]:
    """
    Get metrics from all active rate limiters.

    **Returns:**
    - Metrics for each rate limiter (requests_allowed, requests_denied, errors)
    - Algorithm and configuration details
    - Failure mode settings

    **Use cases:**
    - Monitoring dashboards (Grafana, Datadog)
    - Alerting on rate limit errors
    - Capacity planning
    """
    if not RATE_LIMIT_ENABLED:
        return {"enabled": False, "message": "Rate limiting is globally disabled"}

    # Rate limit this endpoint too (prevent metrics scraping abuse)
    manager = get_rate_limiter_manager()
    models_limiter = await manager.get_models_limiter()  # High limit
    await enforce_rate_limit(http_request, models_limiter)

    metrics = await manager.get_all_metrics()

    return {
        "enabled": True,
        "metrics": metrics,
        "timestamp": __import__("time").time(),
    }


@router.get("/status/{identifier}")
async def get_identifier_status(identifier: str, http_request: Request) -> Dict[str, Any]:
    """
    Get current rate limit status for a specific identifier.

    **Args:**
    - identifier: Client identifier (e.g., "session:abc123", "user:user_id", "ip:1.2.3.4")

    **Returns:**
    - Current rate limit status
    - Remaining requests
    - Reset time
    - Whether next request would be allowed

    **Use cases:**
    - Client-side UI (show user their remaining quota)
    - Debugging rate limit issues
    - Support tickets
    """
    if not RATE_LIMIT_ENABLED:
        return {"enabled": False, "message": "Rate limiting is globally disabled"}

    # Rate limit this endpoint
    manager = get_rate_limiter_manager()
    models_limiter = await manager.get_models_limiter()
    await enforce_rate_limit(http_request, models_limiter)

    # Get status from default limiter (most commonly used)
    limiter = await manager.get_default_limiter()
    status_info = await limiter.get_status(identifier)

    if status_info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No rate limit data found for identifier: {identifier}",
        )

    return status_info


@router.post("/reset/{identifier}")
async def reset_identifier_limit(
    identifier: str,
    http_request: Request,
    _admin: None = Depends(require_admin_key),
) -> Dict[str, Any]:
    """
    Reset rate limit for a specific identifier (ADMIN ONLY).

    **Args:**
    - identifier: Client identifier to reset

    **Returns:**
    - Success status

    **Use cases:**
    - Admin operations (unblock false positives)
    - Testing
    - VIP customer support

    **Security:**
    - Protected by admin key authentication via X-Admin-Key header
    - Logs all reset operations for audit trail
    """
    if not RATE_LIMIT_ENABLED:
        return {"enabled": False, "message": "Rate limiting is globally disabled"}

    # Rate limit this endpoint (prevent reset abuse)
    manager = get_rate_limiter_manager()
    session_limiter = await manager.get_session_limiter()
    await enforce_rate_limit(http_request, session_limiter)

    # Reset across all limiters
    reset_count = 0
    for limiter_name in [
        "endpoint:agent_stream",
        "endpoint:agent_query",
        "tier:free",
        "tier:premium",
    ]:
        try:
            limiter = manager._limiters.get(limiter_name)
            if limiter:
                success = await limiter.reset_identifier(identifier)
                if success:
                    reset_count += 1
        except Exception as e:
            log.error("Failed to reset limiter %s: %s", limiter_name, e)

    log.warning("ADMIN: Reset rate limit for identifier: %s (%d limiters)", identifier, reset_count)

    return {
        "success": True,
        "identifier": identifier,
        "limiters_reset": reset_count,
        "message": f"Rate limit reset for {identifier}",
    }


@router.get("/health")
async def rate_limit_health_check() -> Dict[str, Any]:
    """
    Health check for rate limiting infrastructure.

    **Returns:**
    - Enabled status
    - Redis connectivity
    - Active rate limiters count
    - Overall health status

    **Use cases:**
    - Load balancer health checks
    - Infrastructure monitoring
    - Alerting systems
    """
    if not RATE_LIMIT_ENABLED:
        return {
            "status": "disabled",
            "healthy": True,
            "message": "Rate limiting is globally disabled",
        }

    try:
        manager = get_rate_limiter_manager()

        # Quick Redis connectivity check via limiter
        limiter = await manager.get_health_limiter()

        # Try a non-blocking check
        test_result = await limiter.aacquire(blocking=False, identifier="health:check")

        return {
            "status": "enabled",
            "healthy": True,
            "redis_connected": True,
            "active_limiters": len(manager._limiters),
            "test_result": test_result,
        }

    except Exception as e:
        log.error("Rate limit health check failed: %s", e)
        return {
            "status": "enabled",
            "healthy": False,
            "redis_connected": False,
            "error": str(e),
        }


@router.get("/config")
async def get_rate_limit_config(http_request: Request) -> Dict[str, Any]:
    """
    Get current rate limiting configuration.

    **Returns:**
    - Global settings
    - Per-endpoint limits
    - Per-tier limits
    - Algorithm and failure mode

    **Use cases:**
    - Documentation generation
    - Client-side quota display
    - Support debugging
    """
    from src.agent_service.core.config import (
        RATE_LIMIT_ADMIN_TIER_RPS,
        RATE_LIMIT_AGENT_QUERY_RPS,
        RATE_LIMIT_AGENT_STREAM_RPS,
        RATE_LIMIT_ALGORITHM,
        RATE_LIMIT_DEFAULT_RPS,
        RATE_LIMIT_FAILURE_MODE,
        RATE_LIMIT_FOLLOW_UP_RPS,
        RATE_LIMIT_FREE_TIER_RPS,
        RATE_LIMIT_HEALTH_RPS,
        RATE_LIMIT_MAX_BURST,
        RATE_LIMIT_MODELS_RPS,
        RATE_LIMIT_PER_IP_ENABLED,
        RATE_LIMIT_PER_IP_RPS,
        RATE_LIMIT_PREMIUM_TIER_RPS,
        RATE_LIMIT_SESSION_RPS,
    )

    # Rate limit this endpoint
    manager = get_rate_limiter_manager()
    models_limiter = await manager.get_models_limiter()
    await enforce_rate_limit(http_request, models_limiter)

    return {
        "enabled": RATE_LIMIT_ENABLED,
        "algorithm": RATE_LIMIT_ALGORITHM,
        "failure_mode": RATE_LIMIT_FAILURE_MODE,
        "max_burst": RATE_LIMIT_MAX_BURST,
        "per_ip_enabled": RATE_LIMIT_PER_IP_ENABLED,
        "endpoints": {
            "agent_stream": RATE_LIMIT_AGENT_STREAM_RPS,
            "agent_query": RATE_LIMIT_AGENT_QUERY_RPS,
            "follow_up": RATE_LIMIT_FOLLOW_UP_RPS,
            "session": RATE_LIMIT_SESSION_RPS,
            "models": RATE_LIMIT_MODELS_RPS,
            "health": RATE_LIMIT_HEALTH_RPS,
            "default": RATE_LIMIT_DEFAULT_RPS,
        },
        "tiers": {
            "free": RATE_LIMIT_FREE_TIER_RPS,
            "premium": RATE_LIMIT_PREMIUM_TIER_RPS,
            "admin": RATE_LIMIT_ADMIN_TIER_RPS,
        },
        "per_ip": {"enabled": RATE_LIMIT_PER_IP_ENABLED, "limit": RATE_LIMIT_PER_IP_RPS},
    }
