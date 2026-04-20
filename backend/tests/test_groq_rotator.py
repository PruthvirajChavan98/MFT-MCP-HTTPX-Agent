from __future__ import annotations

import asyncio
import statistics
from collections import Counter

import pytest

from src.agent_service.llm import groq_rotator


class _FakeRedis:
    """Minimal async Redis stub covering INCR / INCRBY / SET-with-EX / EXISTS."""

    def __init__(self) -> None:
        self._ints: dict[str, int] = {}
        self._strings: dict[str, str] = {}

    async def incr(self, key: str) -> int:
        self._ints[key] = self._ints.get(key, 0) + 1
        return self._ints[key]

    async def incrby(self, key: str, amount: int) -> int:
        self._ints[key] = self._ints.get(key, 0) + int(amount)
        return self._ints[key]

    async def set(
        self,
        key: str,
        value: str,
        *,
        ex: int | None = None,
    ) -> bool:
        self._strings[key] = value
        # TTL ignored in the fake — tests that exercise cooling set/unset
        # manipulate `_strings` directly.
        _ = ex
        return True

    async def exists(self, key: str) -> int:
        return 1 if key in self._strings else 0


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    redis = _FakeRedis()

    async def _fake_get_redis() -> _FakeRedis:
        return redis

    monkeypatch.setattr(groq_rotator, "get_redis", _fake_get_redis)
    return redis


# --- next_groq_key -----------------------------------------------------------


@pytest.mark.asyncio
async def test_raises_when_no_keys_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(groq_rotator, "GROQ_API_KEYS", [])
    with pytest.raises(RuntimeError, match="No GROQ_API_KEYS"):
        await groq_rotator.next_groq_key()


@pytest.mark.asyncio
async def test_single_key_fast_path_no_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(groq_rotator, "GROQ_API_KEYS", ["only-key"])

    async def _boom() -> None:
        raise AssertionError("get_redis must not be called on single-key path")

    monkeypatch.setattr(groq_rotator, "get_redis", _boom)
    assert await groq_rotator.next_groq_key() == "only-key"


@pytest.mark.asyncio
async def test_round_robin_across_keys(
    monkeypatch: pytest.MonkeyPatch,
    fake_redis: _FakeRedis,
) -> None:
    keys = ["k1", "k2", "k3", "k4"]
    monkeypatch.setattr(groq_rotator, "GROQ_API_KEYS", keys)

    picked = [await groq_rotator.next_groq_key() for _ in range(12)]

    # 12 calls, 4 keys → each key exactly 3 times.
    counts = Counter(picked)
    expected = dict.fromkeys(keys, 3)
    assert dict(counts) == expected


@pytest.mark.asyncio
async def test_fair_distribution_under_concurrency(
    monkeypatch: pytest.MonkeyPatch,
    fake_redis: _FakeRedis,
) -> None:
    keys = [f"k{i}" for i in range(4)]
    monkeypatch.setattr(groq_rotator, "GROQ_API_KEYS", keys)

    results = await asyncio.gather(*(groq_rotator.next_groq_key() for _ in range(1000)))
    counts = Counter(results)
    mean = sum(counts.values()) / len(counts)
    stdev = statistics.pstdev(counts.values())
    # Atomic INCR guarantees perfectly even distribution in the fake.
    assert stdev / mean < 0.2, f"unfair distribution: {counts}"


@pytest.mark.asyncio
async def test_skips_cooling_keys(
    monkeypatch: pytest.MonkeyPatch,
    fake_redis: _FakeRedis,
) -> None:
    keys = ["hot-a", "cool-b", "hot-c"]
    monkeypatch.setattr(groq_rotator, "GROQ_API_KEYS", keys)
    # Cool the middle key so index 1 is always skipped.
    await groq_rotator.mark_key_cooling("cool-b", ttl_seconds=60)

    picks = [await groq_rotator.next_groq_key() for _ in range(10)]
    assert "cool-b" not in picks
    # Other two keys still alternate.
    assert set(picks) == {"hot-a", "hot-c"}


@pytest.mark.asyncio
async def test_falls_through_when_all_keys_cooling(
    monkeypatch: pytest.MonkeyPatch,
    fake_redis: _FakeRedis,
) -> None:
    keys = ["a", "b"]
    monkeypatch.setattr(groq_rotator, "GROQ_API_KEYS", keys)
    for k in keys:
        await groq_rotator.mark_key_cooling(k, ttl_seconds=60)

    # Must not raise; returns the modulo pick even though every key is cooling.
    picked = await groq_rotator.next_groq_key()
    assert picked in keys


# --- next_groq_keys ---------------------------------------------------------


@pytest.mark.asyncio
async def test_next_groq_keys_returns_n_distinct_when_enough_keys(
    monkeypatch: pytest.MonkeyPatch,
    fake_redis: _FakeRedis,
) -> None:
    keys = ["k0", "k1", "k2", "k3"]
    monkeypatch.setattr(groq_rotator, "GROQ_API_KEYS", keys)

    picked = await groq_rotator.next_groq_keys(3)

    assert len(picked) == 3
    assert len(set(picked)) == 3  # distinct
    assert all(k in keys for k in picked)


@pytest.mark.asyncio
async def test_next_groq_keys_cycles_when_n_exceeds_keyset(
    monkeypatch: pytest.MonkeyPatch,
    fake_redis: _FakeRedis,
) -> None:
    keys = ["k0", "k1"]  # only 2 keys
    monkeypatch.setattr(groq_rotator, "GROQ_API_KEYS", keys)

    picked = await groq_rotator.next_groq_keys(5)

    assert len(picked) == 5
    # Duplicates are expected; every returned slot must be a configured key.
    assert all(k in keys for k in picked)


@pytest.mark.asyncio
async def test_next_groq_keys_single_key_fast_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(groq_rotator, "GROQ_API_KEYS", ["only-key"])

    async def _boom() -> None:
        raise AssertionError("get_redis must not be called on single-key path")

    monkeypatch.setattr(groq_rotator, "get_redis", _boom)
    assert await groq_rotator.next_groq_keys(3) == ["only-key"] * 3


@pytest.mark.asyncio
async def test_next_groq_keys_zero_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(groq_rotator, "GROQ_API_KEYS", ["a", "b"])
    assert await groq_rotator.next_groq_keys(0) == []


@pytest.mark.asyncio
async def test_concurrent_next_groq_keys_still_fair(
    monkeypatch: pytest.MonkeyPatch,
    fake_redis: _FakeRedis,
) -> None:
    keys = [f"k{i}" for i in range(4)]
    monkeypatch.setattr(groq_rotator, "GROQ_API_KEYS", keys)

    # 100 evaluators each asking for 3 keys → 300 key picks total.
    batches = await asyncio.gather(*(groq_rotator.next_groq_keys(3) for _ in range(100)))
    flat = [k for batch in batches for k in batch]
    counts = Counter(flat)
    mean = sum(counts.values()) / len(counts)
    stdev = statistics.pstdev(counts.values())
    assert stdev / mean < 0.2, f"unfair distribution under concurrency: {counts}"


# --- mark_key_cooling -------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_key_cooling_noop_on_empty_key(
    monkeypatch: pytest.MonkeyPatch,
    fake_redis: _FakeRedis,
) -> None:
    # Should not call Redis at all.
    async def _boom() -> None:
        raise AssertionError("get_redis must not be called with empty key")

    monkeypatch.setattr(groq_rotator, "get_redis", _boom)
    await groq_rotator.mark_key_cooling("")  # must not raise


@pytest.mark.asyncio
async def test_mark_key_cooling_noop_on_nonpositive_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _boom() -> None:
        raise AssertionError("get_redis must not be called with ttl<=0")

    monkeypatch.setattr(groq_rotator, "get_redis", _boom)
    await groq_rotator.mark_key_cooling("whatever", ttl_seconds=0)


@pytest.mark.asyncio
async def test_mark_key_cooling_persists_for_lookup(
    monkeypatch: pytest.MonkeyPatch,
    fake_redis: _FakeRedis,
) -> None:
    monkeypatch.setattr(groq_rotator, "GROQ_API_KEYS", ["a", "b"])
    await groq_rotator.mark_key_cooling("a", ttl_seconds=30)
    assert await groq_rotator._is_cooling(fake_redis, "a") is True
    assert await groq_rotator._is_cooling(fake_redis, "b") is False
