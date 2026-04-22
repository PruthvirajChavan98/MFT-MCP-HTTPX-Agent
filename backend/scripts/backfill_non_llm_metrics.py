"""One-off backfill for historic traces missing rule-based eval_results rows.

Runs ``compute_non_llm_metrics`` against every trace in ``eval_traces``
whose trace_id has no existing ``StreamOk`` / ``AnswerNonEmpty`` /
``ToolMatch(...)`` / ``NormalizedRegexMatch`` row in ``eval_results``.
Shadow-judge rows (separate table) are not touched.

Idempotent: a second run skips any trace that already has the canonical
4 metrics written. Safe to re-run.

Invoke inside the agent container::

    docker exec mft_agent python -m scripts.backfill_non_llm_metrics
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any

import asyncpg

from src.agent_service.features.eval.metrics import compute_non_llm_metrics

log = logging.getLogger("backfill_non_llm_metrics")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")


# ToolMatch metric name is dynamic (`ToolMatch(<tool>)`), so we check by prefix.
_TOOL_MATCH_PREFIX = "ToolMatch("


_INSERT_SQL = """
INSERT INTO eval_results (
    eval_id, trace_id, metric_name, score, passed,
    reasoning, evaluator_id, meta_json, evidence_json
) VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb
)
ON CONFLICT (eval_id) DO NOTHING
"""


async def _fetch_trace_ids_needing_backfill(pool: asyncpg.Pool) -> list[str]:
    rows = await pool.fetch("""
        SELECT t.trace_id
        FROM eval_traces t
        WHERE NOT EXISTS (
            SELECT 1
            FROM eval_results r
            WHERE r.trace_id = t.trace_id
              AND r.metric_name IN ('StreamOk', 'AnswerNonEmpty')
        )
        ORDER BY t.started_at ASC NULLS LAST
        """)
    return [str(r["trace_id"]) for r in rows]


async def _fetch_trace(pool: asyncpg.Pool, trace_id: str) -> dict[str, Any] | None:
    row = await pool.fetchrow(
        """
        SELECT trace_id, status, error, inputs_json, final_output
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
    }


async def _fetch_tool_names(pool: asyncpg.Pool, trace_id: str) -> set[str]:
    rows = await pool.fetch(
        """
        SELECT name, payload_json
        FROM eval_events
        WHERE trace_id = $1 AND event_type IN ('tool_start', 'tool_end')
        """,
        trace_id,
    )
    names: set[str] = set()
    for r in rows:
        payload = r["payload_json"]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}
        payload = payload or {}
        tool_name = payload.get("tool") or r["name"] or ""
        tool_name = str(tool_name).strip()
        if tool_name and tool_name not in {"tool_start", "tool_end"}:
            names.add(tool_name)
    return names


async def _write_metrics(
    pool: asyncpg.Pool,
    trace_id: str,
    metrics: list[dict[str, Any]],
) -> int:
    written = 0
    for m in metrics:
        await pool.execute(
            _INSERT_SQL,
            m.get("eval_id") or uuid.uuid4().hex,
            trace_id,
            m["metric_name"],
            float(m["score"]),
            bool(m["passed"]),
            m.get("reasoning") or "",
            m.get("evaluator_id") or "shadow_eval",
            json.dumps(m.get("meta") or {"backfilled": "pr14_non_llm_metrics_2026-04-22"}),
            json.dumps(m.get("evidence") or []),
        )
        written += 1
    return written


async def main() -> None:
    dsn = os.environ.get("POSTGRES_DSN") or ""
    if not dsn:
        raise SystemExit("POSTGRES_DSN not set")

    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    try:
        trace_ids = await _fetch_trace_ids_needing_backfill(pool)
        log.info("Backfill candidates: %d traces", len(trace_ids))
        if not trace_ids:
            log.info("Nothing to do — every trace already has StreamOk/AnswerNonEmpty rows")
            return

        total_written = 0
        total_traces = 0
        for trace_id in trace_ids:
            trace = await _fetch_trace(pool, trace_id)
            if trace is None:
                log.warning("trace %s vanished between scan and fetch; skipping", trace_id)
                continue
            tool_names = await _fetch_tool_names(pool, trace_id)
            metrics = compute_non_llm_metrics(trace, events=[], tool_names=tool_names)

            # Filter out any metric whose name already exists for this trace
            # (handles partial backfills from earlier script runs).
            existing = await pool.fetch(
                "SELECT metric_name FROM eval_results WHERE trace_id = $1",
                trace_id,
            )
            have = {r["metric_name"] for r in existing}
            new = [
                m
                for m in metrics
                if m["metric_name"] not in have
                and not (
                    m["metric_name"].startswith(_TOOL_MATCH_PREFIX)
                    and any(h.startswith(_TOOL_MATCH_PREFIX) for h in have)
                )
            ]

            written = await _write_metrics(pool, trace_id, new)
            total_written += written
            total_traces += 1
            if total_traces % 25 == 0:
                log.info(
                    "Progress: %d traces processed, %d metric rows written",
                    total_traces,
                    total_written,
                )

        log.info(
            "Backfill done: %d traces scanned, %d metric rows inserted",
            total_traces,
            total_written,
        )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
