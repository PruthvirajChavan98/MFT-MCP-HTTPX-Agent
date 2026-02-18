from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Dict, Optional

from neo4j import GraphDatabase
from neo4j.exceptions import DriverError, ServiceUnavailable, SessionExpired

log = logging.getLogger("neo4j_manager")


class Neo4jManager:
    _driver = None
    _lock = threading.Lock()

    @classmethod
    def _connection_settings(cls) -> Dict[str, Any]:
        return {
            "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            "user": os.getenv("NEO4J_USER", "neo4j"),
            "password": os.getenv("NEO4J_PASSWORD", "password"),
            "conn_timeout": float(os.getenv("NEO4J_CONNECTION_TIMEOUT_SECONDS", "5")),
            "acquire_timeout": float(os.getenv("NEO4J_ACQUISITION_TIMEOUT_SECONDS", "10")),
            "max_retries": int(os.getenv("NEO4J_MAX_RETRIES", "4")),
            "retry_base": float(os.getenv("NEO4J_RETRY_BASE_SECONDS", "0.5")),
        }

    @classmethod
    def get_driver(cls, *, force_refresh: bool = False):
        """Return singleton Neo4j driver with connectivity verification."""
        cfg = cls._connection_settings()
        uri = cfg["uri"]
        user = cfg["user"]
        password = cfg["password"]

        with cls._lock:
            if force_refresh and cls._driver is not None:
                try:
                    cls._driver.close()
                finally:
                    cls._driver = None

            if cls._driver is None:
                cls._driver = GraphDatabase.driver(
                    uri,
                    auth=(user, password),
                    connection_timeout=cfg["conn_timeout"],
                    connection_acquisition_timeout=cfg["acquire_timeout"],
                    max_connection_lifetime=1800,
                    max_connection_pool_size=50,
                )

            try:
                cls._driver.verify_connectivity()
            except Exception:
                # Reset broken driver so next retry can recreate it.
                try:
                    cls._driver.close()
                except Exception:
                    pass
                cls._driver = None
                raise

            return cls._driver

    @classmethod
    def close(cls):
        with cls._lock:
            if cls._driver:
                cls._driver.close()
                cls._driver = None

    @classmethod
    def _with_retry(cls, fn_name: str, query: str, params: Optional[dict] = None):
        cfg = cls._connection_settings()
        max_retries = max(1, cfg["max_retries"])
        retry_base = max(0.1, cfg["retry_base"])
        last_err: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                driver = cls.get_driver(force_refresh=(attempt > 1))
                with driver.session() as session:
                    result = session.run(query, params or {})
                    return [record.data() for record in result]
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
                time.sleep(sleep_s)

        err = last_err or RuntimeError("Neo4j operation failed")
        raise RuntimeError(f"Neo4j {fn_name} failed after {max_retries} attempts: {err}") from err

    @classmethod
    def execute_write(cls, query, params=None):
        """Execute write query with connectivity retries."""
        return cls._with_retry("write", query, params)

    @classmethod
    def execute_read(cls, query, params=None):
        """Execute read query with connectivity retries."""
        return cls._with_retry("read", query, params)
