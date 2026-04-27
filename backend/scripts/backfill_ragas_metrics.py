"""Backfill RAGAS metrics into ``eval_results`` for historic traces.

For every trace in ``eval_traces`` that has no row whose
``evaluator_id LIKE 'ragas:%'``, this script:

1. Reconstructs a minimal trace dict from the ``eval_traces`` row.
2. Reconstructs ``retrieved_context`` from any ``tool_end`` events
   stored in ``eval_events`` (matching the runtime collector's format
   ``Tool <{tool}> Output: {output}``).
3. Calls ``compute_llm_metrics`` which builds a ``RagasJudge`` and
   evaluates the trace.
4. UPSERTs the resulting metric rows into ``eval_results``.

Idempotent: a re-run skips any trace that already has at least one
``ragas:*`` evaluator_id row. Safe to re-run after partial failures.

Invoke inside the agent container::

    docker exec mft_agent python -m scripts.backfill_ragas_metrics
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from types import SimpleNamespace
from typing import Any

import asyncpg

from src.agent_service.eval_store.pg_store import EvalPgStore
from src.agent_service.features.eval.metrics import compute_llm_metrics

log = logging.getLogger("backfill_ragas_metrics")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")


async def _trace_ids_needing_backfill(pool: asyncpg.Pool) -> list[str]:
    rows = await pool.fetch("""
        SELECT t.trace_id
        FROM eval_traces t
        WHERE t.final_output IS NOT NULL
          AND length(t.final_output) > 0
          AND NOT EXISTS (
              SELECT 1 FROM eval_results r
              WHERE r.trace_id = t.trace_id
                AND r.evaluator_id LIKE 'ragas:%'
          )
        ORDER BY t.started_at ASC NULLS LAST
        """)
    return [str(r["trace_id"]) for r in rows]


async def _reconstruct_trace(pool: asyncpg.Pool, trace_id: str) -> dict[str, Any] | None:
    row = await pool.fetchrow(
        """
        SELECT trace_id, status, error, inputs_json, final_output, model
        FROM eval_traces
        WHERE trace_id = $1
        """,
        trace_id,
    )
    if row is None:
        return None
    inputs = row["inputs_json"] or {}
    if isinstance(inputs, str):
        try:
            inputs = json.loads(inputs)
        except Exception:
            inputs = {}
    return {
        "trace_id": row["trace_id"],
        "status": row["status"],
        "error": row["error"],
        "inputs": inputs,
        "final_output": row["final_output"],
        "model": row["model"],
    }


async def _reconstruct_collector(pool: asyncpg.Pool, trace_id: str) -> SimpleNamespace:
    """Return a minimal collector-shaped object exposing ``retrieved_context``.

    `compute_llm_metrics` only reads ``collector.retrieved_context``; building
    a full ``ShadowEvalCollector`` (a dataclass with many required fields)
    isn't worth the ceremony for a backfill. The contexts are reconstructed
    from `eval_events.tool_end` payloads using the same
    ``Tool <{tool}> Output: {output}`` formatting the live collector emits.
    """
    rows = await pool.fetch(
        """
        SELECT payload_json
        FROM eval_events
        WHERE trace_id = $1 AND event_type = 'tool_end'
        ORDER BY seq
        """,
        trace_id,
    )
    contexts: list[str] = []
    for r in rows:
        payload = r["payload_json"]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}
        payload = payload or {}
        tool = payload.get("tool") or "tool"
        output = payload.get("output")
        if output is None:
            continue
        out_str = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        contexts.append(f"Tool <{tool}> Output: {out_str}")
    return SimpleNamespace(retrieved_context=contexts)


async def main() -> None:
    dsn = os.environ.get("POSTGRES_DSN") or ""
    if not dsn:
        raise SystemExit("POSTGRES_DSN not set")

    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    store = EvalPgStore()
    try:
        trace_ids = await _trace_ids_needing_backfill(pool)
        log.info("Backfill candidates: %d traces", len(trace_ids))
        if not trace_ids:
            log.info("Nothing to do — every eligible trace already has ragas:* rows")
            return

        total_written = 0
        total_processed = 0
        for trace_id in trace_ids:
            trace = await _reconstruct_trace(pool, trace_id)
            if trace is None:
                log.warning("trace %s vanished between scan and fetch; skipping", trace_id)
                continue
            collector = await _reconstruct_collector(pool, trace_id)

            try:
                metrics = await compute_llm_metrics(trace, collector)
            except Exception as exc:  # noqa: BLE001
                log.warning("RAGAS evaluation failed for trace %s: %s", trace_id, exc)
                continue

            if metrics:
                await store.upsert_evals(pool, trace_id, metrics)
                total_written += len(metrics)
            total_processed += 1
            if total_processed % 10 == 0:
                log.info(
                    "Progress: %d traces processed, %d ragas rows written",
                    total_processed,
                    total_written,
                )

        log.info(
            "Backfill done: %d traces processed, %d ragas rows written",
            total_processed,
            total_written,
        )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
