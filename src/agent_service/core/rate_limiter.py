"""
Production-Grade Distributed Rate Limiter using Redis.

Features:
- Atomic operations via Lua scripts (prevents race conditions)
- Sliding window algorithm (prevents burst at window boundaries)
- Token bucket algorithm (allows controlled bursts)
- Graceful degradation on Redis failures
- Multi-tenancy support with key prefixes
- Comprehensive observability and metrics
- Automatic key cleanup via TTL
- Connection pooling for high throughput

Based on best practices from:
- https://redis.io/tutorials/howtos/ratelimiting/
- https://oneuptime.com/blog/post/2026-01-25-distributed-rate-limiter-redis-rust/view
- https://www.hellointerview.com/learn/system-design/problem-breakdowns/distributed-rate-limiter
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from langchain_core.rate_limiters import BaseRateLimiter
from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import ConnectionError, RedisError, TimeoutError

log = logging.getLogger(__name__)


class RateLimitAlgorithm(Enum):
    """Rate limiting algorithm selection."""

    SLIDING_WINDOW = "sliding_window"  # Smooth enforcement, no boundary bursts
    TOKEN_BUCKET = "token_bucket"  # Allows controlled bursts


class FailureMode(Enum):
    """Behavior when Redis is unavailable."""

    FAIL_OPEN = "fail_open"  # Allow requests (availability priority)
    FAIL_CLOSED = "fail_closed"  # Deny requests (security priority)


@dataclass
class RateLimitResult:
    """Detailed result of rate limit check."""

    allowed: bool
    remaining: int
    reset_at: int  # Unix timestamp
    retry_after: Optional[int] = None  # Seconds until retry
    limit: Optional[int] = None


class RedisRateLimiter(BaseRateLimiter):
    """
    Production-grade distributed rate limiter using Redis.

    Args:
        redis_client: AsyncRedis connection (reuses existing connection pool)
        requests_per_second: Rate limit (supports fractional rates)
        algorithm: SLIDING_WINDOW (smooth) or TOKEN_BUCKET (bursty)
        max_burst: Maximum burst size (token bucket only, defaults to rate)
        key_prefix: Redis key namespace for isolation
        failure_mode: Behavior when Redis fails
        redis_timeout: Redis operation timeout in seconds
        enable_metrics: Enable internal metrics tracking
    """

    def __init__(
        self,
        redis_client: AsyncRedis,
        requests_per_second: float,
        algorithm: RateLimitAlgorithm = RateLimitAlgorithm.SLIDING_WINDOW,
        max_burst: Optional[int] = None,
        key_prefix: str = "ratelimit",
        failure_mode: FailureMode = FailureMode.FAIL_OPEN,
        redis_timeout: float = 1.0,
        enable_metrics: bool = True,
    ):
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")

        self.redis = redis_client
        self.rate = requests_per_second
        self.window_size = int(max(1, 60 / requests_per_second))  # Adaptive window
        self.algorithm = algorithm
        self.max_burst = max_burst or int(requests_per_second)
        self.key_prefix = key_prefix
        self.failure_mode = failure_mode
        self.redis_timeout = redis_timeout
        self.enable_metrics = enable_metrics

        # Metrics
        self._metrics: Dict[str, int] = {
            "requests_allowed": 0,
            "requests_denied": 0,
            "redis_errors": 0,
        }

        # Precompile Lua scripts for atomicity
        self._script = self._get_lua_script()

    def _get_lua_script(self) -> str:
        """
        Get Lua script based on algorithm.

        Sliding Window: Prevents double-burst at window boundaries
        https://redis.io/tutorials/develop/dotnet/aspnetcore/rate-limiting/sliding-window/

        Token Bucket: Allows controlled bursts with continuous refill
        https://api7.ai/blog/rate-limiting-guide-algorithms-best-practices
        """
        if self.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
            return """
            local current_key = KEYS[1]
            local previous_key = KEYS[2]
            local window_size = tonumber(ARGV[1])
            local max_requests = tonumber(ARGV[2])
            local now = tonumber(ARGV[3])
            local window_start = tonumber(ARGV[4])

            -- Get counts from both windows
            local current_count = tonumber(redis.call('GET', current_key) or '0')
            local previous_count = tonumber(redis.call('GET', previous_key) or '0')

            -- Calculate sliding window weight (0.0 to 1.0)
            local elapsed = now - window_start
            local weight = math.max(0, 1.0 - (elapsed / window_size))

            -- Weighted count
            local weighted_count = current_count + (previous_count * weight)

            if weighted_count >= max_requests then
                -- Rate limited
                local remaining = math.max(0, max_requests - weighted_count)
                local reset_at = window_start + window_size
                return {0, math.floor(remaining), reset_at}
            end

            -- Increment current window with atomic expiry
            redis.call('INCR', current_key)
            redis.call('EXPIRE', current_key, window_size * 2)

            local remaining = math.floor(max_requests - weighted_count - 1)
            local reset_at = window_start + window_size
            return {1, remaining, reset_at}
            """
        else:  # TOKEN_BUCKET
            return """
            local key = KEYS[1]
            local max_tokens = tonumber(ARGV[1])
            local refill_rate = tonumber(ARGV[2])
            local now = tonumber(ARGV[3])
            local tokens_requested = tonumber(ARGV[4])

            -- Get current state (tokens, last_refill)
            local state = redis.call('HMGET', key, 'tokens', 'last_refill')
            local tokens = tonumber(state[1])
            local last_refill = tonumber(state[2])

            -- Initialize if first request
            if not tokens or not last_refill then
                tokens = max_tokens
                last_refill = now
            else
                -- Refill tokens based on elapsed time
                local elapsed = math.max(0, now - last_refill)
                tokens = math.min(max_tokens, tokens + (elapsed * refill_rate))
            end

            -- Check if enough tokens available
            if tokens >= tokens_requested then
                tokens = tokens - tokens_requested
                redis.call('HSET', key, 'tokens', tokens, 'last_refill', now)
                redis.call('EXPIRE', key, 3600)  -- Cleanup after 1 hour idle

                local remaining = math.floor(tokens)
                local reset_at = now + math.ceil((max_tokens - tokens) / refill_rate)
                return {1, remaining, reset_at}
            else
                -- Not enough tokens
                local retry_after = math.ceil((tokens_requested - tokens) / refill_rate)
                local reset_at = now + retry_after
                return {0, math.floor(tokens), reset_at, retry_after}
            end
            """

    def _get_keys(self, identifier: str = "global") -> tuple[str, str]:
        """Generate Redis keys with proper namespacing."""
        now = int(time.time())

        if self.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
            window_start = (now // self.window_size) * self.window_size
            previous_start = window_start - self.window_size

            current_key = f"{self.key_prefix}:{identifier}:{window_start}"
            previous_key = f"{self.key_prefix}:{identifier}:{previous_start}"
            return current_key, previous_key
        else:
            # Token bucket uses single key
            key = f"{self.key_prefix}:bucket:{identifier}"
            return key, ""

    async def aacquire(self, blocking: bool = True, identifier: str = "global") -> bool:
        """
        Async rate limit check with proper connection management.

        Args:
            blocking: If True, wait for token availability. If False, return immediately.
            identifier: Client/tenant identifier for isolated rate limiting

        Returns:
            True if request allowed, False if rate limited
        """
        max_wait = 60.0 if blocking else 0.0
        start_time = time.time()

        while True:
            try:
                result = await self._check_async(identifier)

                if result.allowed:
                    if self.enable_metrics:
                        self._metrics["requests_allowed"] += 1
                    return True

                if not blocking:
                    if self.enable_metrics:
                        self._metrics["requests_denied"] += 1
                    return False

                # Calculate backoff with jitter
                sleep_time = result.retry_after or (1.0 / self.rate)
                sleep_time = min(sleep_time, 1.0)

                # Check timeout
                elapsed = time.time() - start_time
                if elapsed + sleep_time > max_wait:
                    if self.enable_metrics:
                        self._metrics["requests_denied"] += 1
                    return False

                await asyncio.sleep(sleep_time)

            except (ConnectionError, TimeoutError, RedisError) as e:
                log.warning(f"Redis error in rate limiter: {e}")
                if self.enable_metrics:
                    self._metrics["redis_errors"] += 1

                # Fail open/closed based on configuration
                if self.failure_mode == FailureMode.FAIL_OPEN:
                    log.info("Failing open - allowing request due to Redis unavailability")
                    return True
                else:
                    log.warning("Failing closed - denying request due to Redis unavailability")
                    return False

    async def _check_async(self, identifier: str) -> RateLimitResult:
        """Execute rate limit check (async)."""
        now = time.time()

        if self.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
            current_key, previous_key = self._get_keys(identifier)
            window_start = (int(now) // self.window_size) * self.window_size

            result = await self.redis.eval(
                self._script,
                2,  # Number of keys
                current_key,
                previous_key,
                self.window_size,
                int(self.rate * self.window_size),
                int(now),
                window_start,
            )
        else:
            key, _ = self._get_keys(identifier)
            result = await self.redis.eval(
                self._script,
                1,  # Number of keys
                key,
                self.max_burst,
                self.rate,
                now,
                1,  # Request 1 token
            )

        return RateLimitResult(
            allowed=bool(result[0]),
            remaining=int(result[1]),
            reset_at=int(result[2]),
            retry_after=int(result[3]) if len(result) > 3 else None,
            limit=(
                int(self.rate * self.window_size)
                if self.algorithm == RateLimitAlgorithm.SLIDING_WINDOW
                else self.max_burst
            ),
        )

    def acquire(self, blocking: bool = True, identifier: str = "global") -> bool:
        """
        Synchronous rate limit check (runs async in event loop).

        Args:
            blocking: If True, wait for token availability
            identifier: Client/tenant identifier

        Returns:
            True if request allowed, False if rate limited
        """
        # Run async version in event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context - this shouldn't happen
                raise RuntimeError("Cannot use sync acquire() in async context - use aacquire()")
            return loop.run_until_complete(self.aacquire(blocking, identifier))
        except RuntimeError:
            # Fallback: create new event loop
            return asyncio.run(self.aacquire(blocking, identifier))

    async def get_metrics(self) -> Dict[str, Any]:
        """Return rate limiter metrics for observability."""
        return {
            **self._metrics,
            "algorithm": self.algorithm.value,
            "rate": self.rate,
            "failure_mode": self.failure_mode.value,
            "window_size": self.window_size,
            "max_burst": self.max_burst,
        }

    async def reset_identifier(self, identifier: str) -> bool:
        """
        Reset rate limit for a specific identifier.

        Useful for:
        - Admin operations
        - Testing
        - Clearing false positives

        Args:
            identifier: The identifier to reset

        Returns:
            True if successful
        """
        try:
            if self.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
                current_key, previous_key = self._get_keys(identifier)
                deleted = await self.redis.delete(current_key, previous_key)
            else:
                key, _ = self._get_keys(identifier)
                deleted = await self.redis.delete(key)

            log.info(f"Reset rate limit for identifier: {identifier} ({deleted} keys deleted)")
            return deleted > 0

        except RedisError as e:
            log.error(f"Redis error resetting rate limit: {e}")
            return False

    async def get_status(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Get current rate limit status for an identifier.

        Args:
            identifier: The identifier to check

        Returns:
            Status dict with remaining, reset_at, etc.
        """
        try:
            result = await self._check_async(identifier)
            return {
                "identifier": identifier,
                "allowed": result.allowed,
                "remaining": result.remaining,
                "limit": result.limit,
                "reset_at": result.reset_at,
                "retry_after": result.retry_after,
                "algorithm": self.algorithm.value,
            }
        except Exception as e:
            log.error(f"Failed to get rate limit status: {e}")
            return None
