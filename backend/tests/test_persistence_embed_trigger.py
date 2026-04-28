"""Regression for the "orphan trace" bug.

Before this fix, `_commit_bundle` only fired
``EvalEmbedder.embed_trace_if_needed`` inside
`features/shadow_eval.py` — and only for traces that produced
eval results. At the default `SHADOW_EVAL_SAMPLE_RATE = 0.05`, the
other 95% of traces shipped to Postgres without a Milvus row, so
semantic trace search could only match 8 / 153 rows in production.

The commit-bundle path now schedules the trace embed unconditionally
as a fire-and-forget task. Tests:

1. Every bundle commit schedules exactly one embed, even when
   events and evals are empty.
2. When the embedder is disabled (missing `OPENROUTER_API_KEY`),
   no task is scheduled.
3. Task-set bookkeeping: scheduled tasks are tracked until done,
   then released (no strong-ref leak).
"""

from __future__ import annotations

from typing import Any

import pytest

from src.agent_service.eval_store import _bg
from src.agent_service.features.eval import persistence


class _FakeStore:
    def __init__(self) -> None:
        self.trace_calls: list[dict[str, Any]] = []
        self.event_calls: list[tuple[str, list[dict[str, Any]]]] = []
        self.eval_calls: list[tuple[str, list[dict[str, Any]]]] = []

    async def upsert_trace(self, _pool, trace):
        self.trace_calls.append(trace)

    async def upsert_events(self, _pool, trace_id, events):
        self.event_calls.append((trace_id, events))

    async def upsert_evals(self, _pool, trace_id, evals):
        self.eval_calls.append((trace_id, evals))


class _SpyEmbedder:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self.calls: list[tuple[Any, dict[str, Any], list[dict[str, Any]]]] = []

    async def embed_trace_if_needed(self, pool, trace, events):
        self.calls.append((pool, trace, events))


@pytest.fixture(autouse=True)
def _reset_bg_tasks():
    """Drain any leftover tasks so task-count assertions are clean."""
    _bg._BG_TASKS.clear()
    yield
    _bg._BG_TASKS.clear()


@pytest.mark.asyncio
async def test_commit_bundle_schedules_trace_embed_even_with_zero_evals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _FakeStore()
    embedder = _SpyEmbedder(enabled=True)
    monkeypatch.setattr(persistence, "STORE", store)
    monkeypatch.setattr(persistence, "get_eval_embedder", lambda: embedder)
    monkeypatch.setattr(persistence, "get_shared_pool", lambda: object())

    await persistence._commit_bundle(
        trace={"trace_id": "t-1", "inputs": {"question": "fuck off"}},
        events=[],
        evals=[],
    )

    # Task scheduled but not yet awaited by _commit_bundle (fire-and-forget).
    # Drain it so we can assert the spy got called.
    for task in list(_bg._BG_TASKS):
        await task

    assert len(embedder.calls) == 1
    _, trace, events = embedder.calls[0]
    assert trace["trace_id"] == "t-1"
    assert events == []


@pytest.mark.asyncio
async def test_commit_bundle_skips_embed_when_embedder_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _FakeStore()
    embedder = _SpyEmbedder(enabled=False)
    monkeypatch.setattr(persistence, "STORE", store)
    monkeypatch.setattr(persistence, "get_eval_embedder", lambda: embedder)
    monkeypatch.setattr(persistence, "get_shared_pool", lambda: object())

    await persistence._commit_bundle(
        trace={"trace_id": "t-2"},
        events=[],
        evals=[],
    )

    assert embedder.calls == []
    assert _bg._pending_task_count() == 0


@pytest.mark.asyncio
async def test_commit_bundle_passes_events_through_to_embedder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _FakeStore()
    embedder = _SpyEmbedder(enabled=True)
    monkeypatch.setattr(persistence, "STORE", store)
    monkeypatch.setattr(persistence, "get_eval_embedder", lambda: embedder)
    monkeypatch.setattr(persistence, "get_shared_pool", lambda: object())

    events = [{"event_type": "tool_start", "name": "search_knowledge_base"}]
    await persistence._commit_bundle(
        trace={"trace_id": "t-3"},
        events=events,
        evals=[],
    )

    for task in list(_bg._BG_TASKS):
        await task

    _, _, passed_events = embedder.calls[0]
    assert passed_events == events


@pytest.mark.asyncio
async def test_schedule_releases_task_reference_on_completion() -> None:
    async def _noop() -> None:
        return None

    task = _bg.schedule(_noop())
    await task
    # Give the done-callback a tick to run (it's already scheduled by
    # asyncio.Task, but on some loop configs the callback runs after
    # the next yield point).
    import asyncio

    await asyncio.sleep(0)
    assert task not in _bg._BG_TASKS
    assert _bg._pending_task_count() == 0
