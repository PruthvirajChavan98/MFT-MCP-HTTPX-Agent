from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src.agent_service.api import admin_analytics


class _FakeConn:
    def __init__(self):
        self.executed: list[tuple[str, tuple]] = []

    async def execute(self, query: str, *args):
        self.executed.append((query, args))

    async def fetchrow(self, query: str, *args):
        if "FROM security.session_ip_events" in query:
            return {"total": 2}
        return {"total_events": 2, "avg_risk_score": 0.62, "deny_events": 1}

    async def fetch(self, query: str, *args):
        if "GROUP BY bucket" in query:
            return [
                {
                    "bucket": datetime(2026, 1, 1, 10, tzinfo=timezone.utc),
                    "total_events": 3,
                    "deny_events": 1,
                    "avg_risk_score": 0.5,
                }
            ]
        return [
            {
                "event_time": datetime(2026, 1, 1, 10, tzinfo=timezone.utc),
                "session_id": "s-1",
                "risk_score": 0.8,
                "risk_decision": "deny",
                "request_path": "/agent/stream",
                "risk_reasons": ["anomaly"],
            },
            {
                "event_time": datetime(2026, 1, 1, 11, tzinfo=timezone.utc),
                "session_id": "s-2",
                "risk_score": 0.2,
                "risk_decision": "allow",
                "request_path": "/health/ready",
                "risk_reasons": [],
            },
        ]

    def transaction(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakePool:
    def __init__(self):
        self.conn = _FakeConn()

    def acquire(self):
        return self.conn


@pytest.mark.asyncio
async def test_guardrails_events_support_filters_and_pagination():
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(postgres_pool=SimpleNamespace(pool=_FakePool())))
    )
    response = await admin_analytics.guardrails(
        request=request,
        tenant_id="tenant-a",
        decision="deny",
        min_risk=0.4,
        session_id=None,
        start=None,
        end=None,
        offset=0,
        limit=25,
    )

    assert response["total"] == 2
    assert response["count"] == 2
    assert response["items"][0]["severity"] == "critical"


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

    monkeypatch.setattr(admin_analytics, "get_redis", _fake_get_redis)
    monkeypatch.setattr(admin_analytics, "SHADOW_TRACE_QUEUE_KEY", "agent:shadow:test")

    response = await admin_analytics.guardrails_queue_health()
    assert response["depth"] == 4
    assert response["queue_key"] == "agent:shadow:test"
    assert response["oldest_age_seconds"] is not None


@pytest.mark.asyncio
async def test_guardrails_judge_summary_returns_aggregates(monkeypatch):
    async def _fake_neo4j_read(query: str, params: dict[str, object]):
        if "count(e) AS total_evals" in query:
            return [
                {
                    "total_evals": 5,
                    "avg_helpfulness": 0.8,
                    "avg_faithfulness": 0.7,
                    "avg_policy_adherence": 0.9,
                }
            ]
        return [
            {
                "trace_id": "trace-1",
                "session_id": "session-1",
                "model": "model-a",
                "summary": "Needs improvement",
                "helpfulness": 0.2,
                "faithfulness": 0.4,
                "policy_adherence": 0.3,
                "evaluated_at": "2026-01-01T10:00:00Z",
            }
        ]

    monkeypatch.setattr(admin_analytics, "_neo4j_read", _fake_neo4j_read)
    response = await admin_analytics.guardrails_judge_summary(limit_failures=5)

    assert response["total_evals"] == 5
    assert len(response["recent_failures"]) == 1
