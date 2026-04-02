from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase
from neo4j.exceptions import DriverError, ServiceUnavailable, SessionExpired

log = logging.getLogger("memgraph_manager")

# Memgraph 3.8.1 vector index creation syntax.
# Note: Memgraph uses WITH CONFIG {}, NOT OPTIONS {} like Neo4j.
# vector_search.search() yields (node, distance, similarity) — use `similarity` directly (0–1 cosine).
_SCHEMA_STMTS: list[str] = [
    (
        "CREATE VECTOR INDEX followup_context_emb ON :FollowUpContext(embedding) "
        'WITH CONFIG {"dimension": 1536, "capacity": 10000, "metric": "cos"}'
    ),
]


class MemgraphManager:
    def __init__(self) -> None:
        self._driver: AsyncDriver | None = None
        self._uri: str = os.getenv("MEMGRAPH_URI", "bolt://localhost:7687")
        self._user: str = os.getenv("MEMGRAPH_USER", "")
        self._password: str = os.getenv("MEMGRAPH_PASSWORD", "")
        self._max_retries: int = int(os.getenv("MEMGRAPH_MAX_RETRIES", "4"))
        self._retry_base: float = float(os.getenv("MEMGRAPH_RETRY_BASE_SECONDS", "0.5"))

    async def connect(self) -> None:
        if self._driver is not None:
            return

        self._driver = AsyncGraphDatabase.driver(
            self._uri,
            auth=(self._user, self._password),
            max_connection_lifetime=1800,
            max_connection_pool_size=50,
        )

        try:
            await self._driver.verify_connectivity()
            log.info("Memgraph connected: %s", self._uri)
        except Exception as exc:
            log.error("Memgraph connect failed: %s", exc)
            await self.close()
            raise

        await self._ensure_schema()

    async def close(self) -> None:
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
            log.info("Memgraph driver closed")

    async def _ensure_schema(self) -> None:
        """Create vector indexes idempotently. Errors for already-existing indexes are suppressed."""
        async with self._driver.session() as session:  # type: ignore[union-attr]
            for stmt in _SCHEMA_STMTS:
                try:
                    await session.run(stmt)
                except Exception as exc:
                    # Memgraph raises on duplicate index — safe to ignore
                    log.debug("Schema stmt skipped (likely exists): %s", exc)

    async def _with_retry(
        self, op: str, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        if self._driver is None:
            raise RuntimeError("MemgraphManager not connected — call connect() first")

        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                async with self._driver.session() as session:
                    result = await session.run(query, params or {})
                    return await result.data()
            except (ServiceUnavailable, SessionExpired, DriverError, OSError) as exc:
                last_exc = exc
                if attempt >= self._max_retries:
                    break
                delay = self._retry_base * (2 ** (attempt - 1))
                log.warning(
                    "Memgraph %s failed (attempt %d/%d): %s — retrying in %.2fs",
                    op,
                    attempt,
                    self._max_retries,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)

        raise RuntimeError(
            f"Memgraph {op} failed after {self._max_retries} attempts: {last_exc}"
        ) from last_exc

    async def execute_write(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return await self._with_retry("write", query, params)

    async def execute_read(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return await self._with_retry("read", query, params)


memgraph_mgr = MemgraphManager()
