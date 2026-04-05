from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import src.agent_service.api.admin_analytics.guardrails as guardrails_mod
import src.agent_service.api.admin_analytics.repo as repo_mod


@pytest.mark.asyncio
async def test_guardrails_events_support_filters_and_pagination():
    now = datetime.now(timezone.utc)
    rows = [
        {
            "trace_id": "trace-deny",
            "session_id": "s-1",
            "endpoint": "/agent/stream",
            "started_at": now.isoformat(),
            "meta_json": "{}",
            "inline_guard_decision": "block",
            "inline_guard_reason_code": "unsafe_signal",
            "inline_guard_risk_score": 0.9,
        },
        {
            "trace_id": "trace-allow",
            "session_id": "s-2",
            "endpoint": "/agent/stream",
            "started_at": now.isoformat(),
            "meta_json": "{}",
            "inline_guard_decision": "allow",
            "inline_guard_reason_code": "safe",
            "inline_guard_risk_score": 0.1,
        },
    ]

    async def _fake_rows(pool, **kwargs):
        return rows

    fake_pool = SimpleNamespace()  # pool unused because fetch_guardrail_trace_rows is patched
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pool=fake_pool)))
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(repo_mod.analytics_repo, "fetch_guardrail_trace_rows", _fake_rows)
    response = await guardrails_mod.guardrails(
        request=request,
        tenant_id="tenant-a",
        decision="block",
        min_risk=0.4,
        session_id=None,
        start=None,
        end=None,
        offset=0,
        limit=25,
    )
    monkeypatch.undo()

    assert response["total"] == 1
    assert response["count"] == 1
    assert response["items"][0]["trace_id"] == "trace-deny"
    assert response["items"][0]["severity"] == "critical"


@pytest.mark.asyncio
async def test_guardrails_trends_accepts_integer_hours():
    now = datetime.now(timezone.utc)
    rows = [
        {
            "trace_id": "trace-1",
            "session_id": "s-1",
            "endpoint": "/agent/stream",
            "started_at": now.isoformat(),
            "meta_json": "{}",
            "inline_guard_decision": "allow",
            "inline_guard_reason_code": "safe",
            "inline_guard_risk_score": 0.1,
        },
        {
            "trace_id": "trace-2",
            "session_id": "s-2",
            "endpoint": "/agent/stream",
            "started_at": now.isoformat(),
            "meta_json": "{}",
            "inline_guard_decision": "block",
            "inline_guard_reason_code": "unsafe_signal",
            "inline_guard_risk_score": 0.8,
        },
    ]

    captured: dict[str, object] = {}

    async def _fake_rows(pool, **kwargs):
        captured.update(kwargs)
        return rows

    fake_pool = SimpleNamespace()  # pool unused because fetch_guardrail_trace_rows is patched
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pool=fake_pool)))
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(repo_mod.analytics_repo, "fetch_guardrail_trace_rows", _fake_rows)

    response = await guardrails_mod.guardrails_trends(
        request=request,
        tenant_id="tenant-a",
        hours=24,
    )
    monkeypatch.undo()

    assert response["hours"] == 24
    assert response["items"][0]["total_events"] >= 1
    assert captured["tenant_id"] == "tenant-a"
    assert isinstance(captured["start"], datetime)


@pytest.mark.asyncio
async def test_guardrails_trends_returns_503_when_db_query_fails():
    async def _raise(pool, **kwargs):
        raise RuntimeError("db unavailable")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(repo_mod.analytics_repo, "fetch_guardrail_trace_rows", _raise)

    fake_pool = SimpleNamespace()  # pool unused because fetch_guardrail_trace_rows is patched
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pool=fake_pool)))

    with pytest.raises(HTTPException) as exc_info:
        await guardrails_mod.guardrails_trends(
            request=request,
            tenant_id="tenant-a",
            hours=24,
        )
    monkeypatch.undo()

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Guardrail analytics unavailable"


@pytest.mark.asyncio
async def test_guardrails_queue_health_reports_depth_and_oldest_age(monkeypatch):
    class _FakeRedis:
        async def llen(self, key: str):
            return 4

        async def lindex(self, key: str, idx: int):
            return json.dumps(
                {"enqueued_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
            )

    async def _fake_get_redis():
        return _FakeRedis()

    monkeypatch.setattr(guardrails_mod, "get_redis", _fake_get_redis)
    monkeypatch.setattr(guardrails_mod, "SHADOW_TRACE_QUEUE_KEY", "agent:shadow:test")

    response = await guardrails_mod.guardrails_queue_health()
    assert response["depth"] == 4
    assert response["queue_key"] == "agent:shadow:test"
    assert response["oldest_age_seconds"] is not None


@pytest.mark.asyncio
async def test_guardrails_judge_summary_returns_aggregates():
    aggregate_row = {
        "total_evals": 5,
        "avg_helpfulness": 0.8,
        "avg_faithfulness": 0.7,
        "avg_policy_adherence": 0.9,
    }
    failure_row = {
        "trace_id": "trace-1",
        "session_id": "session-1",
        "model": "model-a",
        "summary": "Needs improvement",
        "helpfulness": 0.2,
        "faithfulness": 0.4,
        "policy_adherence": 0.3,
        "evaluated_at": "2026-01-01T10:00:00Z",
    }

    call_count = 0

    class _FakePoolJudge:
        async def fetch(self, query: str, *args):
            nonlocal call_count
            call_count += 1
            if "COUNT(*) AS total_evals" in query:
                return [aggregate_row]
            return [failure_row]

    fake_pool = _FakePoolJudge()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pool=fake_pool)))
    response = await guardrails_mod.guardrails_judge_summary(
        request=request,
        limit_failures=5,
    )

    assert response["total_evals"] == 5
    assert len(response["recent_failures"]) == 1
