import redis
from typing import Optional, cast

from redis_session_store import RedisSessionStore
from Loggers.StdOutLogger import StdoutLogger

log = StdoutLogger(name="redis_image_store")

# One shared session store (also gives us the resolved redis_uri)
session_store = RedisSessionStore()

class RedisImageStore:
    def __init__(self, redis_uri: Optional[str] = None):
        # ✅ If no redis_uri passed, use the SAME redis that session_store connected to
        uri = (redis_uri or session_store.redis_uri)
        if not uri:
            raise RuntimeError("RedisImageStore: could not resolve redis_uri")
        log.info(f"Using Redis URI: {uri}")
        self.client = redis.from_url(uri, decode_responses=True)

    def save_image(self, image_base64: str, session_id: str) -> str:
        session_data = session_store.get(session_id=session_id)
        if not session_data:
            raise ValueError(f"No session data found for session_id: {session_id}")

        app_id = session_data.get("app_id")
        if not app_id:
            raise ValueError(f"No app_id found in session data for session_id: {session_id}")

        image_ref = f"{app_id}_{session_id}"
        self.client.set(image_ref, image_base64)
        return image_ref

    def get_image(self, image_ref: str) -> Optional[str]:
        return cast(Optional[str], self.client.get(image_ref))

    def cleanup_image(self, image_ref: str):
        self.client.delete(image_ref)
