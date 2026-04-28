"""One-shot: drop + rebuild the ``eval_results_emb`` Milvus collection.

The collection's field schema was locked at first-insert time, before
the embedder started emitting an ``eval_id`` metadata field. That
leaves `POST /api/eval/vector-search?kind=result` failing with
``MilvusException: field eval_id not exist`` whenever its
`expr` filter references the id. Fix is structural: drop the
collection, replay every persisted eval row through the existing
``EvalEmbedder.embed_eval_if_needed`` path, and Milvus auto-creates
the collection with today's full metadata schema on first insert.

Run once per environment after deploying the code change:

    docker exec mft_agent python -m scripts.rebuild_eval_results_collection

Safety
------
- Idempotent: if the collection already doesn't exist, the drop is a
  no-op. The re-embed loop short-circuits rows whose ``doc_hash``
  already matches the current content — but we NULL ``doc_hash`` on
  every row first so every row embeds exactly once.
- Never touches ``eval_traces_emb``; that collection doesn't need
  rebuilding because its metadata shape has been stable.
- Embedding cost is bounded: one OpenRouter call per persisted
  ``eval_results`` row. Current prod has ~34 rows → ~$0.001.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Any

import asyncpg
from pymilvus import MilvusClient, connections, utility

# Path gymnastics so the module works when invoked with
# ``python -m scripts.rebuild_eval_results_collection`` OR
# ``python backend/scripts/rebuild_eval_results_collection.py``.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent_service.core.config import (  # noqa: E402
    MILVUS_URI,
    POSTGRES_DSN,
)
from src.agent_service.eval_store.embedder import EvalEmbedder  # noqa: E402
from src.common.milvus_mgr import milvus_mgr  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("rebuild_eval_results")

_MILVUS_TOKEN = os.environ.get("MILVUS_TOKEN", "").strip() or None
_COLLECTION_NAME = "eval_results_emb"


def _drop_collection() -> None:
    """Drop the old collection so the first aadd_documents() call in the
    re-embed loop creates a new one with the current metadata shape."""
    log.info("Connecting to Milvus at %s to drop %s", MILVUS_URI, _COLLECTION_NAME)
    # MilvusClient + pymilvus `connections` both work; use the low-level
    # module to avoid taking a dependency on the langchain-milvus wrapper.
    connections.connect(
        alias="rebuild",
        uri=MILVUS_URI,
        token=_MILVUS_TOKEN or "",
    )
    try:
        if utility.has_collection(_COLLECTION_NAME, using="rebuild"):
            utility.drop_collection(_COLLECTION_NAME, using="rebuild")
            log.info("Dropped collection %s", _COLLECTION_NAME)
        else:
            log.info("Collection %s did not exist — skipping drop", _COLLECTION_NAME)
    finally:
        connections.disconnect("rebuild")


async def _reembed_all_eval_results() -> tuple[int, int]:
    """Iterate every persisted eval_results row and call the embedder.
    Returns (attempted, succeeded) counts."""
    if not POSTGRES_DSN:
        raise RuntimeError("POSTGRES_DSN not configured")

    # Force re-embed by clearing the hash; the embedder skips rows whose
    # doc_hash already matches the freshly-built doc.
    pool = await asyncpg.create_pool(POSTGRES_DSN, min_size=1, max_size=4)
    try:
        await pool.execute("UPDATE eval_results SET doc_hash = NULL")

        rows = await pool.fetch("""
            SELECT eval_id, trace_id, metric_name, score, passed, reasoning,
                   evaluator_id, meta_json, evidence_json
            FROM eval_results
            ORDER BY updated_at ASC
            """)
        log.info("Re-embedding %d eval_results rows", len(rows))

        # Ensure the shared Milvus manager has fresh handles (the collection
        # we just dropped needs to be re-acquired).
        await milvus_mgr.aconnect()

        embedder = EvalEmbedder()
        if not embedder.enabled:
            raise RuntimeError("EvalEmbedder is not enabled — check OPENROUTER_API_KEY in env")

        succeeded = 0
        for r in rows:
            ev: dict[str, Any] = {
                "eval_id": r["eval_id"],
                "metric_name": r["metric_name"],
                "score": r["score"],
                "passed": r["passed"],
                "reasoning": r["reasoning"],
                "evaluator_id": r["evaluator_id"],
                "meta": r["meta_json"] or {},
                "evidence": r["evidence_json"] or [],
            }
            try:
                await embedder.embed_eval_if_needed(pool, r["trace_id"], ev)
                succeeded += 1
            except Exception as exc:
                log.error(
                    "embed_eval_if_needed failed eval_id=%s trace_id=%s err=%s",
                    r["eval_id"],
                    r["trace_id"],
                    exc,
                )

        return len(rows), succeeded
    finally:
        await pool.close()


def main() -> int:
    # Sanity check — MilvusClient round-trip to make sure we're talking to
    # the right cluster before destroying anything.
    client = MilvusClient(uri=MILVUS_URI, token=_MILVUS_TOKEN)
    existing = client.list_collections()
    log.info("Milvus collections before drop: %s", existing)

    _drop_collection()

    attempted, succeeded = asyncio.run(_reembed_all_eval_results())
    log.info(
        "Rebuild complete — %d attempted, %d succeeded, %d failed",
        attempted,
        succeeded,
        attempted - succeeded,
    )

    # Confirm the new collection has the eval_id field.
    client = MilvusClient(uri=MILVUS_URI, token=_MILVUS_TOKEN)
    if _COLLECTION_NAME in client.list_collections():
        desc = client.describe_collection(_COLLECTION_NAME)
        fields = [f["name"] for f in desc.get("fields", [])]
        log.info("Post-rebuild schema fields: %s", fields)
        if "eval_id" not in fields:
            log.warning(
                "eval_id field STILL missing after rebuild — inspect the "
                "embedder doc-construction path"
            )
            return 2
    else:
        log.warning(
            "%s did not reappear after the rebuild loop — no rows embedded?",
            _COLLECTION_NAME,
        )
        return 3

    return 0 if succeeded == attempted else 1


if __name__ == "__main__":
    sys.exit(main())
