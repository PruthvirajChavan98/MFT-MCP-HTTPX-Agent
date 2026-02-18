"""Redis-backed session security risk engine."""

from __future__ import annotations

import ipaddress
import json
import logging
import math
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Protocol

from redis.asyncio import Redis as AsyncRedis

from src.agent_service.security.metrics import (
    SESSION_CONCURRENT_IP_HIGH_RISK_TOTAL,
    SESSION_DECISIONS_TOTAL,
    SESSION_DEVICE_MISMATCH_TOTAL,
    SESSION_GEO_ANOMALY_TOTAL,
    SESSION_IMPOSSIBLE_TRAVEL_TOTAL,
    SESSION_RISK_SCORE,
)

log = logging.getLogger("security.session")

RiskDecision = Literal["allow", "step_up", "deny"]


class GeoResolverProtocol(Protocol):
    """Protocol for IP geolocation resolvers."""

    async def resolve(self, ip_str: str) -> "GeoLocation | None":
        pass


@dataclass(slots=True)
class GeoLocation:
    latitude: float
    longitude: float
    country_code: str | None = None


@dataclass(slots=True)
class SessionSecurityConfig:
    impossible_travel_speed_kmh: float = 900.0
    concurrent_ip_window_seconds: int = 300
    concurrent_ip_threshold: int = 3

    risk_impossible_travel: float = 0.6
    risk_concurrent_ips: float = 0.5
    risk_device_mismatch: float = 0.4
    risk_geo_anomaly: float = 0.3

    allow_threshold: float = 0.4
    step_up_threshold: float = 0.7

    key_ttl_seconds: int = 86400 * 30


@dataclass(slots=True)
class RiskAssessment:
    session_id: str
    score: float
    decision: RiskDecision
    reasons: list[str] = field(default_factory=list)
    required_action: str = "none"
    velocity_kmh: float | None = None
    distance_km: float | None = None
    concurrent_ip_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SessionSecurityValidator:
    """Evaluate request/session risk with Redis time-series IP tracking."""

    def __init__(
        self,
        redis: AsyncRedis,
        *,
        config: SessionSecurityConfig | None = None,
        geo_resolver: GeoResolverProtocol | None = None,
    ) -> None:
        self.redis = redis
        self.config = config or SessionSecurityConfig()
        self.geo_resolver = geo_resolver

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Great-circle distance in kilometers."""
        r_earth_km = 6371.0
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = (
            math.sin(d_lat / 2) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return r_earth_km * c

    @staticmethod
    def _validate_session_id(session_id: str) -> str:
        sid = (session_id or "").strip()
        if not sid:
            raise ValueError("session_id must be a non-empty string")
        if len(sid) > 256:
            raise ValueError("session_id too long")
        return sid

    @staticmethod
    def _validate_ip(ip_str: str) -> str:
        normalized = (ip_str or "").strip()
        ipaddress.ip_address(normalized)
        return normalized

    def _decision_for_score(self, score: float) -> tuple[RiskDecision, str]:
        if score < self.config.allow_threshold:
            return "allow", "none"
        if score <= self.config.step_up_threshold:
            return "step_up", "require_2fa"
        return "deny", "deny_request"

    async def _load_last_state(self, state_key: str) -> dict[str, str]:
        state = await self.redis.hgetall(state_key)
        return state or {}

    async def _resolve_geo(self, ip_str: str) -> GeoLocation | None:
        if self.geo_resolver is None:
            return None
        try:
            return await self.geo_resolver.resolve(ip_str)
        except Exception as exc:
            log.warning("Geo resolver failed for %s: %r", ip_str, exc)
            return None

    async def assess(
        self,
        *,
        session_id: str,
        client_ip: str,
        device_fingerprint: str | None,
    ) -> RiskAssessment:
        """Assess request risk and persist updated session telemetry."""
        sid = self._validate_session_id(session_id)
        ip_str = self._validate_ip(client_ip)

        now = time.time()
        cfg = self.config

        zset_key = f"session:ip_ts:{sid}"
        state_key = f"session:state:{sid}"
        fp_key = f"session:fingerprint:{sid}"

        # Sliding window tracking for concurrent IP detection.
        window_floor = now - cfg.concurrent_ip_window_seconds
        await self.redis.zremrangebyscore(zset_key, "-inf", window_floor)
        await self.redis.zadd(zset_key, {ip_str: now})
        concurrent_ip_count = int(await self.redis.zcard(zset_key))

        reasons: list[str] = []
        score = 0.0
        velocity_kmh: float | None = None
        distance_km: float | None = None

        # Device fingerprint consistency.
        if device_fingerprint:
            existing_fp = await self.redis.get(fp_key)
            if existing_fp and existing_fp != device_fingerprint:
                score += cfg.risk_device_mismatch
                reasons.append("device_fingerprint_mismatch")
                SESSION_DEVICE_MISMATCH_TOTAL.inc()
            elif not existing_fp:
                await self.redis.set(fp_key, device_fingerprint, ex=cfg.key_ttl_seconds)

        # Concurrent IP anomaly in short window.
        if concurrent_ip_count > cfg.concurrent_ip_threshold:
            score += cfg.risk_concurrent_ips
            reasons.append("high_concurrent_ip_activity")
            SESSION_CONCURRENT_IP_HIGH_RISK_TOTAL.inc()

        # Geographic velocity / impossible travel.
        previous = await self._load_last_state(state_key)
        current_geo = await self._resolve_geo(ip_str)
        if current_geo and previous:
            try:
                prev_ts = float(previous.get("last_seen_ts", "0"))
                prev_lat = float(previous.get("last_lat", "0"))
                prev_lon = float(previous.get("last_lon", "0"))

                distance_km = self._haversine_km(
                    prev_lat, prev_lon, current_geo.latitude, current_geo.longitude
                )
                delta_hours = max((now - prev_ts) / 3600.0, 1e-9)
                velocity_kmh = distance_km / delta_hours

                if velocity_kmh > cfg.impossible_travel_speed_kmh:
                    score += cfg.risk_impossible_travel
                    reasons.append("impossible_travel")
                    SESSION_IMPOSSIBLE_TRAVEL_TOTAL.inc()
                elif previous.get("last_country") and current_geo.country_code:
                    if previous.get("last_country") != current_geo.country_code:
                        score += cfg.risk_geo_anomaly
                        reasons.append("geographic_anomaly")
                        SESSION_GEO_ANOMALY_TOTAL.inc()
            except Exception as exc:
                log.warning("Failed travel-risk evaluation for %s: %r", sid, exc)

        score = min(1.0, round(score, 3))
        decision, required_action = self._decision_for_score(score)

        if "impossible_travel" in reasons:
            decision, required_action = "deny", "deny_request"

        assessment = RiskAssessment(
            session_id=sid,
            score=score,
            decision=decision,
            reasons=reasons,
            required_action=required_action,
            velocity_kmh=velocity_kmh,
            distance_km=distance_km,
            concurrent_ip_count=concurrent_ip_count,
        )

        payload = {
            "last_seen_ts": str(now),
            "last_ip": ip_str,
        }
        if current_geo:
            payload.update(
                {
                    "last_lat": str(current_geo.latitude),
                    "last_lon": str(current_geo.longitude),
                    "last_country": current_geo.country_code or "",
                }
            )

        await self.redis.hset(state_key, mapping=payload)
        await self.redis.expire(state_key, cfg.key_ttl_seconds)
        await self.redis.expire(zset_key, cfg.key_ttl_seconds)

        # Persist the latest decision for auditing/debug support.
        await self.redis.set(
            f"session:risk:last:{sid}",
            json.dumps(assessment.to_dict(), separators=(",", ":")),
            ex=cfg.key_ttl_seconds,
        )

        SESSION_DECISIONS_TOTAL.labels(decision=decision).inc()
        SESSION_RISK_SCORE.labels(decision=decision).observe(score)

        log.info(
            "session_risk_evaluated sid=%s score=%.3f decision=%s reasons=%s concurrent_ip_count=%s",
            sid,
            score,
            decision,
            ",".join(reasons) if reasons else "none",
            concurrent_ip_count,
        )

        return assessment
