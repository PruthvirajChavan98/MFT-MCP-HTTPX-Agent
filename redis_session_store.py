import json
import os
from typing import Optional, cast, Iterable

import redis
from Loggers.StdOutLogger import StdoutLogger

log = StdoutLogger(name="redis_session_store")

# ✅ Backward-compat constant (older modules import this)
DEFAULT_REDIS_URI = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

def _in_docker() -> bool:
    return os.path.exists("/.dockerenv")

def _redact_uri(uri: str) -> str:
    try:
        if "://" in uri and "@" in uri:
            scheme, rest = uri.split("://", 1)
            creds, hostpart = rest.split("@", 1)
            if ":" in creds:
                user = creds.split(":", 1)[0]
                return f"{scheme}://{user}:***@{hostpart}"
    except Exception:
        pass
    return uri

def _candidate_uris() -> Iterable[str]:
    env_uri = (os.getenv("REDIS_URL") or "").strip()
    if env_uri:
        yield env_uri

    # ✅ include default for compatibility
    if DEFAULT_REDIS_URI:
        yield DEFAULT_REDIS_URI

    if _in_docker():
        yield "redis://crm_redis:6379/0"
        yield "redis://redis:6379/0"
        yield "redis://host.docker.internal:6379/0"
    else:
        yield "redis://127.0.0.1:6379/0"
        yield "redis://localhost:6379/0"

class RedisSessionStore:
    def __init__(self, redis_uri: Optional[str] = None):
        self.redis_uri: Optional[str] = None
        self.client: Optional[redis.Redis] = None

        uris = []
        if redis_uri and str(redis_uri).strip():
            uris.append(str(redis_uri).strip())
        uris.extend(list(_candidate_uris()))

        last_err: Optional[Exception] = None
        for uri in uris:
            try:
                c = redis.from_url(uri, decode_responses=True)
                c.ping()
                self.client = c
                self.redis_uri = uri
                log.info(f"✅ Connected to Redis: {_redact_uri(uri)}")
                break
            except Exception as e:
                last_err = e
                log.warning(f"⚠️ Redis connect failed: {_redact_uri(uri)} | {e}")

        if self.client is None:
            raise RuntimeError(f"❌ Could not connect to any Redis. Last error: {last_err}")

    def _valid_session_id(self, session_id: object) -> Optional[str]:
        if session_id is None:
            return None
        sid = str(session_id).strip()
        if not sid or sid.lower() in {"null", "none"}:
            return None
        return sid

    def set(self, session_id: str, data: dict):
        sid = self._valid_session_id(session_id)
        if not sid:
            log.error(f"Refusing to write invalid session_id: {session_id!r}")
            return
        assert self.client is not None
        self.client.set(sid, json.dumps(data, ensure_ascii=False))
        log.info(f"[Redis] SET {sid} | Keys: {list(data.keys())}")

    def get(self, session_id: str) -> Optional[dict]:
        sid = self._valid_session_id(session_id)
        if not sid:
            log.error(f"Refusing to read invalid session_id: {session_id!r}")
            return None
        assert self.client is not None
        data = cast(Optional[str], self.client.get(sid))
        if not data:
            log.warning(f"[Redis] MISS {sid}")
            return None
        log.info(f"[Redis] HIT {sid}")
        return json.loads(data)

    def update(self, session_id: str, updates: dict):
        sid = self._valid_session_id(session_id)
        if not sid:
            log.error(f"Refusing to update invalid session_id: {session_id!r}")
            return
        current = self.get(sid) or {}
        current.update(updates)
        self.set(sid, current)

    def delete(self, session_id: str):
        sid = self._valid_session_id(session_id)
        if not sid:
            log.error(f"Refusing to delete invalid session_id: {session_id!r}")
            return
        assert self.client is not None
        self.client.delete(sid)
        log.info(f"[Redis] DEL {sid}")
