"""Tor exit node source client with retry/backoff semantics."""

from __future__ import annotations

import asyncio
import ipaddress
from typing import Optional

import httpx


class TorExitNodes:
    """
    Fetch and parse Tor exit IPs from Tor Project list.

    Source:
      https://check.torproject.org/exit-addresses
    """

    DEFAULT_URL = "https://check.torproject.org/exit-addresses"

    def __init__(
        self,
        *,
        url: str = DEFAULT_URL,
        timeout: float = 20.0,
        headers: Optional[dict[str, str]] = None,
        verify: bool = True,
        http2: bool = True,
        retry_attempts: int = 3,
        retry_backoff_seconds: tuple[float, float, float] = (1.0, 2.0, 4.0),
    ) -> None:
        self.url = url
        self.timeout = timeout
        self.verify = verify
        self.http2 = http2
        self.retry_attempts = max(1, retry_attempts)
        self.retry_backoff_seconds = retry_backoff_seconds
        self.headers = {"Accept": "text/plain", **(headers or {})}

    async def aget(self) -> list[str]:
        """Fetch Tor exits with exponential backoff retries."""
        last_error: Exception | None = None

        for attempt in range(1, self.retry_attempts + 1):
            try:
                async with httpx.AsyncClient(
                    http2=self.http2,
                    verify=self.verify,
                    timeout=self.timeout,
                    headers=self.headers,
                ) as client:
                    response = await client.get(self.url)
                    response.raise_for_status()
                    return self._parse_exit_addresses(response.text)
            except Exception as exc:
                last_error = exc
                if attempt >= self.retry_attempts:
                    break

                delay = self.retry_backoff_seconds[
                    min(attempt - 1, len(self.retry_backoff_seconds) - 1)
                ]
                await asyncio.sleep(delay)

        assert last_error is not None
        raise last_error

    @staticmethod
    def _parse_exit_addresses(text: str) -> list[str]:
        """Parse and normalize IPs from lines starting with `ExitAddress`."""
        ips: set[ipaddress._BaseAddress] = set()

        for line in text.splitlines():
            if not line.startswith("ExitAddress "):
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            try:
                ip_value = ipaddress.ip_address(parts[1])
            except ValueError:
                continue

            ips.add(ip_value)

        sorted_ips = sorted(ips, key=lambda ip_value: (ip_value.version, int(ip_value)))
        return [ip_value.compressed for ip_value in sorted_ips]
