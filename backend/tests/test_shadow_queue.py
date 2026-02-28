from __future__ import annotations

import pytest

from src.agent_service.eval_store import shadow_queue


class _FakeRedis:
    def __init__(self):
        self._items: dict[str, list[str]] = {}

    def _bucket(self, key: str) -> list[str]:
        return self._items.setdefault(key, [])

    async def lpush(self, key: str, value: str):
        self._bucket(key).insert(0, value)

    async def ltrim(self, key: str, start: int, stop: int):
        bucket = self._bucket(key)
        if stop < 0:
            self._items[key] = []
        else:
            self._items[key] = bucket[start : stop + 1]

    async def rpop(self, key: str):
        bucket = self._bucket(key)
        if not bucket:
            return None
        return bucket.pop()

    async def llen(self, key: str):
        return len(self._bucket(key))


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


@pytest.mark.asyncio
async def test_redis_trace_queue_requeue_and_dead_letter(monkeypatch):
    fake_redis = _FakeRedis()

    async def _fake_get_redis():
        return fake_redis

    monkeypatch.setattr(shadow_queue, "get_redis", _fake_get_redis)
    queue = shadow_queue.RedisTraceQueue(
        queue_key="test:shadow",
        dlq_key="test:shadow:dlq",
        maxlen=100,
        dlq_maxlen=100,
        max_retries=1,
    )

    requeued, dead_lettered = await queue.requeue_or_dead_letter_batch(
        [{"trace_id": "trace-1", "retry_count": 0}],
        reason="temporary failure",
    )
    assert requeued == 1
    assert dead_lettered == 0
    assert await queue.depth() == 1
    assert await queue.dead_letter_depth() == 0

    requeued, dead_lettered = await queue.requeue_or_dead_letter_batch(
        [{"trace_id": "trace-2", "retry_count": 1}],
        reason="permanent failure",
    )
    assert requeued == 0
    assert dead_lettered == 1
    assert await queue.dead_letter_depth() == 1
