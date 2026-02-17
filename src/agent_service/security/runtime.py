"""Runtime wiring for security components."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from redis.asyncio import Redis as AsyncRedis

from src.agent_service.core.config import (
    GEOIP_DB_PATH,
    SECURITY_CONCURRENT_IP_THRESHOLD,
    SECURITY_CONCURRENT_IP_WINDOW_SECONDS,
    SECURITY_IMPOSSIBLE_TRAVEL_KMH,
    SECURITY_RISK_ALLOW_THRESHOLD,
    SECURITY_RISK_CONCURRENT_IP,
    SECURITY_RISK_DEVICE_MISMATCH,
    SECURITY_RISK_GEO_ANOMALY,
    SECURITY_RISK_IMPOSSIBLE_TRAVEL,
    SECURITY_RISK_STEP_UP_THRESHOLD,
    TOR_NEGATIVE_CACHE_CLEANUP_INTERVAL,
    TOR_NEGATIVE_CACHE_TTL_SECONDS,
    TOR_REFRESH_SECONDS,
    TOR_STALE_AFTER_SECONDS,
)
from src.agent_service.security.geoip_resolver import MaxMindGeoLiteResolver
from src.agent_service.security.session_security import (
    SessionSecurityConfig,
    SessionSecurityValidator,
)
from src.agent_service.security.tor_block import TorExitBlocker

log = logging.getLogger("security.runtime")


@dataclass(slots=True)
class SecurityRuntime:
    """Container for startup-managed security components."""

    tor_blocker: TorExitBlocker
    session_validator: SessionSecurityValidator
    geo_resolver: MaxMindGeoLiteResolver | None

    async def start(self) -> None:
        await self.tor_blocker.start()

    async def stop(self) -> None:
        await self.tor_blocker.stop()
        if self.geo_resolver:
            self.geo_resolver.close()


def build_security_runtime(redis: AsyncRedis) -> SecurityRuntime:
    """Build runtime objects from environment-backed config."""
    geo_resolver: MaxMindGeoLiteResolver | None = None

    if GEOIP_DB_PATH:
        try:
            geo_resolver = MaxMindGeoLiteResolver(GEOIP_DB_PATH)
            log.info("Loaded GeoIP database: %s", GEOIP_DB_PATH)
        except Exception as exc:
            log.warning("GeoIP resolver disabled: %r", exc)

    session_config = SessionSecurityConfig(
        impossible_travel_speed_kmh=SECURITY_IMPOSSIBLE_TRAVEL_KMH,
        concurrent_ip_window_seconds=SECURITY_CONCURRENT_IP_WINDOW_SECONDS,
        concurrent_ip_threshold=SECURITY_CONCURRENT_IP_THRESHOLD,
        risk_impossible_travel=SECURITY_RISK_IMPOSSIBLE_TRAVEL,
        risk_concurrent_ips=SECURITY_RISK_CONCURRENT_IP,
        risk_device_mismatch=SECURITY_RISK_DEVICE_MISMATCH,
        risk_geo_anomaly=SECURITY_RISK_GEO_ANOMALY,
        allow_threshold=SECURITY_RISK_ALLOW_THRESHOLD,
        step_up_threshold=SECURITY_RISK_STEP_UP_THRESHOLD,
    )

    tor_blocker = TorExitBlocker(
        refresh_seconds=TOR_REFRESH_SECONDS,
        stale_after_seconds=TOR_STALE_AFTER_SECONDS,
        negative_cache_ttl_seconds=TOR_NEGATIVE_CACHE_TTL_SECONDS,
        negative_cache_cleanup_interval=TOR_NEGATIVE_CACHE_CLEANUP_INTERVAL,
    )

    validator = SessionSecurityValidator(redis, config=session_config, geo_resolver=geo_resolver)
    return SecurityRuntime(
        tor_blocker=tor_blocker,
        session_validator=validator,
        geo_resolver=geo_resolver,
    )
