from __future__ import annotations

import httpx
import pytest

from src.agent_service.worker.shadow_judge_worker import ShadowJudgeWorker


class _FakeQueue:
    def __init__(self, items: list[dict]):
        self.items = list(items)
        self.failed_batches: list[tuple[list[dict], str]] = []

    async def pop_batch(self, *, limit: int):
        if not self.items:
            return []
        batch = self.items[:limit]
        self.items = self.items[limit:]
        return batch

    async def requeue_or_dead_letter_batch(self, items: list[dict], *, reason: str):
        self.failed_batches.append((items, reason))
        return (len(items), 0)


@pytest.mark.asyncio
async def test_shadow_worker_process_once_persists_rows(monkeypatch):
    queue = _FakeQueue(
        [
            {
                "trace_id": "trace-1",
                "session_id": "session-1",
                "user_prompt": "hello",
                "agent_response": "world",
            }
        ]
    )
    worker = ShadowJudgeWorker(queue=queue)
    persisted_rows: list[dict] = []

    async def _fake_eval(batch):
        return [
            {
                "eval_id": "eval-1",
                "evaluated_at": "2026-01-01T00:00:00Z",
                "trace_id": "trace-1",
                "session_id": "session-1",
                "helpfulness": 1.0,
                "faithfulness": 1.0,
                "policy_adherence": 1.0,
                "summary": "ok",
                "model": "model-a",
            }
        ]

    async def _fake_persist(rows):
        persisted_rows.extend(rows)

    monkeypatch.setattr(worker, "_evaluate_batch", _fake_eval)
    monkeypatch.setattr(worker, "_persist_rows", _fake_persist)

    processed = await worker.process_once()
    assert processed == 1
    assert len(persisted_rows) == 1
    assert persisted_rows[0]["trace_id"] == "trace-1"


@pytest.mark.asyncio
async def test_shadow_worker_uses_fallback_model_on_primary_failure(monkeypatch):
    worker = ShadowJudgeWorker(queue=_FakeQueue([]))
    calls: list[str] = []

    async def _fake_call(batch, model):
        calls.append(model)
        if len(calls) == 1:
            raise RuntimeError("primary failed")
        return [{"trace_id": "trace-1"}]

    monkeypatch.setattr(worker, "_call_groq", _fake_call)
    result = await worker._evaluate_batch([{"trace_id": "trace-1"}])  # noqa: SLF001

    assert len(result) == 1
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_shadow_worker_requeues_failed_batches(monkeypatch):
    queue = _FakeQueue(
        [
            {
                "trace_id": "trace-fail",
                "session_id": "session-fail",
                "user_prompt": "hello",
                "agent_response": "world",
            }
        ]
    )
    worker = ShadowJudgeWorker(queue=queue)

    async def _fake_eval(_batch):
        raise RuntimeError("judge failure")

    monkeypatch.setattr(worker, "_evaluate_batch", _fake_eval)

    with pytest.raises(RuntimeError, match="judge failure"):
        await worker.process_once()

    assert len(queue.failed_batches) == 1
    failed_items, reason = queue.failed_batches[0]
    assert failed_items[0]["trace_id"] == "trace-fail"
    assert "judge failure" in reason


@pytest.mark.asyncio
async def test_shadow_worker_persists_default_rows_on_non_retryable_4xx(monkeypatch):
    worker = ShadowJudgeWorker(queue=_FakeQueue([]))
    calls = 0

    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(status_code=400, request=request)
    status_error = httpx.HTTPStatusError("400 Bad Request", request=request, response=response)

    async def _fake_call(_batch, model):
        nonlocal calls
        if calls == 0:
            calls += 1
            raise RuntimeError("primary failed")
        raise status_error

    monkeypatch.setattr(worker, "_call_groq", _fake_call)

    rows = await worker._evaluate_batch(  # noqa: SLF001
        [{"trace_id": "trace-4xx", "session_id": "session-4xx"}]
    )

    assert len(rows) == 1
    assert rows[0]["trace_id"] == "trace-4xx"
    assert rows[0]["policy_adherence"] == 0.0
    assert "default evaluation recorded" in rows[0]["summary"]
