"""
Production-Grade Redis Event Bus.
Handles decoupled Pub/Sub broadcasting for real-time frontend SSE feeds.
"""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict

from redis.asyncio import Redis

from src.agent_service.core.session_utils import get_redis

log = logging.getLogger("event_bus")


class EventBus:
    def __init__(self):
        self._redis: Redis | None = None

    async def _get_client(self) -> Redis:
        if self._redis is None:
            self._redis = await get_redis()
        return self._redis

    async def publish(self, channel: str, event_type: str, data: Dict[str, Any]) -> None:
        """Fire-and-forget broadcast to all listening workers/clients."""
        try:
            client = await self._get_client()
            payload = json.dumps({"event": event_type, "data": data}, ensure_ascii=False)
            await client.publish(channel, payload)
        except Exception as e:
            log.error(f"Failed to publish to {channel}: {e}")

    async def subscribe(self, channel: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Yields events from a Redis channel for SSE consumption."""
        client = await self._get_client()
        pubsub = client.pubsub()
        await pubsub.subscribe(channel)

        log.info(f"Subscribed to EventBus channel: {channel}")
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        yield json.loads(message["data"])
                    except json.JSONDecodeError:
                        continue
        except asyncio.CancelledError:
            log.info(f"Unsubscribing from {channel}")
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    async def close(self) -> None:
        """
        Gracefully terminate EventBus resources.
        Currently relies on the global Redis pool closure, but acts as a
        forward-compatible hook for dedicated Pub/Sub connections.
        """
        if self._redis:
            # We don't close the client here because it's managed by the global pool.
            # But we release the reference.
            self._redis = None
            log.info("EventBus resources released.")


event_bus = EventBus()
