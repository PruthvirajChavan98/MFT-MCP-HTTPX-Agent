"""GeoIP resolvers for session risk analysis."""

from __future__ import annotations

import ipaddress
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.agent_service.security.session_security import GeoLocation

log = logging.getLogger("security.geoip")


@dataclass(slots=True)
class MaxMindGeoLiteResolver:
    """GeoIP resolver backed by a local GeoLite2 City MMDB file."""

    db_path: str
    _reader: Any = None

    def __post_init__(self) -> None:
        self._reader = None
        if not Path(self.db_path).exists():
            raise FileNotFoundError(f"GeoLite database not found: {self.db_path}")

        try:
            import geoip2.database  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("geoip2 package is required for MaxMindGeoLiteResolver") from exc

        self._reader = geoip2.database.Reader(self.db_path)

    async def resolve(self, ip_str: str) -> GeoLocation | None:
        try:
            ipaddress.ip_address(ip_str)
            city = self._reader.city(ip_str)
            if city.location.latitude is None or city.location.longitude is None:
                return None
            return GeoLocation(
                latitude=float(city.location.latitude),
                longitude=float(city.location.longitude),
                country_code=city.country.iso_code,
            )
        except Exception:
            return None

    def close(self) -> None:
        if self._reader:
            self._reader.close()
