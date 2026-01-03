import redis
import json
from typing import Optional


class RedisSessionStore:
    def __init__(self, redis_uri: str):
        # Connect to Redis using the URI
        self.client = redis.from_url(redis_uri, decode_responses=True)

    def set(self, session_id: str, data: dict):
        # Set data in Redis with an expiration time (optional)
        self.client.set(session_id, json.dumps(data))

    def get(self, session_id: str) -> Optional[dict]:
        data = self.client.get(session_id)
        return json.loads(data) if data else None

    def update(self, session_id: str, updates: dict):
        current_data = self.get(session_id) or {}
        current_data.update(updates)
        self.set(session_id, current_data)

    def delete(self, session_id: str):
        self.client.delete(session_id)