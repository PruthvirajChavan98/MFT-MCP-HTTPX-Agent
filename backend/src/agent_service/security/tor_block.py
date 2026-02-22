"""Tor blocking runtime and FastAPI middleware."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import time
from collections.abc import Iterable
from typing import Any, Protocol

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.agent_service.security.metrics import (
    TOR_BLOCKS_TOTAL,
    TOR_EXIT_NODES_COUNT,
    TOR_LIST_REFRESH_DURATION_SECONDS,
    TOR_LIST_REFRESH_FAILURES_TOTAL,
    TOR_LIST_STALENESS_SECONDS,
    TOR_MONITORED_TOTAL,
    normalize_path_for_metrics,
)
from src.agent_service.security.tor_exit_nodes import TorExitNodes

log = logging.getLogger("security.tor")


class AnonymizerCheckerProtocol(Protocol):
    """Protocol for optional VPN/proxy/hosting classification providers."""

    def classify(self, ip_str: str) -> dict[str, bool]:
        pass


def _audit_event(event_type: str, **fields: Any) -> None:
    """Emit structured JSON logs for SIEM pipelines."""
    payload = {
        "event_type": event_type,
        "event_time": int(time.time()),
        **fields,
    }
    log.info(json.dumps(payload, sort_keys=True, separators=(",", ":")))


class TorExitBlocker:
    """Background refresher + in-memory lookup for Tor exits."""

    def __init__(
        self,
        *,
        refresh_seconds: int = 1800,
        stale_after_seconds: int = 7200,
        negative_cache_ttl_seconds: int = 300,
        negative_cache_cleanup_interval: int = 1000,
        client: TorExitNodes | None = None,
    ) -> None:
        self.refresh_seconds = refresh_seconds
        self.stale_after_seconds = stale_after_seconds
        self.negative_cache_ttl_seconds = negative_cache_ttl_seconds
        self.negative_cache_cleanup_interval = max(1, negative_cache_cleanup_interval)

        self._ips: set[ipaddress._BaseAddress] = set()
        self._negative_cache: dict[str, float] = {}
        self._checks = 0
        self._last_refresh_epoch: float | None = None

        self._task: asyncio.Task | None = None
        self._client = client or TorExitNodes()

    @property
    def last_refresh_epoch(self) -> float | None:
        return self._last_refresh_epoch

    def staleness_seconds(self) -> float:
        if self._last_refresh_epoch is None:
            return float("inf")
        age = max(0.0, time.time() - self._last_refresh_epoch)
        TOR_LIST_STALENESS_SECONDS.set(age)
        return age

    def is_stale(self) -> bool:
        return self.staleness_seconds() > self.stale_after_seconds

    def _cleanup_negative_cache(self, now_epoch: float) -> None:
        if self._checks % self.negative_cache_cleanup_interval != 0:
            return

        expired = [ip for ip, expiry in self._negative_cache.items() if expiry <= now_epoch]
        for ip in expired:
            self._negative_cache.pop(ip, None)

    async def refresh_once(self) -> None:
        started = time.perf_counter()
        try:
            ip_strings = await self._client.aget()
            self._ips = {ipaddress.ip_address(ip_value) for ip_value in ip_strings}
            self._last_refresh_epoch = time.time()

            TOR_EXIT_NODES_COUNT.set(len(self._ips))
            _audit_event(
                "tor_list_refreshed",
                exits_count=len(self._ips),
                stale_seconds=self.staleness_seconds(),
            )
        except Exception as exc:
            TOR_LIST_REFRESH_FAILURES_TOTAL.inc()
            _audit_event(
                "tor_list_refresh_failed",
                error=repr(exc),
                stale_seconds=self.staleness_seconds(),
            )
            log.warning("Failed to refresh Tor exit list: %r", exc)
        finally:
            TOR_LIST_REFRESH_DURATION_SECONDS.observe(time.perf_counter() - started)

    async def _loop(self) -> None:
        while True:
            await self.refresh_once()
            await asyncio.sleep(self.refresh_seconds)

    async def start(self) -> None:
        await self.refresh_once()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if not self._task:
            return

        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    def is_tor_ip(self, ip_str: str | None) -> bool:
        if not ip_str:
            return False

        now_epoch = time.time()
        self._checks += 1
        self._cleanup_negative_cache(now_epoch)

        expiry = self._negative_cache.get(ip_str)
        if expiry is not None and expiry > now_epoch:
            return False

        try:
            ip_value = ipaddress.ip_address(ip_str)
        except ValueError:
            return False

        if ip_value in self._ips:
            return True

        self._negative_cache[ip_str] = now_epoch + self.negative_cache_ttl_seconds
        return False


class BlockTorMiddleware(BaseHTTPMiddleware):
    """
    Block Tor and optional anonymizer traffic with path-aware policy.

    - Critical paths: blocked on Tor/anonymizer detection.
    - Monitored paths: request allowed but audited and counted.
    """

    def __init__(
        self,
        app: ASGIApp,
        tor_blocker: TorExitBlocker | None = None,
        *,
        critical_paths: Iterable[str] = (),
        monitored_paths: Iterable[str] = (),
        proxies_trusted: bool = False,
        prefer_header: str | None = None,
        anonymizer: AnonymizerCheckerProtocol | None = None,
        block_hosting: bool = True,
    ) -> None:
        super().__init__(app)
        self.tor_blocker = tor_blocker
        self.critical_paths = tuple(critical_paths)
        self.monitored_paths = tuple(monitored_paths)
        self.proxies_trusted = proxies_trusted
        self.prefer_header = (prefer_header or "").lower()
        self.anonymizer = anonymizer
        self.block_hosting = block_hosting

    @staticmethod
    def _first_ip_from_xff(value: str) -> str | None:
        return value.split(",")[0].strip() if value else None

    def _extract_client_ip(self, request: Request) -> str | None:
        if self.proxies_trusted:
            if self.prefer_header:
                preferred = request.headers.get(self.prefer_header)
                if preferred:
                    return (
                        self._first_ip_from_xff(preferred)
                        if self.prefer_header == "x-forwarded-for"
                        else preferred.strip()
                    )

            for header_name in ("cf-connecting-ip", "x-real-ip", "x-forwarded-for"):
                value = request.headers.get(header_name)
                if not value:
                    continue
                if header_name == "x-forwarded-for":
                    return self._first_ip_from_xff(value)
                return value.strip()

        return request.client.host if request.client else None

    def _path_mode(self, path: str) -> str:
        if any(path.startswith(prefix) for prefix in self.critical_paths):
            return "critical"
        if any(path.startswith(prefix) for prefix in self.monitored_paths):
            return "monitored"
        return "critical"

    def _blocked_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={"detail": "Forbidden"},
            headers={"Cache-Control": "no-store"},
        )

    async def dispatch(self, request: Request, call_next):
        tor_blocker = self.tor_blocker
        if tor_blocker is None:
            runtime = getattr(request.app.state, "security_runtime", None)
            tor_blocker = getattr(runtime, "tor_blocker", None) if runtime else None

        if tor_blocker is None:
            return await call_next(request)

        path = request.url.path
        client_ip = self._extract_client_ip(request)
        request.state.client_ip = client_ip

        mode = self._path_mode(path)

        if tor_blocker.is_stale():
            _audit_event(
                "tor_list_stale",
                stale_seconds=tor_blocker.staleness_seconds(),
                path=path,
            )

        is_tor = tor_blocker.is_tor_ip(client_ip)
        if is_tor:
            route = request.scope.get("route")
            route_path = getattr(route, "path", None)
            path_pattern = normalize_path_for_metrics(path, route_path=route_path)
            if mode == "critical":
                TOR_BLOCKS_TOTAL.labels(path_pattern=path_pattern).inc()
                _audit_event("tor_blocked", ip=client_ip, path=path, mode=mode)
                return self._blocked_response()

            TOR_MONITORED_TOTAL.labels(path_pattern=path_pattern).inc()
            _audit_event("tor_monitored", ip=client_ip, path=path, mode=mode)

        if self.anonymizer and client_ip:
            cls = self.anonymizer.classify(client_ip)
            blocked = bool(
                cls.get("vpn") or cls.get("proxy") or (self.block_hosting and cls.get("hosting"))
            )
            if blocked:
                if mode == "critical":
                    _audit_event(
                        "anonymizer_blocked",
                        ip=client_ip,
                        path=path,
                        mode=mode,
                        cls=cls,
                    )
                    return self._blocked_response()
                _audit_event("anonymizer_monitored", ip=client_ip, path=path, mode=mode, cls=cls)

        return await call_next(request)
