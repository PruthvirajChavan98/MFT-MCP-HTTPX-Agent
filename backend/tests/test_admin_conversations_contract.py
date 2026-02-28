from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.agent_service.api import admin_analytics


@pytest.mark.asyncio
async def test_conversations_cursor_contract_returns_next_cursor(monkeypatch):
    monkeypatch.setattr(admin_analytics, "ADMIN_CURSOR_APIS_V2", True)

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

    async def _fake_read(_query: str, params: dict[str, object]):
        assert params["search"] == "loan"
        assert params["limit_plus_one"] == 3
        return rows

    monkeypatch.setattr(admin_analytics, "_neo4j_read", _fake_read)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))

    response = await admin_analytics.conversations(
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

    async def _fake_read(_query: str, params: dict[str, object]):
        assert params["limit_plus_one"] == 3
        assert params["search"] == "q"
        return rows

    monkeypatch.setattr(admin_analytics, "_neo4j_read", _fake_read)
    response = await admin_analytics.traces(
        limit=2, cursor=None, search="q", status=None, model=None
    )

    assert response["count"] == 2
    assert response["next_cursor"]
    assert response["items"][0]["trace_id"] == "trace-3"


@pytest.mark.asyncio
async def test_session_traces_returns_additive_assistant_metadata(monkeypatch):
    assistant = SimpleNamespace(
        type="ai",
        content="Answer text",
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

    response = await admin_analytics.session_traces(
        request=request, session_id="session-1", limit=50
    )
    assistant_row = next(item for item in response["items"] if item["role"] == "assistant")

    assert assistant_row["traceId"] == "trace-123"
    assert assistant_row["followUps"] == ["Follow-up one", "Follow-up two"]
    assert assistant_row["provider"] == "openrouter"
    assert assistant_row["model"] == "deepseek/deepseek-v3.2"
    assert assistant_row["totalTokens"] == 88
    assert assistant_row["cost"]["total_cost"] == 0.00042


@pytest.mark.asyncio
async def test_session_traces_reconstructs_from_eval_trace_when_checkpoint_missing(monkeypatch):
    class _FakeCheckpointer:
        async def aget_tuple(self, _config):
            return None

    async def _fake_read(_query: str, _params: dict[str, object]):
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

    monkeypatch.setattr(admin_analytics, "_neo4j_read", _fake_read)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(checkpointer=_FakeCheckpointer()))
    )

    response = await admin_analytics.session_traces(
        request=request, session_id="session-1", limit=50
    )
    assert len(response["items"]) == 2
    assert response["items"][0]["role"] == "user"
    assert response["items"][1]["role"] == "assistant"
    assert response["items"][1]["traceId"] == "trace-xyz"
