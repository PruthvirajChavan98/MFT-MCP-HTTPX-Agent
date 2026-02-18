"""
Session Management & Authentication Utilities
Handles session validation, Redis operations, and authentication checks.
"""

import json
import logging
from typing import Any, Dict, Optional

from redis import Redis
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
    def is_user_authenticated(session_id: str) -> bool:
        """Check if user has an active access_token in Redis."""
        try:
            client = Redis.from_url(REDIS_URL, decode_responses=True)
            data_str = client.get(session_id)

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

    @staticmethod
    async def save_session_config(
        session_id: str, config: Dict[str, Any], ttl: int = 30 * 24 * 60 * 60
    ) -> bool:
        """Save session configuration to Redis (BYOK storage)."""
        try:
            redis = await get_redis()
            key = f"session:config:{session_id}"
            await redis.set(key, json.dumps(config), ex=ttl)
            log.info(f"Saved config for session {session_id}")
            return True
        except Exception as e:
            log.error(f"Failed to save session config: {e}")
            return False

    @staticmethod
    async def get_session_config(session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session configuration from Redis."""
        try:
            redis = await get_redis()
            key = f"session:config:{session_id}"
            config_str = await redis.get(key)
            return json.loads(config_str) if config_str else None
        except Exception as e:
            log.error(f"Failed to get session config: {e}")
            return None

    @staticmethod
    async def delete_session(session_id: str) -> bool:
        """Delete session configuration from Redis."""
        try:
            redis = await get_redis()
            key = f"session:config:{session_id}"
            deleted = await redis.delete(key)
            if deleted > 0:
                log.info(f"Deleted session config for {session_id}")
                return True
            return False
        except Exception as e:
            log.error(f"Failed to delete session: {e}")
            return False


# Singleton instance
session_utils = SessionUtils()


# Backward compatibility aliases
def valid_session_id(session_id: object) -> str:
    """DEPRECATED: Use session_utils.validate_session_id() instead."""
    return session_utils.validate_session_id(session_id)


def is_user_authenticated(session_id: str) -> bool:
    """DEPRECATED: Use session_utils.is_user_authenticated() instead."""
    return session_utils.is_user_authenticated(session_id)
