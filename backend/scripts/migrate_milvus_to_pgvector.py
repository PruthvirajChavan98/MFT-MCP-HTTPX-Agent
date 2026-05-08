"""One-shot data migration: Milvus → pgvector.

Reads every record from each Milvus collection (kb_faqs, eval_traces_emb,
eval_results_emb, inline_guard_cache) and writes the embeddings + metadata
into the corresponding pgvector tables in `mft_security`.

Idempotent: each insert is `ON CONFLICT DO UPDATE` keyed on the natural
primary key, so re-running picks up where it left off (or just confirms
existing rows are correct).

Pre-flight requirements:
1. The `vector` extension must be installed (db_migrate.sh handles this on
   bootstrap; or run `CREATE EXTENSION vector;` as superuser manually).
2. `04_pgvector_init.sql` must have been applied (creates kb_faqs +
   inline_guard_cache tables, adds embedding columns to eval_*).
3. MILVUS_URI + POSTGRES_DSN both reachable from the script's container.

Usage (from inside the agent container so env is wired):

    docker exec mft_agent python -m scripts.migrate_milvus_to_pgvector --dry-run
    docker exec mft_agent python -m scripts.migrate_milvus_to_pgvector

Pass --dry-run to read counts only without writing. Otherwise the script
writes in batches of 200 and reports progress per collection.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Any

import asyncpg
from pgvector.asyncpg import register_vector

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent_service.core.config import (  # noqa: E402
    MILVUS_URI,
    POSTGRES_DSN,
)
from src.common.milvus_mgr import milvus_mgr  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("milvus_to_pgvector")

BATCH = 200


async def _connect_pg() -> asyncpg.Connection:
    if not POSTGRES_DSN:
        raise SystemExit("POSTGRES_DSN env var required")
    conn = await asyncpg.connect(POSTGRES_DSN)
    await register_vector(conn)
    return conn


async def _read_collection_rows(collection_name: str) -> list[dict[str, Any]]:
    """Read every row from a Milvus collection via pymilvus.MilvusClient.
    Returns rows with `vector` and `metadata` populated."""
    from pymilvus import MilvusClient

    token = os.environ.get("MILVUS_TOKEN", "").strip() or None
    conn_args: dict[str, Any] = {"uri": MILVUS_URI}
    if token:
        conn_args["token"] = token
    client = MilvusClient(**conn_args)
    if not client.has_collection(collection_name):
        log.info("Collection %s not present in Milvus — skipping", collection_name)
        return []

    # Page through all rows. Milvus doesn't paginate the same way as SQL —
    # we iterate via the iterator pattern. For our scale (hundreds → low
    # thousands) a single query_iterator pass works fine.
    rows: list[dict[str, Any]] = []
    iterator = client.query_iterator(
        collection_name=collection_name,
        filter="",
        output_fields=["*"],
        batch_size=BATCH,
    )
    while True:
        batch = iterator.next()
        if not batch:
            break
        rows.extend(batch)
    iterator.close()
    return rows


async def _migrate_kb_faqs(conn: asyncpg.Connection, dry_run: bool) -> int:
    rows = await _read_collection_rows("kb_faqs")
    log.info("kb_faqs: %d rows in Milvus", len(rows))
    if dry_run or not rows:
        return len(rows)
    written = 0
    for r in rows:
        meta = {k: v for k, v in r.items() if k not in {"vector", "pk"}}
        question_key = meta.get("question_key") or meta.get("pk") or ""
        if not question_key:
            log.warning("kb_faqs row missing question_key — skipping")
            continue
        await conn.execute(
            """
            INSERT INTO kb_faqs (
                question_key, question, answer, category, embedding, embedding_model
            ) VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (question_key) DO UPDATE SET
                question = EXCLUDED.question,
                answer = EXCLUDED.answer,
                category = EXCLUDED.category,
                embedding = EXCLUDED.embedding,
                embedding_model = EXCLUDED.embedding_model,
                updated_at = NOW()
            """,
            str(question_key),
            str(meta.get("question") or meta.get("text") or meta.get("page_content") or ""),
            str(meta.get("answer") or ""),
            str(meta.get("category") or ""),
            list(r["vector"]),
            "openai/text-embedding-3-small",
        )
        written += 1
    log.info("kb_faqs: wrote %d rows to pgvector", written)
    return written


async def _migrate_eval_traces(conn: asyncpg.Connection, dry_run: bool) -> int:
    rows = await _read_collection_rows("eval_traces_emb")
    log.info("eval_traces_emb: %d rows in Milvus", len(rows))
    if dry_run or not rows:
        return len(rows)
    written = 0
    for r in rows:
        trace_id = r.get("trace_id") or r.get("pk")
        if not trace_id:
            continue
        result = await conn.execute(
            "UPDATE eval_traces SET embedding = $1 WHERE trace_id = $2",
            list(r["vector"]),
            str(trace_id),
        )
        if result.endswith(" 1"):
            written += 1
    log.info("eval_traces_emb: matched + updated %d rows", written)
    return written


async def _migrate_eval_results(conn: asyncpg.Connection, dry_run: bool) -> int:
    rows = await _read_collection_rows("eval_results_emb")
    log.info("eval_results_emb: %d rows in Milvus", len(rows))
    if dry_run or not rows:
        return len(rows)
    written = 0
    for r in rows:
        eval_id = r.get("eval_id") or r.get("pk")
        if not eval_id:
            continue
        result = await conn.execute(
            "UPDATE eval_results SET embedding = $1 WHERE eval_id = $2",
            list(r["vector"]),
            str(eval_id),
        )
        if result.endswith(" 1"):
            written += 1
    log.info("eval_results_emb: matched + updated %d rows", written)
    return written


async def _migrate_inline_guard_cache(conn: asyncpg.Connection, dry_run: bool) -> int:
    rows = await _read_collection_rows("inline_guard_cache")
    log.info("inline_guard_cache: %d rows in Milvus", len(rows))
    if dry_run or not rows:
        return len(rows)
    written = 0
    for r in rows:
        await conn.execute(
            """
            INSERT INTO inline_guard_cache (
                decision, reason_code, risk_score,
                model_version, embedder_version, content_hash,
                ts, embedding
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (content_hash, model_version, embedder_version)
            DO UPDATE SET
                decision = EXCLUDED.decision,
                reason_code = EXCLUDED.reason_code,
                risk_score = EXCLUDED.risk_score,
                ts = EXCLUDED.ts,
                embedding = EXCLUDED.embedding
            """,
            str(r.get("decision") or ""),
            str(r.get("reason_code") or ""),
            float(r.get("risk_score") or 0.0),
            str(r.get("model_version") or ""),
            str(r.get("embedder_version") or ""),
            str(r.get("content_hash") or ""),
            int(r.get("ts") or 0),
            list(r["vector"]),
        )
        written += 1
    log.info("inline_guard_cache: wrote %d rows to pgvector", written)
    return written


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Read counts only")
    args = parser.parse_args()

    log.info("Milvus URI: %s", MILVUS_URI)
    log.info("Postgres DSN host: %s", POSTGRES_DSN.split("@", 1)[-1] if POSTGRES_DSN else "?")
    log.info("Mode: %s", "DRY RUN" if args.dry_run else "WRITE")

    # Initialize Milvus singleton — needed if the iterator path uses it.
    if milvus_mgr.kb_faqs is None:
        await milvus_mgr.aconnect()

    conn = await _connect_pg()
    try:
        kb = await _migrate_kb_faqs(conn, args.dry_run)
        et = await _migrate_eval_traces(conn, args.dry_run)
        er = await _migrate_eval_results(conn, args.dry_run)
        ig = await _migrate_inline_guard_cache(conn, args.dry_run)
        log.info(
            "Migration complete (mode=%s) — kb_faqs=%d eval_traces=%d eval_results=%d inline_guard_cache=%d",
            "dry" if args.dry_run else "write",
            kb,
            et,
            er,
            ig,
        )
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
