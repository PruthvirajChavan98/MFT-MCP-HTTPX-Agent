"""Prove that ShadowJudgeWorker._call_groq round-robins Groq keys per batch.

Regression lock for the fix that moved shadow judge off `GROQ_API_KEYS[0]`
onto the shared `groq_rotator.next_groq_key()` helper. Also asserts that
a 429 response cools the offending key.
"""

from __future__ import annotations

from collections import Counter

import httpx
import pytest

from src.agent_service.llm import groq_rotator
from src.agent_service.worker import shadow_judge_worker
from src.agent_service.worker.shadow_judge_worker import ShadowJudgeWorker


class _FakeRedis:
    def __init__(self) -> None:
        self._ints: dict[str, int] = {}
        self._strings: dict[str, str] = {}

    async def incr(self, key: str) -> int:
        self._ints[key] = self._ints.get(key, 0) + 1
        return self._ints[key]

    async def incrby(self, key: str, amount: int) -> int:
        self._ints[key] = self._ints.get(key, 0) + int(amount)
        return self._ints[key]

    async def set(self, key: str, value: str, *, ex: int | None = None) -> bool:
        self._strings[key] = value
        _ = ex
        return True

    async def exists(self, key: str) -> int:
        return 1 if key in self._strings else 0


@pytest.fixture
def redis_stub(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    redis = _FakeRedis()

    async def _fake_get_redis() -> _FakeRedis:
        return redis

    monkeypatch.setattr(groq_rotator, "get_redis", _fake_get_redis)
    return redis


def _make_response(status: int, *, text: str = "") -> httpx.Response:
    body = (
        b'{"choices":[{"message":{"content":"{\\"evaluations\\":[]}"}}]}'
        if not text
        else text.encode()
    )
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return httpx.Response(status_code=status, content=body, request=request)


class _AuthCapturingClient:
    """Fake HTTP client that records Authorization headers and returns 200."""

    def __init__(self) -> None:
        self.auth_headers: list[str] = []

    async def post(self, url: str, *, json, headers):
        self.auth_headers.append(headers["Authorization"])
        return _make_response(200)


class _Client429:
    """Fake HTTP client that always returns 429."""

    def __init__(self) -> None:
        self.auth_headers: list[str] = []

    async def post(self, url: str, *, json, headers):
        self.auth_headers.append(headers["Authorization"])
        return _make_response(429)


@pytest.mark.asyncio
async def test_shadow_judge_round_robins_keys_across_batches(
    monkeypatch: pytest.MonkeyPatch,
    redis_stub: _FakeRedis,
) -> None:
    keys = ["k-alpha", "k-beta", "k-gamma"]
    monkeypatch.setattr(groq_rotator, "GROQ_API_KEYS", keys)
    monkeypatch.setattr(shadow_judge_worker, "GROQ_API_KEYS", keys)

    client = _AuthCapturingClient()

    async def _fake_get_http_client() -> _AuthCapturingClient:
        return client

    monkeypatch.setattr(shadow_judge_worker, "get_http_client", _fake_get_http_client)

    worker = ShadowJudgeWorker()
    batch = [{"trace_id": "t", "session_id": "s", "user_prompt": "q", "agent_response": "a"}]

    for _ in range(9):
        await worker._call_groq(batch, model="gpt-oss-120b")  # noqa: SLF001

    keys_seen = [h.removeprefix("Bearer ") for h in client.auth_headers]
    counts = Counter(keys_seen)
    # Exact even split — atomic INCR across 9 calls / 3 keys.
    assert dict(counts) == dict.fromkeys(keys, 3)


@pytest.mark.asyncio
async def test_shadow_judge_cools_key_on_429(
    monkeypatch: pytest.MonkeyPatch,
    redis_stub: _FakeRedis,
) -> None:
    keys = ["k-alpha", "k-beta"]
    monkeypatch.setattr(groq_rotator, "GROQ_API_KEYS", keys)
    monkeypatch.setattr(shadow_judge_worker, "GROQ_API_KEYS", keys)

    client = _Client429()

    async def _fake_get_http_client() -> _Client429:
        return client

    monkeypatch.setattr(shadow_judge_worker, "get_http_client", _fake_get_http_client)

    worker = ShadowJudgeWorker()
    batch = [{"trace_id": "t", "session_id": "s", "user_prompt": "q", "agent_response": "a"}]

    with pytest.raises(httpx.HTTPStatusError):
        await worker._call_groq(batch, model="gpt-oss-120b")  # noqa: SLF001

    # Confirm one cooling marker was set; the key matches what was used.
    used_key = client.auth_headers[0].removeprefix("Bearer ")
    assert await groq_rotator._is_cooling(redis_stub, used_key) is True  # noqa: SLF001
