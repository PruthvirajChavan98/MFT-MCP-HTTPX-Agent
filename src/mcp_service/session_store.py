import json
from typing import Optional, cast
import redis
from src.common.logger import StdoutLogger
from .config import REDIS_URL

log = StdoutLogger(name="redis_session_store")

def _redact_uri(uri: str) -> str:
    try:
        if "://" in uri and "@" in uri:
            scheme, rest = uri.split("://", 1)
            creds, hostpart = rest.split("@", 1)
            if ":" in creds:
                user = creds.split(":", 1)[0]
                return f"{scheme}://{user}:***@{hostpart}"
    except Exception: pass
    return uri

class RedisSessionStore:
    def __init__(self, redis_uri: Optional[str] = None):
        self.redis_uri = redis_uri or REDIS_URL
        self.client: Optional[redis.Redis] = None
        try:
            c = redis.from_url(self.redis_uri, decode_responses=True)
            c.ping()
            self.client = c
            log.info(f"✅ Connected to Redis: {_redact_uri(self.redis_uri)}")
        except Exception as e:
            log.error(f"❌ Redis connect failed: {e}")
            raise RuntimeError(f"Could not connect to Redis: {e}")

    def _valid_session_id(self, session_id: object) -> Optional[str]:
        if session_id is None: return None
        sid = str(session_id).strip()
        if not sid or sid.lower() in {"null", "none"}: return None
        return sid

    def set(self, session_id: str, data: dict):
        sid = self._valid_session_id(session_id)
        if not sid: return
        self.client.set(sid, json.dumps(data, ensure_ascii=False))
        log.info(f"[Redis] SET {sid} | Keys: {list(data.keys())}")

    def get(self, session_id: str) -> Optional[dict]:
        sid = self._valid_session_id(session_id)
        if not sid: return None
        data = cast(Optional[str], self.client.get(sid))
        if not data:
            log.warning(f"[Redis] MISS {sid}")
            return None
        log.info(f"[Redis] HIT {sid}")
        return json.loads(data)

    def update(self, session_id: str, updates: dict):
        sid = self._valid_session_id(session_id)
        if not sid: return
        current = self.get(sid) or {}
        current.update(updates)
        self.set(sid, current)

    def delete(self, session_id: str):
        sid = self._valid_session_id(session_id)
        if not sid: return
        self.client.delete(sid)
        log.info(f"[Redis] DEL {sid}")
