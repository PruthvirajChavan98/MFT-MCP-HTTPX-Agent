import redis
import json
from typing import Optional

from redis_session_store import RedisSessionStore

# Initialize SessionStore (Redis)
session_store = RedisSessionStore(redis_uri="rediss://red-d1i1cu2dbo4c73a52p3g:f5QVDfxRmEIhy7UDqAbglpzim5LWQZsv@oregon-keyvalue.render.com:6379")

class RedisImageStore:
    def __init__(self, redis_uri: str):
        # Connect to Redis for image storage
        self.client = redis.from_url(redis_uri, decode_responses=True)

    def save_image(self, image_base64: str, session_id: str) -> str:
        # Retrieve session data using SessionStore (Redis)
        session_data = session_store.get(session_id=session_id)
        if not session_data:
            raise ValueError(f"No session data found for session_id: {session_id}")
        
        app_id = session_data.get("app_id")
        if not app_id:
            raise ValueError(f"No app_id found in session data for session_id: {session_id}")
        
        # Create image reference using app_id and session_id
        image_ref = f"{app_id}_{session_id}"
        
        # Save the image base64 data to Redis
        self.client.set(image_ref, image_base64)
        
        return image_ref

    def get_image(self, image_ref: str) -> Optional[str]:
        """
        Retrieve the base64 image string by its reference from Redis.
        """
        image_base64 = self.client.get(image_ref)
        return image_base64 if image_base64 else None

    def cleanup_image(self, image_ref: str):
        """
        Delete the image record from Redis after processing is done.
        """
        self.client.delete(image_ref)
