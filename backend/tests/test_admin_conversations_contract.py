from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import src.agent_service.api.admin_analytics.conversations as conversations_mod
import src.agent_service.api.admin_analytics.traces as traces_mod


@pytest.mark.asyncio
async def test_conversations_cursor_contract_returns_next_cursor(monkeypatch):
    monkeypatch.setattr(conversations_mod, "ADMIN_CURSOR_APIS_V2", True)

    rows = [
        {
            "session_id": "s-3",
            "started_at": "2026-02-27T22:30:00Z",
            "message_count": 9,
            "model": "deepseek/deepseek-v3.2",
            "provider": "openrouter",
            "inputs_json": '{"question":"loan eligibility"}',
        },
        {
            "session_id": "s-2",
            "started_at": "2026-02-27T22:20:00Z",
            "message_count": 5,
            "model": "deepseek/deepseek-v3.2",
            "provider": "openrouter",
            "inputs_json": {"question": "foreclosure charges"},
        },
        {
            "session_id": "s-1",
            "started_at": "2026-02-27T22:10:00Z",
            "message_count": 3,
            "model": "deepseek/deepseek-v3.2",
            "provider": "openrouter",
            "inputs_json": '{"question":"upi mandate"}',
        },
    ]

    async def _fake_pg_rows(_pool, _query: str, *args):
        # args: search_pat, cursor_started_at, cursor_session_id, limit+1
        assert args[0] == "%loan%"  # search_pat
        assert args[3] == 3  # limit_plus_one
        return rows

    monkeypatch.setattr(conversations_mod, "_pg_rows", _fake_pg_rows)
    fake_pool = object()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pool=fake_pool)))

    response = await conversations_mod.conversations(
        request=request,
        limit=2,
        cursor=None,
        search="loan",
    )

    assert response["count"] == 2
    assert response["limit"] == 2
    assert response["next_cursor"]
    assert response["items"][0]["first_question"] == "loan eligibility"


@pytest.mark.asyncio
async def test_traces_cursor_contract_returns_next_cursor(monkeypatch):
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        {
            "trace_id": "trace-3",
            "case_id": "default",
            "session_id": "s-1",
            "provider": "openrouter",
            "model": "deepseek/deepseek-v3.2",
            "endpoint": "/agent/stream",
            "started_at": now,
            "ended_at": now,
            "latency_ms": 1200,
            "status": "success",
            "error": None,
            "inputs_json": '{"question":"q3"}',
            "final_output": "a3",
            "meta_json": "{}",
        },
        {
            "trace_id": "trace-2",
            "case_id": "default",
            "session_id": "s-1",
            "provider": "openrouter",
            "model": "deepseek/deepseek-v3.2",
            "endpoint": "/agent/stream",
            "started_at": now,
            "ended_at": now,
            "latency_ms": 1200,
            "status": "success",
            "error": None,
            "inputs_json": '{"question":"q2"}',
            "final_output": "a2",
            "meta_json": "{}",
        },
        {
            "trace_id": "trace-1",
            "case_id": "default",
            "session_id": "s-1",
            "provider": "openrouter",
            "model": "deepseek/deepseek-v3.2",
            "endpoint": "/agent/stream",
            "started_at": now,
            "ended_at": now,
            "latency_ms": 1200,
            "status": "error",
            "error": "boom",
            "inputs_json": '{"question":"q1"}',
            "final_output": "",
            "meta_json": "{}",
        },
    ]

    async def _fake_pg_rows(_pool, _query: str, *args):
        # args: normalized_status, normalized_model, search_pat,
        #       cursor_started_at, cursor_trace_id, limit+1
        assert args[2] == "%q%"  # search_pat
        assert args[5] == 3  # limit_plus_one
        return rows

    monkeypatch.setattr(traces_mod, "_pg_rows", _fake_pg_rows)
    fake_pool = object()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pool=fake_pool)))

    response = await traces_mod.traces(
        request=request, limit=2, cursor=None, search="q", status=None, model=None
    )

    assert response["count"] == 2
    assert response["next_cursor"]
    assert response["items"][0]["trace_id"] == "trace-3"


@pytest.mark.asyncio
async def test_session_traces_returns_additive_assistant_metadata(monkeypatch):
    assistant = SimpleNamespace(
        type="ai",
        content='Answer text\nFOLLOW_UPS:["Raw follow-up"]',
        additional_kwargs={
            "follow_ups": ["Follow-up one", "Follow-up two"],
            "trace_id": "trace-123",
            "provider": "openrouter",
            "model": "deepseek/deepseek-v3.2",
            "total_tokens": 88,
            "cost": {"total_cost": 0.00042, "currency": "USD"},
        },
        response_metadata={
            "created": 1700000000,
            "model_provider": "openrouter",
            "model_name": "deepseek/deepseek-v3.2",
        },
    )
    user = SimpleNamespace(
        type="human", content="Question text", additional_kwargs={}, response_metadata={}
    )
    checkpoint = {"channel_values": {"messages": [user, assistant]}}
    fake_ckp = SimpleNamespace(checkpoint=checkpoint)

    class _FakeCheckpointer:
        async def aget_tuple(self, _config):
            return fake_ckp

    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(checkpointer=_FakeCheckpointer()))
    )

    response = await traces_mod.session_traces(request=request, session_id="session-1", limit=50)
    assistant_row = next(item for item in response["items"] if item["role"] == "assistant")

    assert assistant_row["traceId"] == "trace-123"
    assert assistant_row["content"] == "Answer text"
    assert assistant_row["followUps"] == ["Follow-up one", "Follow-up two"]
    assert assistant_row["provider"] == "openrouter"
    assert assistant_row["model"] == "deepseek/deepseek-v3.2"
    assert assistant_row["totalTokens"] == 88
    assert assistant_row["cost"]["total_cost"] == 0.00042


@pytest.mark.asyncio
async def test_session_traces_omits_synthetic_trace_id_when_checkpoint_message_has_none():
    assistant = SimpleNamespace(
        type="ai",
        content="Answer text",
        additional_kwargs={},
        response_metadata={"created": 1700000000},
    )
    user = SimpleNamespace(
        type="human", content="Question text", additional_kwargs={}, response_metadata={}
    )
    checkpoint = {"channel_values": {"messages": [user, assistant]}}
    fake_ckp = SimpleNamespace(checkpoint=checkpoint)

    class _FakeCheckpointer:
        async def aget_tuple(self, _config):
            return fake_ckp

    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(checkpointer=_FakeCheckpointer()))
    )

    response = await traces_mod.session_traces(request=request, session_id="session-1", limit=50)
    assistant_row = next(item for item in response["items"] if item["role"] == "assistant")

    assert "traceId" not in assistant_row


@pytest.mark.asyncio
async def test_session_traces_adds_static_eval_status_for_assistant_messages(monkeypatch):
    assistant = SimpleNamespace(
        type="ai",
        content="Answer text",
        additional_kwargs={"trace_id": "trace-123"},
        response_metadata={"created": 1700000000},
    )
    user = SimpleNamespace(
        type="human", content="Question text", additional_kwargs={}, response_metadata={}
    )
    checkpoint = {"channel_values": {"messages": [user, assistant]}}
    fake_ckp = SimpleNamespace(checkpoint=checkpoint)

    class _FakeCheckpointer:
        async def aget_tuple(self, _config):
            return fake_ckp

    async def _fake_pg_rows(_pool, query: str, *args):
        trace_ids = args[0]
        assert trace_ids == ["trace-123"]
        if "FROM eval_traces" in query:
            return [
                {
                    "trace_id": "trace-123",
                    "meta_json": {},
                    "ended_at": "2026-04-04T10:00:00Z",
                    "updated_at": "2026-04-04T10:00:00Z",
                }
            ]
        if "FROM eval_results" in query:
            return [
                {
                    "trace_id": "trace-123",
                    "metric_name": "faithfulness",
                    "score": 0.95,
                    "passed": True,
                },
                {
                    "trace_id": "trace-123",
                    "metric_name": "groundedness",
                    "score": 0.22,
                    "passed": False,
                },
            ]
        if "FROM shadow_judge_evals" in query:
            return []
        raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr(traces_mod, "_pg_rows", _fake_pg_rows)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(checkpointer=_FakeCheckpointer(), pool=object()))
    )

    response = await traces_mod.session_traces(request=request, session_id="session-1", limit=50)
    assistant_row = next(item for item in response["items"] if item["role"] == "assistant")

    assert assistant_row["evalStatus"] == {
        "status": "complete",
        "reason": None,
        "passed": 1,
        "failed": 1,
        "shadowJudge": None,
    }


@pytest.mark.asyncio
async def test_session_traces_reconstructs_from_eval_trace_when_checkpoint_missing(monkeypatch):
    class _FakeCheckpointer:
        async def aget_tuple(self, _config):
            return None

    async def _fake_pg_rows(_pool, query: str, *args):
        if "WHERE session_id = $1" in query:
            return [
                {
                    "trace_id": "trace-xyz",
                    "started_at": "2026-02-27T22:18:36Z",
                    "inputs_json": '{"question":"use html span to say something in green"}',
                    "final_output": "This text is in green using HTML span!",
                    "status": "success",
                    "model": "deepseek/deepseek-v3.2",
                    "provider": "openrouter",
                    "meta_json": '{"inline_guard":{"reason_code":"infra_degraded"}}',
                }
            ]
        if "FROM eval_traces" in query:
            return [
                {
                    "trace_id": "trace-xyz",
                    "meta_json": '{"inline_guard":{"reason_code":"infra_degraded"}}',
                    "ended_at": "2026-02-27T22:18:36Z",
                    "updated_at": "2026-02-27T22:18:36Z",
                }
            ]
        if "FROM eval_results" in query or "FROM shadow_judge_evals" in query:
            return []
        raise AssertionError(f"Unexpected query: {query}")

    monkeypatch.setattr(traces_mod, "_pg_rows", _fake_pg_rows)
    fake_pool = object()
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(checkpointer=_FakeCheckpointer(), pool=fake_pool))
    )

    response = await traces_mod.session_traces(request=request, session_id="session-1", limit=50)
    assert len(response["items"]) == 2
    assert response["items"][0]["role"] == "user"
    assert response["items"][1]["role"] == "assistant"
    assert response["items"][1]["traceId"] == "trace-xyz"


@pytest.mark.asyncio
async def test_session_traces_derives_follow_ups_from_checkpoint_content_when_missing_metadata():
    assistant = SimpleNamespace(
        type="ai",
        content='Answer text\nFOLLOW_UPS:["Follow-up one","Follow-up two"]',
        additional_kwargs={},
        response_metadata={"created": 1700000000},
    )
    user = SimpleNamespace(
        type="human", content="Question text", additional_kwargs={}, response_metadata={}
    )
    checkpoint = {"channel_values": {"messages": [user, assistant]}}
    fake_ckp = SimpleNamespace(checkpoint=checkpoint)

    class _FakeCheckpointer:
        async def aget_tuple(self, _config):
            return fake_ckp

    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(checkpointer=_FakeCheckpointer()))
    )

    response = await traces_mod.session_traces(request=request, session_id="session-1", limit=50)
    assistant_row = next(item for item in response["items"] if item["role"] == "assistant")

    assert assistant_row["content"] == "Answer text"
    assert assistant_row["followUps"] == ["Follow-up one", "Follow-up two"]


@pytest.mark.asyncio
async def test_checkpoint_trace_detail_strips_raw_follow_up_suffix():
    assistant = SimpleNamespace(
        type="ai",
        content='Answer text\nFOLLOW_UPS:["Follow-up one","Follow-up two"]',
        additional_kwargs={"trace_id": "trace-123"},
        response_metadata={
            "created": 1700000000,
            "model_provider": "openrouter",
            "model_name": "deepseek/deepseek-v3.2",
        },
    )
    user = SimpleNamespace(
        type="human", content="Question text", additional_kwargs={}, response_metadata={}
    )
    checkpoint = {"channel_values": {"messages": [user, assistant]}}
    fake_ckp = SimpleNamespace(checkpoint=checkpoint)

    class _FakeCheckpointer:
        async def aget_tuple(self, _config):
            return fake_ckp

    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(checkpointer=_FakeCheckpointer()))
    )

    detail = await traces_mod._checkpoint_trace_detail(request, "session-1~2")

    assert detail["trace"]["final_output"] == "Answer text"
    assert detail["events"][-1]["event_type"] == "token"
    assert detail["events"][-1]["text"] == "Answer text"
