from __future__ import annotations

import pytest

from src.agent_service.eval_store import shadow_queue


class _FakeRedis:
    def __init__(self):
        self._items: list[str] = []

    async def lpush(self, key: str, value: str):
        self._items.insert(0, value)

    async def ltrim(self, key: str, start: int, stop: int):
        if stop < 0:
            self._items = []
        else:
            self._items = self._items[start : stop + 1]

    async def rpop(self, key: str):
        if not self._items:
            return None
        return self._items.pop()

    async def llen(self, key: str):
        return len(self._items)


@pytest.mark.asyncio
async def test_redis_trace_queue_enqueue_and_pop_batch(monkeypatch):
    fake_redis = _FakeRedis()

    async def _fake_get_redis():
        return fake_redis

    monkeypatch.setattr(shadow_queue, "get_redis", _fake_get_redis)
    queue = shadow_queue.RedisTraceQueue(queue_key="test:shadow", maxlen=100)

    await queue.enqueue_trace(
        session_id="s1",
        user_prompt="user question",
        agent_response="assistant answer",
        trace_id="trace-1",
    )
    await queue.enqueue_trace(
        session_id="s2",
        user_prompt="second question",
        agent_response="second answer",
        trace_id="trace-2",
    )

    items = await queue.pop_batch(limit=2)
    assert len(items) == 2
    assert items[0]["trace_id"] == "trace-1"
    assert items[1]["trace_id"] == "trace-2"
    assert await queue.depth() == 0
