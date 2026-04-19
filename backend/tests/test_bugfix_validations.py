from __future__ import annotations

import asyncio
import importlib
import sys
import warnings
from datetime import datetime
from types import SimpleNamespace

import pytest

from src.agent_service.api import eval_read
from src.agent_service.eval_store.pg_store import EvalPgStore
from src.agent_service.features import runtime_trace_store
from src.agent_service.features.knowledge_base import service as kb_service_module
from src.agent_service.features.knowledge_base.service import KnowledgeBaseService
from src.agent_service.features.shadow_eval import ShadowEvalCollector


class _FakeRequest:
    def __init__(self, pool):
        self.app = SimpleNamespace(state=SimpleNamespace(pool=pool))


class _EvalSearchPool:
    def __init__(self):
        self.fetchrow_calls: list[tuple[str, tuple[object, ...]]] = []
        self.fetch_calls: list[tuple[str, tuple[object, ...]]] = []

    async def fetchrow(self, query: str, *args):
        self.fetchrow_calls.append((query, args))
        return {"total": 3}

    async def fetch(self, query: str, *args):
        self.fetch_calls.append((query, args))
        return [
            {
                "trace_id": "trace-1",
                "case_id": "app-1",
                "session_id": "session-1",
                "provider": "openrouter",
                "model": "model-1",
                "endpoint": "/eval",
                "started_at": "2026-04-02T00:00:00Z",
                "ended_at": "2026-04-02T00:00:01Z",
                "latency_ms": 1000,
                "status": "success",
                "error": None,
                "event_count": 2,
                "eval_count": 1,
                "pass_count": 1,
                "scores": '[{"name":"faithfulness","score":0.9,"passed":true}]',
            }
        ]


class _VectorSearchPool:
    def __init__(self):
        self.fetch_calls: list[tuple[str, tuple[object, ...]]] = []

    async def fetch(self, query: str, *args):
        self.fetch_calls.append((query, args))
        return [
            {
                "trace_id": "trace-1",
                "inputs_json": {"question": "how do i close my loan"},
                "final_output": "closure details",
                "provider": "openrouter",
                "model": "model-1",
                "session_id": "session-1",
                "case_id": "app-1",
                "status": "success",
                "started_at": "2026-04-02T00:00:00Z",
            }
        ]


class _VectorStore:
    def __init__(self):
        self.by_vector_calls: list[tuple[list[float], dict[str, object]]] = []
        self.by_text_calls: list[tuple[str, dict[str, object]]] = []

    async def asimilarity_search_with_score_by_vector(self, vector: list[float], **kwargs):
        self.by_vector_calls.append((vector, kwargs))
        return [(SimpleNamespace(metadata={"trace_id": "trace-1"}), 0.91)]

    async def asimilarity_search_with_score(self, query: str, **kwargs):
        self.by_text_calls.append((query, kwargs))
        raise AssertionError("text-based search should not be used when req.vector is provided")


class _TextVectorStore(_VectorStore):
    async def asimilarity_search_with_score(self, query: str, **kwargs):
        self.by_text_calls.append((query, kwargs))
        return [(SimpleNamespace(metadata={"trace_id": "trace-1"}), 0.88)]


class _RecordingPgPool:
    def __init__(self):
        self.execute_calls: list[tuple[str, tuple[object, ...]]] = []
        self.executemany_calls: list[tuple[str, list[tuple[object, ...]]]] = []

    async def execute(self, query: str, *args):
        self.execute_calls.append((query, args))
        return "OK"

    async def executemany(self, query: str, rows):
        copied_rows = list(rows)
        self.executemany_calls.append((query, copied_rows))
        return "OK"


@pytest.mark.asyncio
async def test_eval_search_uses_asyncpg_positional_having_params_and_correct_count_query():
    pool = _EvalSearchPool()

    result = await eval_read.eval_search(
        request=_FakeRequest(pool),
        limit=20,
        offset=10,
        metric_name="faithfulness",
        passed=True,
        min_score=0.7,
    )

    assert result["total"] == 3
    count_query, count_args = pool.fetchrow_calls[0]
    assert "%(" not in count_query
    assert "SELECT COUNT(*) AS total FROM (" in count_query
    assert "bool_or(r.metric_name = $6)" in count_query
    assert "bool_or(r.passed = $7)" in count_query
    assert "bool_or(r.score >= $8)" in count_query
    assert count_args == (None, None, None, None, None, "faithfulness", True, 0.7)

    main_query, main_args = pool.fetch_calls[0]
    assert "%(" not in main_query
    assert "OFFSET $9 LIMIT $10" in main_query
    assert main_args == (None, None, None, None, None, "faithfulness", True, 0.7, 10, 20)


@pytest.mark.asyncio
async def test_eval_vector_search_uses_req_vector_path(monkeypatch):
    pool = _VectorSearchPool()
    calls: list[dict[str, object]] = []

    async def _fake_search_raw(**kwargs):
        calls.append(kwargs)
        return [(SimpleNamespace(metadata={"trace_id": "trace-1"}), 0.91)]

    monkeypatch.setattr(eval_read.milvus_mgr, "semantic_search_raw", _fake_search_raw)

    result = await eval_read.eval_vector_search(
        request=_FakeRequest(pool),
        req=eval_read.VectorSearchRequest(kind="trace", vector=[0.1, 0.2], k=2),
        x_openrouter_key=None,
    )

    assert len(calls) == 1
    assert calls[0]["collection"] == "eval_traces_emb"
    assert calls[0]["query_vector"] == [0.1, 0.2]
    assert calls[0]["limit"] == 2
    assert calls[0].get("query", "") == ""  # vector path — no text query
    assert result["items"][0]["trace_id"] == "trace-1"
    assert result["items"][0]["question"] == "how do i close my loan"


@pytest.mark.asyncio
async def test_eval_vector_search_text_path_no_longer_requires_request_openrouter_key(monkeypatch):
    pool = _VectorSearchPool()
    calls: list[dict[str, object]] = []

    async def _fake_search_raw(**kwargs):
        calls.append(kwargs)
        return [(SimpleNamespace(metadata={"trace_id": "trace-1"}), 0.88)]

    monkeypatch.setattr(eval_read.milvus_mgr, "semantic_search_raw", _fake_search_raw)

    result = await eval_read.eval_vector_search(
        request=_FakeRequest(pool),
        req=eval_read.VectorSearchRequest(kind="trace", text="loan closure", k=2),
        x_openrouter_key=None,
    )

    assert len(calls) == 1
    assert calls[0]["collection"] == "eval_traces_emb"
    assert calls[0]["query"] == "loan closure"
    assert calls[0]["limit"] == 2
    assert calls[0].get("query_vector") is None
    assert result["items"][0]["trace_id"] == "trace-1"


@pytest.mark.asyncio
async def test_update_faq_awaits_milvus_sync(monkeypatch):
    service = KnowledgeBaseService()
    call_order: list[str] = []

    async def _update_one(*args, **kwargs):
        call_order.append("update")
        return True

    async def _dump_all(*args, **kwargs):
        call_order.append("dump")
        return [{"question": "Q", "answer": "A"}]

    async def _sync_to_milvus(*args, **kwargs):
        await asyncio.sleep(0)
        call_order.append("sync")

    monkeypatch.setattr(service.repo, "update_one", _update_one)
    monkeypatch.setattr(service.repo, "dump_all", _dump_all)
    monkeypatch.setattr(service, "_sync_to_milvus", _sync_to_milvus)

    updated = await service.update_faq(
        object(),
        faq_id="faq-1",
        original_question=None,
        new_question="Q2",
        new_answer="A2",
        new_category="Billing",
        new_tags=["billing"],
    )

    assert updated is True
    assert call_order == ["update", "dump", "sync"]


@pytest.mark.asyncio
async def test_delete_faq_awaits_milvus_sync(monkeypatch):
    service = KnowledgeBaseService()
    call_order: list[str] = []

    async def _delete_one(*args, **kwargs):
        call_order.append("delete")
        return 1

    async def _dump_all(*args, **kwargs):
        call_order.append("dump")
        return [{"question": "Q", "answer": "A"}]

    async def _sync_to_milvus(*args, **kwargs):
        await asyncio.sleep(0)
        call_order.append("sync")

    monkeypatch.setattr(service.repo, "delete_one", _delete_one)
    monkeypatch.setattr(service.repo, "dump_all", _dump_all)
    monkeypatch.setattr(service, "_sync_to_milvus", _sync_to_milvus)

    deleted = await service.delete_faq(object(), faq_id="faq-1", question=None)

    assert deleted == 1
    assert call_order == ["delete", "dump", "sync"]


@pytest.mark.asyncio
async def test_semantic_delete_does_not_fallback_to_substring(monkeypatch):
    service = KnowledgeBaseService()

    async def _semantic_search(*args, **kwargs):
        raise RuntimeError("Milvus unavailable")

    async def _dump_all(*args, **kwargs):
        raise AssertionError("substring fallback should not run")

    monkeypatch.setattr(kb_service_module.kb_milvus_store, "semantic_search", _semantic_search)
    monkeypatch.setattr(service.repo, "dump_all", _dump_all)

    with pytest.raises(RuntimeError, match="Milvus semantic delete search failed"):
        await service.semantic_delete(object(), query="loan", threshold=0.9)


def test_ragas_judge_import_path_emits_no_deprecation_warning():
    module_name = "src.agent_service.eval_store.ragas_judge"
    existing = sys.modules.get(module_name)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        if existing is None:
            module = importlib.import_module(module_name)
        else:
            module = importlib.reload(existing)

    assert module is not None
    deprecation_messages = [
        str(item.message) for item in caught if issubclass(item.category, DeprecationWarning)
    ]
    assert not any("AnswerRelevancy" in msg for msg in deprecation_messages)
    assert not any("ContextRelevance" in msg for msg in deprecation_messages)
    assert not any("Faithfulness" in msg for msg in deprecation_messages)


@pytest.mark.asyncio
async def test_pg_store_upsert_trace_normalizes_iso_timestamp_strings():
    pool = _RecordingPgPool()
    store = EvalPgStore()

    await store.upsert_trace(
        pool,
        {
            "trace_id": "trace-1",
            "started_at": "2026-04-02T00:00:00Z",
            "ended_at": "2026-04-02T00:00:01Z",
            "inputs": {"question": "hello"},
            "tags": {},
            "meta": {},
        },
    )

    _, args = pool.execute_calls[0]
    assert isinstance(args[6], datetime)
    assert isinstance(args[7], datetime)
    assert args[6].tzinfo is not None
    assert args[7].tzinfo is not None


@pytest.mark.asyncio
async def test_runtime_trace_persistence_normalizes_collector_timestamps(monkeypatch):
    pool = _RecordingPgPool()
    collector = ShadowEvalCollector(
        session_id="session-1",
        question="i want to hack you",
        provider="openrouter",
        model="model-1",
        endpoint="/agent/stream",
        system_prompt="system",
        tool_definitions="",
    )
    collector.set_inline_guard_decision(
        {
            "allow": False,
            "decision": "block",
            "reason_code": "unsafe_signal",
            "risk_score": 0.95,
            "checks": [],
        }
    )
    collector.on_done("", "Prompt violates security policy")

    monkeypatch.setattr(runtime_trace_store, "get_shared_pool", lambda: pool)
    monkeypatch.setattr(
        runtime_trace_store,
        "classify_question_category",
        lambda question, router_reason: SimpleNamespace(
            category="fraud_and_security",
            confidence=0.9,
            source="test",
        ),
    )

    persisted = await runtime_trace_store.persist_runtime_trace(collector)

    assert persisted is True
    trace_query, trace_args = pool.execute_calls[0]
    assert "INSERT INTO eval_traces" in trace_query
    assert isinstance(trace_args[6], datetime)
    assert isinstance(trace_args[7], datetime)
    assert trace_args[18] == "block"
    assert trace_args[19] == "unsafe_signal"

    event_query, event_rows = pool.executemany_calls[0]
    assert "INSERT INTO eval_events" in event_query
    assert all(isinstance(row[3], datetime) for row in event_rows)
