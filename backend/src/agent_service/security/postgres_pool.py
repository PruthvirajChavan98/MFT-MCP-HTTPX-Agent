"""Optional PostgreSQL async pool for security analytics workflows."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("security.postgres")


@dataclass(slots=True)
class PostgresPoolManager:
    dsn: str
    min_size: int = 10
    max_size: int = 50
    _pool: Any = field(init=False, default=None, repr=False)

    @property
    def pool(self):
        return self._pool

    async def start(self) -> None:
        import asyncpg

        self._pool = await asyncpg.create_pool(
            dsn=self.dsn,
            min_size=self.min_size,
            max_size=self.max_size,
            command_timeout=10,
        )
        log.info(
            "Initialized PostgreSQL pool min=%s max=%s",
            self.min_size,
            self.max_size,
        )

    async def stop(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            log.info("Closed PostgreSQL pool")

    async def ping(self) -> bool:
        if self._pool is None:
            return False
        try:
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception:
            return False
