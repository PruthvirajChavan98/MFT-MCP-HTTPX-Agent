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
_client_lock = asyncio.Lock()


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

    async with _client_lock:
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
    async with _client_lock:
        if _client is not None:
            await _client.aclose()
            _client = None
            log.info("Closed shared http client")
