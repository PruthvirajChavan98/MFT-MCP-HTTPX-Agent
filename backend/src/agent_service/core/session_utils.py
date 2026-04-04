"""
Session Management & Authentication Utilities
Handles session validation, Redis operations, and authentication checks.
"""

import json
import logging
from typing import Any, Dict, Optional

from redis.asyncio import ConnectionPool
from redis.asyncio import Redis as AsyncRedis

from src.agent_service.core.config import (
    REDIS_HEALTH_CHECK_INTERVAL,
    REDIS_MAX_CONNECTIONS,
    REDIS_URL,
)

log = logging.getLogger(__name__)


# Global async Redis client (singleton)
_async_redis_client: Optional[AsyncRedis] = None
_async_redis_pool: Optional[ConnectionPool] = None


async def get_redis() -> AsyncRedis:
    """
    Get or create global async Redis client (singleton pattern).

    Returns:
        AsyncRedis client instance
    """
    global _async_redis_client
    global _async_redis_pool

    if _async_redis_client is None:
        _async_redis_pool = ConnectionPool.from_url(
            REDIS_URL,
            decode_responses=True,
            encoding="utf-8",
            max_connections=REDIS_MAX_CONNECTIONS,
            health_check_interval=REDIS_HEALTH_CHECK_INTERVAL,
        )
        _async_redis_client = AsyncRedis(connection_pool=_async_redis_pool)
        log.info(
            "Initialized async Redis client with connection pool (max_connections=%s)",
            REDIS_MAX_CONNECTIONS,
        )

    return _async_redis_client


async def close_redis() -> None:
    """Close global Redis connection (cleanup on shutdown)."""
    global _async_redis_client
    global _async_redis_pool

    if _async_redis_client:
        await _async_redis_client.aclose()
        _async_redis_client = None

    if _async_redis_pool:
        await _async_redis_pool.disconnect()
        _async_redis_pool = None

    log.info("Closed async Redis client")


class SessionUtils:
    """Centralized session management and authentication utilities."""

    @staticmethod
    def validate_session_id(session_id: object) -> str:
        """Ensures session_id is a valid non-empty string."""
        sid = str(session_id).strip() if session_id is not None else ""
        if not sid or sid.lower() in {"null", "none"}:
            raise ValueError(f"Invalid session_id: {session_id!r}")
        return sid

    @staticmethod
    async def is_user_authenticated(session_id: str) -> bool:
        """Check if user has an active access_token in Redis (async)."""
        try:
            redis = await get_redis()
            data_str = await redis.get(session_id)

            if not data_str:
                return False

            data = json.loads(str(data_str))
            return bool(data.get("access_token"))

        except Exception as e:
            log.warning(f"Auth check failed for session {session_id}: {e}")
            return False

    @staticmethod
    async def get_app_id_for_session(session_id: str) -> Optional[str]:
        """Retrieve app_id associated with a session from Redis (async)."""
        try:
            redis = await get_redis()
            data_str = await redis.get(session_id)

            if data_str:
                data = json.loads(str(data_str))
                return data.get("app_id")
        except Exception as e:
            log.warning(f"Failed to retrieve app_id for session {session_id}: {e}")

        return None

    @staticmethod
    async def get_session_metadata(session_id: str) -> Dict[str, Any]:
        """Retrieve full session metadata from Redis (async)."""
        try:
            redis = await get_redis()
            data_str = await redis.get(session_id)

            if data_str:
                return json.loads(str(data_str))
        except Exception as e:
            log.error(f"Failed to retrieve metadata for session {session_id}: {e}")

        return {}


# Singleton instance
session_utils = SessionUtils()


# Backward compatibility aliases
def valid_session_id(session_id: object) -> str:
    """DEPRECATED: Use session_utils.validate_session_id() instead."""
    return session_utils.validate_session_id(session_id)


async def is_user_authenticated(session_id: str) -> bool:
    """DEPRECATED: Use session_utils.is_user_authenticated() instead."""
    return await session_utils.is_user_authenticated(session_id)
