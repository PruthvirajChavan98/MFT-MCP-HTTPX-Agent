"""PostgreSQL persistence and embedding for shadow evaluation bundles."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.agent_service.eval_store.embedder import EvalEmbedder
from src.agent_service.eval_store.pg_store import EvalPgStore, get_shared_pool

log = logging.getLogger("shadow_eval")

# Lazy singleton factories (mockable in tests)
_store_instance: EvalPgStore | None = None
_embedder_instance: EvalEmbedder | None = None


def get_eval_store() -> EvalPgStore:
    """Lazy factory for EvalPgStore singleton."""
    global _store_instance
    if _store_instance is None:
        _store_instance = EvalPgStore()
    return _store_instance


def get_eval_embedder() -> EvalEmbedder:
    """Lazy factory for EvalEmbedder singleton."""
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = EvalEmbedder()
    return _embedder_instance


# Backward-compat: existing importers use these module-level names
STORE = get_eval_store()
EMBEDDER = get_eval_embedder()


async def _commit_bundle(
    trace: Dict[str, Any], events: List[Dict[str, Any]], evals: List[Dict[str, Any]]
) -> None:
    pool = get_shared_pool()
    if pool is None:
        log.error("[shadow_eval] PostgreSQL pool not configured; skipping bundle commit")
        return
    await STORE.upsert_trace(pool, trace)
    if events:
        await STORE.upsert_events(pool, trace["trace_id"], events)
    if evals:
        await STORE.upsert_evals(pool, trace["trace_id"], evals)
