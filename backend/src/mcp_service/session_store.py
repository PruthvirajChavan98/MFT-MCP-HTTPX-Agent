from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from redis.asyncio import ConnectionPool
from redis.asyncio import Redis as AsyncRedis

from .config import REDIS_URL

log = logging.getLogger(name="redis_session_store")

# ---------------------------------------------------------------------------
# Module-level async Redis singleton (lazy initialisation)
# ---------------------------------------------------------------------------
_pool: Optional[ConnectionPool] = None
_client: Optional[AsyncRedis] = None
_lock = asyncio.Lock()


def _redact_uri(uri: str) -> str:
    try:
        if "://" in uri and "@" in uri:
            scheme, rest = uri.split("://", 1)
            creds, hostpart = rest.split("@", 1)
            if ":" in creds:
                user = creds.split(":", 1)[0]
                return f"{scheme}://{user}:***@{hostpart}"
    except Exception:
        log.debug("URI redaction failed, returning raw URI")
    return uri


async def get_redis(redis_uri: Optional[str] = None) -> AsyncRedis:
    """Return (and lazily create) the module-level async Redis client."""
    global _pool, _client

    if _client is not None:
        return _client

    async with _lock:
        if _client is not None:
            return _client

        uri = redis_uri or REDIS_URL
        _pool = ConnectionPool.from_url(
            uri,
            decode_responses=True,
            encoding="utf-8",
            max_connections=20,
            health_check_interval=30,
        )
        _client = AsyncRedis(connection_pool=_pool)
        await _client.ping()
        log.info("Connected to Redis: %s", _redact_uri(uri))

    return _client


async def close_redis() -> None:
    """Shutdown the module-level async Redis connection pool."""
    global _pool, _client

    async with _lock:
        if _client is not None:
            await _client.aclose()
            _client = None
        if _pool is not None:
            await _pool.disconnect()
            _pool = None
        log.info("Closed async Redis client")


# ---------------------------------------------------------------------------
# Strict session ID validator (raises on invalid — used by API wrappers)
# ---------------------------------------------------------------------------
def valid_session_id(session_id: object) -> str:
    """Validate and return a non-empty session ID string. Raises ValueError if invalid."""
    sid = str(session_id).strip() if session_id is not None else ""
    if not sid or sid.lower() in {"null", "none"}:
        raise ValueError(f"Invalid session_id: {session_id!r}")
    return sid


# ---------------------------------------------------------------------------
# Session store — thin async wrapper over the module-level Redis client
# ---------------------------------------------------------------------------
class RedisSessionStore:
    """Async Redis session store used by MCP tool implementations."""

    def __init__(self, redis_uri: Optional[str] = None) -> None:
        self._redis_uri = redis_uri

    async def _redis(self) -> AsyncRedis:
        return await get_redis(self._redis_uri)

    @staticmethod
    def _valid_session_id(session_id: object) -> Optional[str]:
        if session_id is None:
            return None
        sid = str(session_id).strip()
        if not sid or sid.lower() in {"null", "none"}:
            return None
        return sid

    async def set(self, session_id: str, data: dict) -> None:
        sid = self._valid_session_id(session_id)
        if not sid:
            return
        r = await self._redis()
        await r.set(sid, json.dumps(data, ensure_ascii=False))
        log.info("[Redis] SET %s | Keys: %s", sid, list(data.keys()))

    async def get(self, session_id: str) -> Optional[dict]:
        sid = self._valid_session_id(session_id)
        if not sid:
            return None
        r = await self._redis()
        data: Optional[str] = await r.get(sid)  # type: ignore[assignment]
        if not data:
            log.warning("[Redis] MISS %s", sid)
            return None
        log.info("[Redis] HIT %s", sid)
        return json.loads(data)

    async def update(self, session_id: str, updates: dict) -> None:
        sid = self._valid_session_id(session_id)
        if not sid:
            return
        current = await self.get(sid) or {}
        current.update(updates)
        await self.set(sid, current)

    async def delete(self, session_id: str) -> None:
        sid = self._valid_session_id(session_id)
        if not sid:
            return
        r = await self._redis()
        await r.delete(sid)
        log.info("[Redis] DEL %s", sid)

    async def set_raw(self, key: str, value: Any, *, ex: int) -> None:
        """Set an arbitrary key with TTL — used for download tokens."""
        r = await self._redis()
        await r.set(key, value, ex=ex)
