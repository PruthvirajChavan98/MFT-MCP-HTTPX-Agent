"""
Rate Limiter Manager - Production-Grade Factory and Registry.

Provides:
- Centralized rate limiter creation and management
- Integration with existing Redis infrastructure
- Per-endpoint, per-user, and per-IP rate limiting
- Easy-to-use FastAPI dependencies
- Metrics aggregation

Based on best practices from:
- https://upstash.com/docs/redis/tutorials/python_rate_limiting
- https://medium.com/@2nick2patel2/fastapi-rate-limiting-with-redis-fair-use-apis-without-user-rage-dbf8ed370c72
"""

import logging
from typing import Dict, Optional

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis as AsyncRedis

from src.agent_service.core.config import (
    RATE_LIMIT_ADMIN_TIER_RPS,
    RATE_LIMIT_AGENT_QUERY_RPS,
    RATE_LIMIT_AGENT_STREAM_RPS,
    RATE_LIMIT_ALGORITHM,
    RATE_LIMIT_DEFAULT_RPS,
    RATE_LIMIT_ENABLE_METRICS,
    RATE_LIMIT_ENABLED,
    RATE_LIMIT_FAILURE_MODE,
    RATE_LIMIT_FOLLOW_UP_RPS,
    RATE_LIMIT_FREE_TIER_RPS,
    RATE_LIMIT_HEALTH_RPS,
    RATE_LIMIT_KEY_PREFIX,
    RATE_LIMIT_MAX_BURST,
    RATE_LIMIT_MODELS_RPS,
    RATE_LIMIT_PER_IP_ENABLED,
    RATE_LIMIT_PER_IP_RPS,
    RATE_LIMIT_PREMIUM_TIER_RPS,
    RATE_LIMIT_REDIS_TIMEOUT,
    RATE_LIMIT_SESSION_RPS,
)
from src.agent_service.core.rate_limiter import (
    FailureMode,
    RateLimitAlgorithm,
    RedisRateLimiter,
)
from src.agent_service.core.session_utils import get_redis

log = logging.getLogger(__name__)


class RateLimiterManager:
    """
    Centralized rate limiter management.

    Features:
    - Lazy initialization of rate limiters
    - Reuses existing Redis connection pool
    - Per-endpoint and per-tier rate limiting
    - Metrics aggregation
    - Easy integration with FastAPI
    """

    def __init__(self):
        """Initialize manager (rate limiters are created lazily)."""
        self._limiters: Dict[str, RedisRateLimiter] = {}
        self._redis: Optional[AsyncRedis] = None

    async def _get_redis(self) -> AsyncRedis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = await get_redis()
        return self._redis

    async def _get_limiter(
        self,
        name: str,
        requests_per_second: float,
        max_burst: Optional[int] = None,
    ) -> RedisRateLimiter:
        """
        Get or create a rate limiter for a specific purpose.

        Args:
            name: Limiter identifier (e.g., "endpoint:agent_stream")
            requests_per_second: Rate limit
            max_burst: Maximum burst size (for token bucket)

        Returns:
            Configured RedisRateLimiter instance
        """
        if name not in self._limiters:
            redis = await self._get_redis()

            # Parse algorithm from config
            algorithm = (
                RateLimitAlgorithm.TOKEN_BUCKET
                if RATE_LIMIT_ALGORITHM == "token_bucket"
                else RateLimitAlgorithm.SLIDING_WINDOW
            )

            # Parse failure mode from config
            failure_mode = (
                FailureMode.FAIL_CLOSED
                if RATE_LIMIT_FAILURE_MODE == "fail_closed"
                else FailureMode.FAIL_OPEN
            )

            self._limiters[name] = RedisRateLimiter(
                redis_client=redis,
                requests_per_second=requests_per_second,
                algorithm=algorithm,
                max_burst=max_burst or RATE_LIMIT_MAX_BURST,
                key_prefix=f"{RATE_LIMIT_KEY_PREFIX}:{name}",
                failure_mode=failure_mode,
                redis_timeout=RATE_LIMIT_REDIS_TIMEOUT,
                enable_metrics=RATE_LIMIT_ENABLE_METRICS,
            )

            log.info(
                f"Created rate limiter '{name}': {requests_per_second} req/s, "
                f"algorithm={algorithm.value}, mode={failure_mode.value}"
            )

        return self._limiters[name]

    # =========================================================================
    # Endpoint-Specific Rate Limiters
    # =========================================================================

    async def get_agent_stream_limiter(self) -> RedisRateLimiter:
        """Rate limiter for /agent/stream endpoint."""
        return await self._get_limiter("endpoint:agent_stream", RATE_LIMIT_AGENT_STREAM_RPS)

    async def get_agent_query_limiter(self) -> RedisRateLimiter:
        """Rate limiter for /agent/query endpoint."""
        return await self._get_limiter("endpoint:agent_query", RATE_LIMIT_AGENT_QUERY_RPS)

    async def get_follow_up_limiter(self) -> RedisRateLimiter:
        """Rate limiter for /follow-up endpoint."""
        return await self._get_limiter("endpoint:follow_up", RATE_LIMIT_FOLLOW_UP_RPS)

    async def get_session_limiter(self) -> RedisRateLimiter:
        """Rate limiter for session management endpoints."""
        return await self._get_limiter("endpoint:session", RATE_LIMIT_SESSION_RPS)

    async def get_models_limiter(self) -> RedisRateLimiter:
        """Rate limiter for /models endpoint."""
        return await self._get_limiter("endpoint:models", RATE_LIMIT_MODELS_RPS)

    async def get_health_limiter(self) -> RedisRateLimiter:
        """Rate limiter for /health endpoint."""
        return await self._get_limiter("endpoint:health", RATE_LIMIT_HEALTH_RPS)

    async def get_default_limiter(self) -> RedisRateLimiter:
        """Default rate limiter for unspecified endpoints."""
        return await self._get_limiter("endpoint:default", RATE_LIMIT_DEFAULT_RPS)

    # =========================================================================
    # Tier-Based Rate Limiters (Per-User)
    # =========================================================================

    async def get_free_tier_limiter(self) -> RedisRateLimiter:
        """Rate limiter for free tier users."""
        return await self._get_limiter("tier:free", RATE_LIMIT_FREE_TIER_RPS)

    async def get_premium_tier_limiter(self) -> RedisRateLimiter:
        """Rate limiter for premium tier users."""
        return await self._get_limiter("tier:premium", RATE_LIMIT_PREMIUM_TIER_RPS)

    async def get_admin_tier_limiter(self) -> RedisRateLimiter:
        """Rate limiter for admin tier users."""
        return await self._get_limiter("tier:admin", RATE_LIMIT_ADMIN_TIER_RPS)

    # =========================================================================
    # IP-Based Rate Limiting
    # =========================================================================

    async def get_ip_limiter(self) -> RedisRateLimiter:
        """Rate limiter for per-IP protection."""
        return await self._get_limiter("ip:global", RATE_LIMIT_PER_IP_RPS)

    # =========================================================================
    # Metrics and Monitoring
    # =========================================================================

    async def get_all_metrics(self) -> Dict[str, Dict]:
        """
        Get metrics from all active rate limiters.

        Returns:
            Dictionary mapping limiter names to their metrics
        """
        metrics = {}
        for name, limiter in self._limiters.items():
            metrics[name] = await limiter.get_metrics()
        return metrics

    async def reset_all_metrics(self):
        """Reset metrics for all rate limiters."""
        for limiter in self._limiters.values():
            limiter._metrics = {
                "requests_allowed": 0,
                "requests_denied": 0,
                "redis_errors": 0,
            }
        log.info("Reset all rate limiter metrics")


# ============================================================================
# Global Singleton
# ============================================================================

_rate_limiter_manager: Optional[RateLimiterManager] = None


def get_rate_limiter_manager() -> RateLimiterManager:
    """Get or create global rate limiter manager instance."""
    global _rate_limiter_manager
    if _rate_limiter_manager is None:
        _rate_limiter_manager = RateLimiterManager()
    return _rate_limiter_manager


# ============================================================================
# FastAPI Dependencies and Helpers
# ============================================================================


def get_client_identifier(request: Request) -> str:
    """
    Extract client identifier from request.

    Priority:
    1. Session ID from headers (X-Session-ID)
    2. User ID from headers (X-User-ID)
    3. API Key from headers (X-API-Key)
    4. Client IP address

    Args:
        request: FastAPI Request object

    Returns:
        Client identifier string
    """
    # Try session ID first
    session_id = request.headers.get("X-Session-ID") or request.headers.get("session-id")
    if session_id:
        return f"session:{session_id}"

    # Try user ID
    user_id = request.headers.get("X-User-ID") or request.headers.get("user-id")
    if user_id:
        return f"user:{user_id}"

    # Try API key
    api_key = request.headers.get("X-API-Key") or request.headers.get("api-key")
    if api_key:
        # Hash API key for privacy
        import hashlib

        key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        return f"api:{key_hash}"

    # Fallback to IP
    client_ip = request.client.host if request.client else "unknown"
    return f"ip:{client_ip}"


async def enforce_rate_limit(
    request: Request,
    limiter: RedisRateLimiter,
    identifier: Optional[str] = None,
) -> None:
    """
    Enforce rate limit and raise HTTPException if exceeded.

    Args:
        request: FastAPI Request object
        limiter: RedisRateLimiter instance
        identifier: Optional identifier (auto-detected if None)

    Raises:
        HTTPException: 429 Too Many Requests if rate limit exceeded
    """
    if not RATE_LIMIT_ENABLED:
        return  # Rate limiting globally disabled

    if identifier is None:
        identifier = get_client_identifier(request)

    allowed = await limiter.aacquire(blocking=False, identifier=identifier)

    if not allowed:
        # Get status for detailed error message
        status_info = await limiter.get_status(identifier)

        error_detail = {
            "error": "rate_limit_exceeded",
            "message": "Too many requests. Please slow down.",
            "identifier": identifier,
            "retry_after": status_info.get("retry_after") if status_info else None,
            "reset_at": status_info.get("reset_at") if status_info else None,
        }

        log.warning(f"Rate limit exceeded for {identifier}: {error_detail}")

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_detail,
            headers={
                "Retry-After": str(status_info.get("retry_after", 60) if status_info else 60),
                "X-RateLimit-Limit": str(
                    status_info.get("limit", "unknown") if status_info else "unknown"
                ),
                "X-RateLimit-Remaining": str(status_info.get("remaining", 0) if status_info else 0),
                "X-RateLimit-Reset": str(status_info.get("reset_at", 0) if status_info else 0),
            },
        )


async def enforce_ip_rate_limit(request: Request) -> None:
    """
    Enforce IP-based rate limiting.

    Use this as a first line of defense against DDoS.

    Args:
        request: FastAPI Request object

    Raises:
        HTTPException: 429 Too Many Requests if rate limit exceeded
    """
    if not RATE_LIMIT_ENABLED or not RATE_LIMIT_PER_IP_ENABLED:
        return

    manager = get_rate_limiter_manager()
    ip_limiter = await manager.get_ip_limiter()

    client_ip = request.client.host if request.client else "unknown"
    identifier = f"ip:{client_ip}"

    await enforce_rate_limit(request, ip_limiter, identifier)
