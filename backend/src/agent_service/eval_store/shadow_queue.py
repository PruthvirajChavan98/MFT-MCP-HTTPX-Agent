from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from src.agent_service.core.config import SHADOW_TRACE_QUEUE_KEY, SHADOW_TRACE_QUEUE_MAXLEN
from src.agent_service.core.session_utils import get_redis

log = logging.getLogger(__name__)


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class RedisTraceQueue:
    def __init__(
        self, queue_key: str = SHADOW_TRACE_QUEUE_KEY, maxlen: int = SHADOW_TRACE_QUEUE_MAXLEN
    ):
        self.queue_key = queue_key
        self.maxlen = maxlen

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
            "trace_id": trace_id,
            "session_id": session_id,
            "user_prompt": user_prompt,
            "agent_response": agent_response,
            "status": status,
            "metadata": metadata or {},
        }
        serialized = json.dumps(payload, ensure_ascii=False)
        await redis.lpush(self.queue_key, serialized)
        if self.maxlen > 0:
            await redis.ltrim(self.queue_key, 0, self.maxlen - 1)

    async def pop_batch(self, *, limit: int) -> list[dict[str, Any]]:
        if limit <= 0:
            return []

        redis = await get_redis()
        items: list[dict[str, Any]] = []
        for _ in range(limit):
            raw = await redis.rpop(self.queue_key)
            if raw is None:
                break
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                log.warning("Skipping malformed shadow queue payload.")
                continue
            if isinstance(parsed, dict):
                items.append(parsed)
        return items

    async def depth(self) -> int:
        redis = await get_redis()
        size = await redis.llen(self.queue_key)
        return int(size)


trace_queue = RedisTraceQueue()
