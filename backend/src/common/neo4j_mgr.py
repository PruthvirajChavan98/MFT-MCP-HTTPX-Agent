from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, Optional

from neo4j import AsyncDriver, AsyncGraphDatabase
from neo4j.exceptions import DriverError, ServiceUnavailable, SessionExpired

log = logging.getLogger("neo4j_manager")


class Neo4jManager:
    def __init__(self):
        self._driver: Optional[AsyncDriver] = None
        self._cfg = self._connection_settings()

    @staticmethod
    def _connection_settings() -> Dict[str, Any]:
        return {
            "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            "user": os.getenv("NEO4J_USER", "neo4j"),
            "password": os.getenv("NEO4J_PASSWORD", "password"),
            "conn_timeout": float(os.getenv("NEO4J_CONNECTION_TIMEOUT_SECONDS", "5")),
            "acquire_timeout": float(os.getenv("NEO4J_ACQUISITION_TIMEOUT_SECONDS", "10")),
            "max_retries": int(os.getenv("NEO4J_MAX_RETRIES", "4")),
            "retry_base": float(os.getenv("NEO4J_RETRY_BASE_SECONDS", "0.5")),
        }

    async def connect(self):
        """Initialize and verify the Neo4j driver."""
        if self._driver is not None:
            return

        uri = self._cfg["uri"]
        user = self._cfg["user"]
        password = self._cfg["password"]

        self._driver = AsyncGraphDatabase.driver(
            uri,
            auth=(user, password),
            connection_timeout=self._cfg["conn_timeout"],
            connection_acquisition_timeout=self._cfg["acquire_timeout"],
            max_connection_lifetime=1800,
            max_connection_pool_size=50,
        )

        try:
            await self._driver.verify_connectivity()
            log.info("✅ Neo4j connected successfully")
        except Exception as e:
            log.error(f"❌ Neo4j connect failed: {e}")
            await self.close()
            raise

    async def close(self):
        """Close the Neo4j driver."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
            log.info("Closed Neo4j driver")

    async def _with_retry(self, fn_name: str, query: str, params: Optional[dict] = None):
        if not self._driver:
            raise RuntimeError("Neo4j driver is not initialized. Call connect() first.")

        max_retries = max(1, self._cfg["max_retries"])
        retry_base = max(0.1, self._cfg["retry_base"])
        last_err: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                # If force_refresh was needed, we'd recreate driver, but AsyncDriver handles pooling.
                async with self._driver.session() as session:
                    result = await session.run(query, params or {})
                    records = await result.data()
                    return records
            except (ServiceUnavailable, SessionExpired, DriverError, OSError) as exc:
                last_err = exc
                if attempt >= max_retries:
                    break
                sleep_s = retry_base * (2 ** (attempt - 1))
                log.warning(
                    "Neo4j %s failed (attempt %s/%s): %s. Retrying in %.2fs",
                    fn_name,
                    attempt,
                    max_retries,
                    exc,
                    sleep_s,
                )
                await asyncio.sleep(sleep_s)

        err = last_err or RuntimeError("Neo4j operation failed")
        raise RuntimeError(f"Neo4j {fn_name} failed after {max_retries} attempts: {err}") from err

    async def execute_write(self, query, params=None):
        """Execute write query with connectivity retries."""
        return await self._with_retry("write", query, params)

    async def execute_read(self, query, params=None):
        """Execute read query with connectivity retries."""
        return await self._with_retry("read", query, params)


# Global instance for use in FastAPI app.state
neo4j_mgr = Neo4jManager()
