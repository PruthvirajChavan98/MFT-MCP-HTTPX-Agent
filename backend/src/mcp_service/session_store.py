from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Optional

from redis.asyncio import ConnectionPool
from redis.asyncio import Redis as AsyncRedis

from .config import REDIS_URL

# Session IDs are caller-supplied (from the chat widget's localStorage).
# Cap length + charset so an attacker cannot inflate a Redis key to MB
# sizes, or embed Redis-scan glob characters (``*``, ``?``, ``[``) that
# could interfere with future ops tooling. Matches what the chat widget
# actually generates (UUIDv4 hex or token_urlsafe-style strings).
# (security review M4)
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{4,128}$")
_REJECT_LITERALS = {"null", "none", "undefined", "nan", "false", "true"}

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


async def get_redis() -> AsyncRedis:
    """Return (and lazily create) the module-level async Redis client.

    Uses the REDIS_URL from config. A single connection pool is shared
    process-wide — no per-caller URI overrides to prevent pool contamination.
    """
    global _pool, _client

    if _client is not None:
        return _client

    async with _lock:
        if _client is not None:
            return _client

        _pool = ConnectionPool.from_url(
            REDIS_URL,
            decode_responses=True,
            encoding="utf-8",
            max_connections=20,
            health_check_interval=30,
        )
        _client = AsyncRedis(connection_pool=_pool)
        await _client.ping()  # type: ignore[misc]
        log.info("Connected to Redis: %s", _redact_uri(REDIS_URL))

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
    """Validate and return a non-empty session ID string.

    Enforces length + charset bounds so caller-supplied IDs cannot carry
    Redis glob characters or inflate to megabyte-sized keys. Raises
    ``ValueError`` on anything outside the allow-list.
    """
    sid = str(session_id).strip() if session_id is not None else ""
    if not sid or sid.lower() in _REJECT_LITERALS:
        raise ValueError(f"Invalid session_id: {session_id!r}")
    if not _SESSION_ID_RE.match(sid):
        raise ValueError(f"Invalid session_id: must be 4-128 chars of [A-Za-z0-9_-], got {sid!r}")
    return sid


# ---------------------------------------------------------------------------
# Session store — thin async wrapper over the module-level Redis client
# ---------------------------------------------------------------------------
class RedisSessionStore:
    """Async Redis session store used by MCP tool implementations."""

    async def _redis(self) -> AsyncRedis:
        return await get_redis()

    @staticmethod
    def _valid_session_id(session_id: object) -> Optional[str]:
        """Non-raising variant of :func:`valid_session_id`; returns
        ``None`` instead of raising so instance methods can treat
        malformed IDs as no-ops. Applies the same length + charset rules.
        """
        if session_id is None:
            return None
        sid = str(session_id).strip()
        if not sid or sid.lower() in _REJECT_LITERALS:
            return None
        if not _SESSION_ID_RE.match(sid):
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

    # Lua-scripted atomic merge — decode JSON, apply top-level key updates,
    # re-encode, write. Runs inside a single Redis script execution so two
    # concurrent updates for the same session_id cannot clobber each other's
    # fields the way a non-atomic ``GET → merge → SET`` sequence did.
    # (security review H3)
    _UPDATE_LUA = """
local cur = redis.call('GET', KEYS[1])
local doc
if cur then
  local ok, parsed = pcall(cjson.decode, cur)
  if ok and type(parsed) == 'table' then
    doc = parsed
  else
    doc = {}
  end
else
  doc = {}
end
local patch = cjson.decode(ARGV[1])
if type(patch) == 'table' then
  for k, v in pairs(patch) do
    doc[k] = v
  end
end
local encoded = cjson.encode(doc)
redis.call('SET', KEYS[1], encoded)
return encoded
"""

    async def update(self, session_id: str, updates: dict) -> None:
        sid = self._valid_session_id(session_id)
        if not sid:
            return
        r = await self._redis()
        await r.eval(  # type: ignore[misc]
            self._UPDATE_LUA,
            1,
            sid,
            json.dumps(updates, ensure_ascii=False),
        )
        log.info("[Redis] UPDATE %s | Keys: %s", sid, list(updates.keys()))

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
