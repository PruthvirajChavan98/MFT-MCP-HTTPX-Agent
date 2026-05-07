"""Tests for the inline-guard vector-similarity cache (Layer 2.5).

Lock the contracts:
* Cache disabled → classifier called every time, behaviour parity with the
  shipped guard.
* Cache miss → classifier called, write-back scheduled.
* Cache hit (fresh, matching versions) → classifier *not* called.
* Cache hit on stale model_version → treated as miss.
* Cache hit on stale embedder_version → treated as miss.
* Cache hit on expired TTL → treated as miss.
* Reshadow path → classifier runs even on a hit; mismatch logged.
* Milvus error during lookup → fail-open to classifier.

All tests mock at the cache + classifier boundary; no live network.
"""

from __future__ import annotations

import time
from typing import Any

import pytest
from langchain_core.documents import Document

from src.agent_service.security import inline_guard
from src.agent_service.security import inline_guard_cache as cache_mod


@pytest.fixture(autouse=True)
def _enable_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(inline_guard, "INLINE_GUARD_ENABLED", True)


def _enable_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both modules read INLINE_GUARD_CACHE_ENABLED at import time; we patch
    every site that read it so the cache logic actually runs in tests."""
    monkeypatch.setattr(inline_guard, "INLINE_GUARD_CACHE_ENABLED", True)
    monkeypatch.setattr(cache_mod, "INLINE_GUARD_CACHE_ENABLED", True)


def _make_hit_doc(
    *,
    decision: str = "allow",
    reason_code: str = "safe",
    risk_score: float = 0.0,
    model_version: str | None = None,
    embedder_version: str | None = None,
    ts_offset_seconds: int = 0,
) -> tuple[Document, float]:
    """Construct a langchain Document that mirrors what `inline_guard_cache`
    expects from `asimilarity_search_with_score`. The float is a *distance*
    (langchain-milvus returns COSINE distance in [0, 2])."""
    meta = {
        "decision": decision,
        "reason_code": reason_code,
        "risk_score": risk_score,
        "model_version": model_version or cache_mod.INLINE_GUARD_GROQ_MODEL,
        "embedder_version": embedder_version or cache_mod.LOCAL_EMBEDDER_VERSION,
        "content_hash": "abc123",
        "ts": int(time.time()) - ts_offset_seconds,
    }
    return Document(page_content="cached prompt", metadata=meta), 0.05  # dist 0.05 -> sim ~0.975


class _StubStore:
    """Mimics `langchain_milvus.Milvus` for the two methods the cache calls."""

    def __init__(self, hits: list[tuple[Document, float]] | None = None) -> None:
        self.hits = hits or []
        self.added: list[Document] = []
        self.lookup_calls = 0

    async def asimilarity_search_with_score(self, prompt: str, k: int = 1):
        self.lookup_calls += 1
        return self.hits

    async def aadd_documents(self, docs: list[Document]) -> None:
        self.added.extend(docs)


def _install_store(monkeypatch: pytest.MonkeyPatch, store: _StubStore | None) -> None:
    """Replace the lazy store accessor inside the cache module."""
    monkeypatch.setattr(cache_mod, "_get_store", lambda: store)


async def _async_bool(value: bool) -> bool:
    return value


# ─── Cache disabled — behaviour parity ────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_disabled_runs_classifier_every_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(inline_guard, "INLINE_GUARD_CACHE_ENABLED", False)
    monkeypatch.setattr(cache_mod, "INLINE_GUARD_CACHE_ENABLED", False)
    classifier_calls = 0

    async def _stub(prompt: str) -> bool:
        nonlocal classifier_calls
        classifier_calls += 1
        return True

    monkeypatch.setattr(inline_guard, "_groq_guard_check", _stub)
    decision = await inline_guard.evaluate_prompt_safety_decision("show my loan")
    assert decision.decision == "allow"
    assert classifier_calls == 1


# ─── Cache miss → classifier + writeback ──────────────────────────────────


@pytest.mark.asyncio
async def test_cache_miss_calls_classifier_and_schedules_writeback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_cache(monkeypatch)
    store = _StubStore(hits=[])  # explicit miss
    _install_store(monkeypatch, store)

    monkeypatch.setattr(inline_guard, "_groq_guard_check", lambda p: _async_bool(True))

    scheduled: list[Any] = []

    def _capture(coro):
        scheduled.append(coro)
        coro.close()  # prevent "coroutine was never awaited" warning

    monkeypatch.setattr(cache_mod, "schedule", _capture)

    decision = await inline_guard.evaluate_prompt_safety_decision("show my loan")
    assert decision.decision == "allow"
    assert store.lookup_calls == 1
    assert len(scheduled) == 1, "writeback must be scheduled on miss"


# ─── Cache hit → classifier skipped ───────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_hit_returns_cached_decision_without_calling_classifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_cache(monkeypatch)
    monkeypatch.setattr(cache_mod, "INLINE_GUARD_CACHE_RESHADOW_RATE", 0.0)

    store = _StubStore(hits=[_make_hit_doc(decision="allow", reason_code="safe")])
    _install_store(monkeypatch, store)

    classifier_calls = 0

    async def _stub(prompt: str) -> bool:
        nonlocal classifier_calls
        classifier_calls += 1
        return True

    monkeypatch.setattr(inline_guard, "_groq_guard_check", _stub)

    decision = await inline_guard.evaluate_prompt_safety_decision("show my loan")
    assert decision.decision == "allow"
    assert decision.reason_code == "safe"
    assert classifier_calls == 0
    assert any(check.name == "cache_hit" for check in decision.checks)


# ─── Stale model_version → fall through to classifier ────────────────────


@pytest.mark.asyncio
async def test_cache_hit_with_stale_model_version_falls_through_to_classifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_cache(monkeypatch)
    monkeypatch.setattr(cache_mod, "INLINE_GUARD_CACHE_RESHADOW_RATE", 0.0)

    store = _StubStore(hits=[_make_hit_doc(model_version="old-safeguard-13b")])
    _install_store(monkeypatch, store)

    classifier_calls = 0

    async def _stub(prompt: str) -> bool:
        nonlocal classifier_calls
        classifier_calls += 1
        return True

    monkeypatch.setattr(inline_guard, "_groq_guard_check", _stub)

    decision = await inline_guard.evaluate_prompt_safety_decision("show my loan")
    assert decision.decision == "allow"
    assert classifier_calls == 1


# ─── Stale embedder_version → fall through to classifier ─────────────────


@pytest.mark.asyncio
async def test_cache_hit_with_stale_embedder_version_falls_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_cache(monkeypatch)
    monkeypatch.setattr(cache_mod, "INLINE_GUARD_CACHE_RESHADOW_RATE", 0.0)

    store = _StubStore(hits=[_make_hit_doc(embedder_version="MiniLM-OLD")])
    _install_store(monkeypatch, store)

    classifier_calls = 0

    async def _stub(prompt: str) -> bool:
        nonlocal classifier_calls
        classifier_calls += 1
        return True

    monkeypatch.setattr(inline_guard, "_groq_guard_check", _stub)

    decision = await inline_guard.evaluate_prompt_safety_decision("show my loan")
    assert decision.decision == "allow"
    assert classifier_calls == 1


# ─── Expired TTL → fall through to classifier ────────────────────────────


@pytest.mark.asyncio
async def test_cache_hit_past_ttl_falls_through(monkeypatch: pytest.MonkeyPatch) -> None:
    _enable_cache(monkeypatch)
    monkeypatch.setattr(cache_mod, "INLINE_GUARD_CACHE_TTL_SECONDS", 60)
    monkeypatch.setattr(cache_mod, "INLINE_GUARD_CACHE_RESHADOW_RATE", 0.0)

    # ts is 5 minutes old → past 60-second TTL.
    store = _StubStore(hits=[_make_hit_doc(ts_offset_seconds=300)])
    _install_store(monkeypatch, store)

    classifier_calls = 0

    async def _stub(prompt: str) -> bool:
        nonlocal classifier_calls
        classifier_calls += 1
        return True

    monkeypatch.setattr(inline_guard, "_groq_guard_check", _stub)

    decision = await inline_guard.evaluate_prompt_safety_decision("show my loan")
    assert decision.decision == "allow"
    assert classifier_calls == 1


# ─── Reshadow loop → classifier still runs on hit, mismatch logged ───────


@pytest.mark.asyncio
async def test_reshadow_runs_classifier_and_logs_mismatch(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _enable_cache(monkeypatch)
    monkeypatch.setattr(cache_mod, "INLINE_GUARD_CACHE_RESHADOW_RATE", 1.0)  # always reshadow

    # Cached as "block"; classifier votes "allow" → mismatch path.
    store = _StubStore(hits=[_make_hit_doc(decision="block", reason_code="unsafe_signal")])
    _install_store(monkeypatch, store)

    monkeypatch.setattr(inline_guard, "_groq_guard_check", lambda p: _async_bool(True))

    with caplog.at_level("WARNING"):
        decision = await inline_guard.evaluate_prompt_safety_decision("show my loan")

    # Classifier verdict wins on mismatch.
    assert decision.decision == "allow"
    assert any("reshadow mismatch" in rec.message for rec in caplog.records)


# ─── Milvus error → fail-open to classifier ──────────────────────────────


@pytest.mark.asyncio
async def test_lookup_failure_falls_through_to_classifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_cache(monkeypatch)

    class _BrokenStore:
        async def asimilarity_search_with_score(self, prompt: str, k: int = 1):
            raise RuntimeError("milvus unreachable")

        async def aadd_documents(self, docs):
            return None

    _install_store(monkeypatch, _BrokenStore())

    classifier_calls = 0

    async def _stub(prompt: str) -> bool:
        nonlocal classifier_calls
        classifier_calls += 1
        return True

    monkeypatch.setattr(inline_guard, "_groq_guard_check", _stub)

    decision = await inline_guard.evaluate_prompt_safety_decision("show my loan")
    assert decision.decision == "allow"
    assert classifier_calls == 1
