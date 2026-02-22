from __future__ import annotations

import json

import pytest

from src.agent_service.api.endpoints import live_dashboards


class _FakePubSub:
    def __init__(self, messages: list[dict] | None = None):
        self._messages = list(messages or [])
        self.closed = False
        self.unsubscribed = False

    async def subscribe(self, *channels):
        self.channels = channels

    async def get_message(self, ignore_subscribe_messages=True, timeout=1.0):
        if self._messages:
            return self._messages.pop(0)
        return None

    async def unsubscribe(self, *channels):
        self.unsubscribed = True

    async def close(self):
        self.closed = True


class _FakeRedis:
    def __init__(self, pubsub: _FakePubSub):
        self._pubsub = pubsub

    def pubsub(self):
        return self._pubsub


class _FakeRequest:
    def __init__(self, disconnect_after_checks: int):
        self._checks = 0
        self._disconnect_after_checks = disconnect_after_checks
        self.scope = {}

    async def is_disconnected(self):
        self._checks += 1
        return self._checks > self._disconnect_after_checks


async def _collect_chunks(response, limit: int = 8) -> list[object]:
    chunks: list[object] = []
    iterator = response.body_iterator
    for _ in range(limit):
        try:
            chunk = await anext(iterator)
        except StopAsyncIteration:
            break
        chunks.append(chunk)
    return chunks


@pytest.mark.asyncio
async def test_global_dashboard_feed_configures_ping_and_cleans_pubsub(monkeypatch):
    pubsub = _FakePubSub(messages=[])

    async def _fake_get_client():
        return _FakeRedis(pubsub)

    monkeypatch.setattr(live_dashboards.event_bus, "_get_client", _fake_get_client)

    response = await live_dashboards.global_dashboard_feed(_FakeRequest(disconnect_after_checks=3))
    assert response._ping_interval == live_dashboards.HEARTBEAT_INTERVAL_SECONDS  # noqa: SLF001
    assert response.send_timeout == live_dashboards.SSE_SEND_TIMEOUT_SECONDS

    chunks = await _collect_chunks(response)
    assert any(
        chunk == {"event": "connected", "data": "global_feed_established"} for chunk in chunks
    )

    assert pubsub.closed is True


@pytest.mark.asyncio
async def test_session_feed_configures_ping_and_cleans_pubsub(monkeypatch):
    payload = {"event": "update", "data": {"ok": True}}
    pubsub = _FakePubSub(messages=[{"type": "message", "data": json.dumps(payload)}])

    async def _fake_get_client():
        return _FakeRedis(pubsub)

    monkeypatch.setattr(live_dashboards.event_bus, "_get_client", _fake_get_client)

    response = await live_dashboards.session_specific_feed(
        "sess-123", _FakeRequest(disconnect_after_checks=4)
    )
    assert response._ping_interval == live_dashboards.HEARTBEAT_INTERVAL_SECONDS  # noqa: SLF001
    assert response.send_timeout == live_dashboards.SSE_SEND_TIMEOUT_SECONDS

    chunks = await _collect_chunks(response)
    assert any(chunk == {"event": "update", "data": '{"ok": true}'} for chunk in chunks)

    assert pubsub.unsubscribed is True
    assert pubsub.closed is True
