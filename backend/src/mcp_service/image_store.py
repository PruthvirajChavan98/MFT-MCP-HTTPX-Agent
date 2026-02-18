import logging
from typing import Optional, cast

from .session_store import RedisSessionStore

log = logging.getLogger(name="redis_image_store")


class RedisImageStore:
    def __init__(self, session_store: Optional[RedisSessionStore] = None):
        self.session_store = session_store or RedisSessionStore()
        self.client = self.session_store.client

    def save_image(self, image_base64: str, session_id: str) -> str:
        session_data = self.session_store.get(session_id=session_id)
        if not session_data:
            raise ValueError(f"No session data found for session_id: {session_id}")
        app_id = session_data.get("app_id")
        if not app_id:
            raise ValueError(f"No app_id found for session_id: {session_id}")
        image_ref = f"{app_id}_{session_id}"
        self.client.set(image_ref, image_base64)  # type: ignore
        return image_ref

    def get_image(self, image_ref: str) -> Optional[str]:
        return cast(Optional[str], self.client.get(image_ref))  # type: ignore

    def cleanup_image(self, image_ref: str):
        self.client.delete(image_ref)  # type: ignore
