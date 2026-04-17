"""Production-Grade Redis Event Bus.

Handles decoupled Pub/Sub broadcasting for real-time frontend SSE feeds.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from redis.asyncio import Redis

from src.agent_service.core.session_utils import get_redis

log = logging.getLogger("event_bus")


class EventBus:
    def __init__(self) -> None:
        self._redis: Redis | None = None
        self._lock: asyncio.Lock | None = None

    def _get_lock(self) -> asyncio.Lock:
        """Lazy-init the lock so it binds to whatever loop is live at first use.

        Creating asyncio.Lock() at module or __init__ time can bind to a stale
        loop if the caller imports this module before an event loop exists
        (common in pytest with asyncio_mode='strict'). Lazy creation on first
        await avoids the RuntimeError("Task got Future attached to a different
        loop") bug class.
        """
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def _get_client(self) -> Redis:
        if self._redis is None:
            async with self._get_lock():
                if self._redis is None:
                    self._redis = await get_redis()
        return self._redis

    async def publish(self, channel: str, event_type: str, data: dict[str, Any]) -> None:
        """Fire-and-forget broadcast to all listening workers/clients."""
        try:
            client = await self._get_client()
            payload = json.dumps({"event": event_type, "data": data}, ensure_ascii=False)
            await client.publish(channel, payload)
        except Exception:
            # Fire-and-forget: the caller already moved on. Capture the traceback
            # for debugging without re-raising.
            log.error("Failed to publish to %s", channel, exc_info=True)

    async def subscribe(self, channel: str) -> AsyncGenerator[dict[str, Any], None]:
        """Yields events from a Redis channel for SSE consumption."""
        client = await self._get_client()
        pubsub = client.pubsub()
        await pubsub.subscribe(channel)

        log.info("Subscribed to EventBus channel: %s", channel)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        yield json.loads(message["data"])
                    except json.JSONDecodeError:
                        continue
        except asyncio.CancelledError:
            log.info("Unsubscribing from %s", channel)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    async def close(self) -> None:
        """Gracefully terminate EventBus resources.

        Subscriber-owned pubsub objects self-clean on asyncio.CancelledError in
        subscribe()'s finally block, so we only release our reference to the
        shared Redis client (which is managed by the global pool elsewhere).
        """
        if self._redis:
            self._redis = None
            log.info("EventBus resources released.")


event_bus = EventBus()
