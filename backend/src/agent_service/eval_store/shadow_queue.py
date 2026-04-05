from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from prometheus_client import Gauge

from src.agent_service.core.config import (
    SHADOW_TRACE_DLQ_KEY,
    SHADOW_TRACE_QUEUE_DLQ_MAXLEN,
    SHADOW_TRACE_QUEUE_KEY,
    SHADOW_TRACE_QUEUE_MAX_RETRIES,
    SHADOW_TRACE_QUEUE_MAXLEN,
)
from src.agent_service.core.session_utils import get_redis

log = logging.getLogger(__name__)

SHADOW_TRACE_QUEUE_DEPTH = Gauge(
    "agent_shadow_trace_queue_depth",
    "Current number of pending shadow trace queue items.",
)

SHADOW_TRACE_DLQ_DEPTH = Gauge(
    "agent_shadow_trace_dlq_depth",
    "Current number of dead-lettered shadow trace queue items.",
)


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class RedisTraceQueue:
    def __init__(
        self,
        queue_key: str = SHADOW_TRACE_QUEUE_KEY,
        maxlen: int = SHADOW_TRACE_QUEUE_MAXLEN,
        dlq_key: str = SHADOW_TRACE_DLQ_KEY,
        dlq_maxlen: int = SHADOW_TRACE_QUEUE_DLQ_MAXLEN,
        max_retries: int = SHADOW_TRACE_QUEUE_MAX_RETRIES,
    ):
        self.queue_key = queue_key
        self.maxlen = maxlen
        self.dlq_key = dlq_key
        self.dlq_maxlen = dlq_maxlen
        self.max_retries = max_retries

    async def _refresh_depth_metrics(self, redis: Any) -> None:
        SHADOW_TRACE_QUEUE_DEPTH.set(float(await redis.llen(self.queue_key)))  # type: ignore[misc]
        SHADOW_TRACE_DLQ_DEPTH.set(float(await redis.llen(self.dlq_key)))  # type: ignore[misc]

    async def enqueue_trace(
        self,
        *,
        session_id: str,
        user_prompt: str,
        agent_response: str,
        trace_id: str | None = None,
        status: str = "success",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        redis = await get_redis()
        payload = {
            "enqueued_at": _utc_iso_now(),
            "retry_count": 0,
            "trace_id": trace_id,
            "session_id": session_id,
            "user_prompt": user_prompt,
            "agent_response": agent_response,
            "status": status,
            "metadata": metadata or {},
        }
        serialized = json.dumps(payload, ensure_ascii=False)
        await redis.lpush(self.queue_key, serialized)  # type: ignore[misc]
        if self.maxlen > 0:
            await redis.ltrim(self.queue_key, 0, self.maxlen - 1)  # type: ignore[misc]
        await self._refresh_depth_metrics(redis)

    async def pop_batch(self, *, limit: int) -> list[dict[str, Any]]:
        if limit <= 0:
            return []

        redis = await get_redis()
        items: list[dict[str, Any]] = []
        for _ in range(limit):
            raw = await redis.rpop(self.queue_key)  # type: ignore[misc]
            if raw is None:
                break
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                log.warning("Skipping malformed shadow queue payload.")
                continue
            if isinstance(parsed, dict):
                items.append(parsed)
        await self._refresh_depth_metrics(redis)
        return items

    async def depth(self) -> int:
        redis = await get_redis()
        size = await redis.llen(self.queue_key)  # type: ignore[misc]
        SHADOW_TRACE_QUEUE_DEPTH.set(float(size))
        return int(size)

    async def dead_letter_depth(self) -> int:
        redis = await get_redis()
        size = await redis.llen(self.dlq_key)  # type: ignore[misc]
        SHADOW_TRACE_DLQ_DEPTH.set(float(size))
        return int(size)

    async def requeue_or_dead_letter_batch(
        self,
        items: list[dict[str, Any]],
        *,
        reason: str,
    ) -> tuple[int, int]:
        """Requeue failed items with bounded retries, then dead-letter."""
        if not items:
            return (0, 0)

        redis = await get_redis()
        requeued = 0
        dead_lettered = 0
        for item in items:
            payload = dict(item)
            retries = int(payload.get("retry_count") or 0) + 1
            payload["retry_count"] = retries
            payload["last_error"] = reason
            payload["last_failed_at"] = _utc_iso_now()
            serialized = json.dumps(payload, ensure_ascii=False)
            if retries > self.max_retries:
                await redis.lpush(self.dlq_key, serialized)  # type: ignore[misc]
                dead_lettered += 1
            else:
                await redis.lpush(self.queue_key, serialized)  # type: ignore[misc]
                requeued += 1

        if self.maxlen > 0:
            await redis.ltrim(self.queue_key, 0, self.maxlen - 1)  # type: ignore[misc]
        if self.dlq_maxlen > 0:
            await redis.ltrim(self.dlq_key, 0, self.dlq_maxlen - 1)  # type: ignore[misc]
        await self._refresh_depth_metrics(redis)
        return (requeued, dead_lettered)


trace_queue = RedisTraceQueue()
