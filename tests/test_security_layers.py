import ipaddress
import time

import fakeredis.aioredis
import pytest

from src.agent_service.security.session_security import (
    GeoLocation,
    SessionSecurityConfig,
    SessionSecurityValidator,
)
from src.agent_service.security.tor_block import TorExitBlocker
from src.agent_service.security.tor_exit_nodes import TorExitNodes


class StaticGeoResolver:
    def __init__(self, mapping: dict[str, GeoLocation]):
        self.mapping = mapping

    async def resolve(self, ip_str: str):
        return self.mapping.get(ip_str)


@pytest.mark.asyncio
async def test_session_risk_device_mismatch_step_up():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    validator = SessionSecurityValidator(redis)

    first = await validator.assess(
        session_id="sess-1",
        client_ip="1.1.1.1",
        device_fingerprint="fp-a",
    )
    assert first.decision == "allow"

    second = await validator.assess(
        session_id="sess-1",
        client_ip="1.1.1.1",
        device_fingerprint="fp-b",
    )
    assert second.decision == "step_up"
    assert "device_fingerprint_mismatch" in second.reasons
    assert second.score == pytest.approx(0.4)


@pytest.mark.asyncio
async def test_session_risk_concurrent_ips_step_up():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    cfg = SessionSecurityConfig(concurrent_ip_threshold=3, concurrent_ip_window_seconds=300)
    validator = SessionSecurityValidator(redis, config=cfg)

    for idx in range(1, 5):
        result = await validator.assess(
            session_id="sess-2",
            client_ip=f"10.0.0.{idx}",
            device_fingerprint="fp",
        )

    assert result.decision == "step_up"
    assert "high_concurrent_ip_activity" in result.reasons
    assert result.concurrent_ip_count == 4
    assert result.score >= 0.5


@pytest.mark.asyncio
async def test_session_risk_impossible_travel_denied():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    resolver = StaticGeoResolver(
        {
            "2.2.2.2": GeoLocation(latitude=51.5074, longitude=-0.1278, country_code="GB"),
        }
    )

    cfg = SessionSecurityConfig(impossible_travel_speed_kmh=900.0)
    validator = SessionSecurityValidator(redis, config=cfg, geo_resolver=resolver)

    # Seed prior state in New York 30 minutes ago.
    now = time.time()
    await redis.hset(
        "session:state:sess-3",
        mapping={
            "last_seen_ts": str(now - 1800),
            "last_lat": "40.7128",
            "last_lon": "-74.0060",
            "last_country": "US",
        },
    )

    result = await validator.assess(
        session_id="sess-3",
        client_ip="2.2.2.2",
        device_fingerprint="fp",
    )

    assert result.decision == "deny"
    assert "impossible_travel" in result.reasons
    assert result.velocity_kmh is not None
    assert result.velocity_kmh > 900.0


def test_tor_exit_nodes_parser_normalizes_and_deduplicates():
    sample = """
ExitAddress 1.1.1.1 2026-02-17 00:00:00
ExitAddress 1.1.1.1 2026-02-17 00:00:01
ExitAddress 2001:0db8::1 2026-02-17 00:00:02
NotARecord 8.8.8.8 2026-02-17 00:00:03
""".strip()

    parsed = TorExitNodes._parse_exit_addresses(sample)
    assert parsed == ["1.1.1.1", "2001:db8::1"]


def test_tor_blocker_negative_cache_and_membership():
    blocker = TorExitBlocker(negative_cache_ttl_seconds=300)
    blocker._ips = {ipaddress.ip_address("1.1.1.1")}  # noqa: SLF001

    assert blocker.is_tor_ip("1.1.1.1") is True

    # First miss populates negative cache.
    assert blocker.is_tor_ip("8.8.8.8") is False
    assert "8.8.8.8" in blocker._negative_cache  # noqa: SLF001

    # Subsequent lookup should short-circuit via negative cache and remain false.
    assert blocker.is_tor_ip("8.8.8.8") is False
