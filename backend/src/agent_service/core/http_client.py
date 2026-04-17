from __future__ import annotations

import asyncio
import logging

import httpx

from src.agent_service.core.config import (
    SHARED_HTTP_MAX_CONNECTIONS,
    SHARED_HTTP_MAX_KEEPALIVE,
    SHARED_HTTP_TIMEOUT_CONNECT_SECONDS,
    SHARED_HTTP_TIMEOUT_POOL_SECONDS,
    SHARED_HTTP_TIMEOUT_READ_SECONDS,
    SHARED_HTTP_TIMEOUT_WRITE_SECONDS,
)

log = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None
_client_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    """Lazy-init the module-level lock.

    Creating asyncio.Lock() at module-import time (the old pattern) binds it to
    whatever loop is current at that moment — which is often no loop at all
    when this file is imported from a sync test harness before the pytest-asyncio
    loop is up. Lazy creation on first use avoids the stale-loop bug class
    (RuntimeError: Task got Future attached to a different loop).
    """
    global _client_lock
    if _client_lock is None:
        _client_lock = asyncio.Lock()
    return _client_lock


def _build_http_client() -> httpx.AsyncClient:
    timeout = httpx.Timeout(
        connect=SHARED_HTTP_TIMEOUT_CONNECT_SECONDS,
        read=SHARED_HTTP_TIMEOUT_READ_SECONDS,
        write=SHARED_HTTP_TIMEOUT_WRITE_SECONDS,
        pool=SHARED_HTTP_TIMEOUT_POOL_SECONDS,
    )
    limits = httpx.Limits(
        max_connections=SHARED_HTTP_MAX_CONNECTIONS,
        max_keepalive_connections=SHARED_HTTP_MAX_KEEPALIVE,
    )
    return httpx.AsyncClient(timeout=timeout, limits=limits)


async def initialize_http_client() -> httpx.AsyncClient:
    global _client
    if _client is not None:
        return _client

    async with _get_lock():
        if _client is None:
            _client = _build_http_client()
            log.info(
                "Initialized shared http client (max_connections=%s, max_keepalive=%s)",
                SHARED_HTTP_MAX_CONNECTIONS,
                SHARED_HTTP_MAX_KEEPALIVE,
            )
    return _client


async def get_http_client() -> httpx.AsyncClient:
    return await initialize_http_client()


async def close_http_client() -> None:
    global _client
    async with _get_lock():
        if _client is not None:
            await _client.aclose()
            _client = None
            log.info("Closed shared http client")
