from __future__ import annotations

import pytest

from src.agent_service.api.endpoints import health
from src.agent_service.security import metrics as security_metrics


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_404_when_disabled(monkeypatch):
    monkeypatch.setattr(health, "PROMETHEUS_METRICS_ENABLED", False)
    response = await health.metrics()
    assert response.status_code == 404
    assert response.body == b"metrics disabled"


@pytest.mark.asyncio
async def test_metrics_endpoint_uses_exporter_when_enabled(monkeypatch):
    monkeypatch.setattr(health, "PROMETHEUS_METRICS_ENABLED", True)
    monkeypatch.setattr(
        health, "export_prometheus_metrics", lambda: (b"mock_metrics", "text/plain")
    )

    response = await health.metrics()
    assert response.status_code == 200
    assert response.body == b"mock_metrics"
    assert response.headers["content-type"].startswith("text/plain")


def test_export_prometheus_metrics_uses_multiprocess_collector(monkeypatch):
    calls = {"collector": 0}

    def _collector(registry):
        calls["collector"] += 1

    monkeypatch.setattr(security_metrics, "PROMETHEUS_MULTIPROC_DIR", "/tmp/prometheus_multiproc")
    monkeypatch.setattr(security_metrics.multiprocess, "MultiProcessCollector", _collector)

    payload, content_type = security_metrics.export_prometheus_metrics()
    assert isinstance(payload, bytes)
    assert content_type.startswith("text/plain")
    assert calls["collector"] == 1


def test_normalize_path_for_metrics_prefers_route_template():
    assert (
        security_metrics.normalize_path_for_metrics(
            "/agent/config/550e8400-e29b-41d4-a716-446655440000",
            route_path="/agent/config/{session_id}",
        )
        == "/agent/config/{session_id}"
    )


def test_normalize_path_for_metrics_bounds_unmatched_and_dynamic_paths():
    assert (
        security_metrics.normalize_path_for_metrics("/totally-random/scanner/probe")
        == "/unmatched_route"
    )
    assert (
        security_metrics.normalize_path_for_metrics(
            "/agent/config/550e8400-e29b-41d4-a716-446655440000"
        )
        == "/agent/config/{id}"
    )
