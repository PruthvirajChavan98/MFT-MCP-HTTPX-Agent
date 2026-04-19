"""Integration-test scaffolding.

These tests are opt-in (``pytest -m integration``) and require a running
stack — MCP server on ``MCP_SERVER_URL`` (default ``http://localhost:8050/sse``),
Redis reachable via ``REDIS_URL``, and the mock CRM providing
``/mockfin-service/otp/{generate_new,validate_new}/``.

If either the MCP endpoint or Redis is unreachable at session start,
every test in this directory is skipped with a clear message — CI (which
doesn't boot the stack) stays green without gating changes.
"""

from __future__ import annotations

import os

import httpx
import pytest


def _mcp_url() -> str:
    return os.environ.get("MCP_SERVER_URL", "http://localhost:8050/sse")


def _is_reachable(url: str, timeout: float = 2.0) -> bool:
    """Probe the MCP SSE root with a short connect budget.

    SSE endpoints respond to GET with 200 + ``text/event-stream`` and
    then hold the connection open emitting server-sent events. A plain
    ``client.get(url)`` would wait for the body and ``ReadTimeout``
    before we see the status code. Using ``stream=True`` + closing
    immediately after headers arrive gives us a reliable 200/not-200
    signal within the connect budget.
    """
    try:
        with httpx.Client(timeout=timeout) as client:
            with client.stream("GET", url, headers={"Accept": "text/event-stream"}) as resp:
                return resp.status_code < 500
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout):
        return False


def pytest_collection_modifyitems(config: pytest.Config, items: list) -> None:  # type: ignore[override]
    """Add a skip marker to every integration test when the stack is down."""
    if not any("integration" in item.keywords for item in items):
        return
    url = _mcp_url()
    if _is_reachable(url):
        return
    skip_down = pytest.mark.skip(
        reason=f"MCP server not reachable at {url} — start with `make local-up`"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_down)
