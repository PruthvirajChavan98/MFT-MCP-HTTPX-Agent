"""Backfill trace embeddings for rows persisted without a Milvus doc.

Before `_commit_bundle` started embedding unconditionally, the trace
embed only fired when ``shadow_eval`` produced eval results — i.e.
~5% of live traffic at the default ``SHADOW_EVAL_SAMPLE_RATE``. The
other ~95% of rows landed in Postgres with ``doc IS NULL`` and
``embedding_model IS NULL``, invisible to the admin Semantic Search.

Run this script once per environment after deploying the commit that
adds the unconditional embed in ``_commit_bundle``:

    docker exec mft_agent python -m scripts.backfill_trace_embeddings

Each row is replayed through the same ``EvalEmbedder.embed_trace_if_needed``
path used by live traffic, so the Milvus doc shape matches production
exactly. Idempotent: any row whose ``doc_hash`` matches the rebuilt
doc short-circuits in the embedder and no API call is made.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any

import asyncpg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent_service.core.config import POSTGRES_DSN  # noqa: E402
from src.agent_service.eval_store.embedder import EvalEmbedder  # noqa: E402
from src.common.milvus_mgr import milvus_mgr  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("backfill_trace_embeddings")


def _decode_jsonb(value: Any) -> Any:
    """asyncpg returns jsonb as a JSON-encoded string unless a codec is
    registered on the pool. The embedder expects the decoded structure,
    so decode here. Matches the `_json_load_maybe` pattern used by the
    API layer (see ``eval_read.py``)."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return None
    return None


def _row_to_trace(row: asyncpg.Record) -> dict[str, Any]:
    """Reshape a DB row into the dict ``embed_trace_if_needed`` expects."""
    inputs = _decode_jsonb(row["inputs_json"])
    return {
        "trace_id": row["trace_id"],
        "case_id": row["case_id"],
        "session_id": row["session_id"],
        "provider": row["provider"],
        "model": row["model"],
        "endpoint": row["endpoint"],
        "status": row["status"],
        "error": row["error"],
        "inputs": inputs if isinstance(inputs, dict) else {},
        "final_output": row["final_output"],
    }


async def _fetch_orphan_trace_ids(pool: asyncpg.Pool) -> list[asyncpg.Record]:
    """All rows whose Milvus embedding is missing."""
    return await pool.fetch("""
        SELECT trace_id, case_id, session_id, provider, model, endpoint,
               status, error, inputs_json, final_output
        FROM eval_traces
        WHERE embedding_model IS NULL
        ORDER BY started_at NULLS LAST, trace_id
        """)


async def _fetch_events(pool: asyncpg.Pool, trace_id: str) -> list[dict[str, Any]]:
    rows = await pool.fetch(
        """
        SELECT event_type, name, text, payload_json
        FROM eval_events
        WHERE trace_id = $1
        ORDER BY seq ASC
        """,
        trace_id,
    )
    return [
        {
            "event_type": r["event_type"],
            "name": r["name"],
            "text": r["text"],
            "payload": _decode_jsonb(r["payload_json"]) or {},
        }
        for r in rows
    ]


async def _backfill() -> tuple[int, int]:
    if not POSTGRES_DSN:
        raise RuntimeError("POSTGRES_DSN not configured")

    pool = await asyncpg.create_pool(POSTGRES_DSN, min_size=1, max_size=4)
    try:
        await milvus_mgr.aconnect()
        embedder = EvalEmbedder()
        if not embedder.enabled:
            raise RuntimeError(
                "EvalEmbedder disabled — OPENROUTER_API_KEY is not set in the "
                "container's environment"
            )

        orphans = await _fetch_orphan_trace_ids(pool)
        log.info("Found %d trace rows without an embedding", len(orphans))

        succeeded = 0
        for row in orphans:
            trace = _row_to_trace(row)
            try:
                events = await _fetch_events(pool, trace["trace_id"])
                await embedder.embed_trace_if_needed(pool, trace, events)
                succeeded += 1
            except Exception as exc:
                log.error(
                    "embed_trace_if_needed failed trace_id=%s err=%s",
                    trace["trace_id"],
                    exc,
                )

        return len(orphans), succeeded
    finally:
        await pool.close()


def main() -> int:
    attempted, succeeded = asyncio.run(_backfill())
    log.info(
        "Backfill complete — %d attempted, %d succeeded, %d failed",
        attempted,
        succeeded,
        attempted - succeeded,
    )
    return 0 if succeeded == attempted else 1


if __name__ == "__main__":
    sys.exit(main())
