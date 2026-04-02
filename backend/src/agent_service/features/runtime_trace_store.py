from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from prometheus_client import Counter, Histogram

from src.agent_service.eval_store.pg_store import EvalPgStore, get_shared_pool
from src.agent_service.features.question_category import classify_question_category

log = logging.getLogger("runtime_trace_store")

_STORE = EvalPgStore()

RUNTIME_TRACE_PERSIST_TOTAL = Counter(
    "agent_runtime_trace_persist_total",
    "Runtime trace persistence outcomes.",
    ["status"],
)

RUNTIME_TRACE_PERSIST_ATTEMPTS_TOTAL = Counter(
    "agent_runtime_trace_persist_attempts_total",
    "Total runtime trace persistence attempts.",
)

RUNTIME_TRACE_PERSIST_RETRIES_TOTAL = Counter(
    "agent_runtime_trace_persist_retries_total",
    "Total runtime trace persistence retries.",
)

RUNTIME_TRACE_PERSIST_DURATION_SECONDS = Histogram(
    "agent_runtime_trace_persist_duration_seconds",
    "Runtime trace persistence duration.",
    ["status"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0),
)


def _coerce_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def persist_runtime_trace(
    collector: Any,
    *,
    max_attempts: int = 3,
    initial_backoff_seconds: float = 0.05,
) -> bool:
    """Persist stream trace + events to Eval store with bounded retry."""

    started = time.perf_counter()
    session_id = str(getattr(collector, "session_id", "") or "").strip()

    try:
        trace = collector.build_trace_dict()
    except Exception as exc:  # noqa: BLE001
        RUNTIME_TRACE_PERSIST_TOTAL.labels(status="failure").inc()
        RUNTIME_TRACE_PERSIST_DURATION_SECONDS.labels(status="failure").observe(
            time.perf_counter() - started
        )
        log.exception("Failed to build runtime trace payload: %s", exc)
        return False

    trace_id = str(trace.get("trace_id") or getattr(collector, "trace_id", "")).strip()
    if not trace_id:
        RUNTIME_TRACE_PERSIST_TOTAL.labels(status="failure").inc()
        RUNTIME_TRACE_PERSIST_DURATION_SECONDS.labels(status="failure").observe(
            time.perf_counter() - started
        )
        log.error("Runtime trace payload missing trace_id; skipping persistence")
        return False

    events = list(getattr(collector, "events", []) or [])

    question = str((trace.get("inputs") or {}).get("question") or "").strip()
    router_reason = str(trace.get("router_reason") or "").strip() or None
    category = classify_question_category(question, router_reason)
    trace["question_category"] = category.category
    trace["question_category_confidence"] = category.confidence
    trace["question_category_source"] = category.source

    # Canonical inline guard fields must be persisted on EvalTrace for guardrail analytics.
    inline_guard = (
        ((trace.get("meta") or {}).get("inline_guard"))
        if isinstance(trace.get("meta"), dict)
        else None
    )
    if isinstance(inline_guard, dict):
        decision = str(inline_guard.get("decision") or "").strip() or None
        reason_code = str(inline_guard.get("reason_code") or "").strip() or None
        risk_score = _coerce_optional_float(inline_guard.get("risk_score"))
        trace["inline_guard_decision"] = decision
        trace["inline_guard_reason_code"] = reason_code
        trace["inline_guard_risk_score"] = risk_score
    else:
        trace["inline_guard_decision"] = None
        trace["inline_guard_reason_code"] = None
        trace["inline_guard_risk_score"] = None

    pool = get_shared_pool()
    if pool is None:
        RUNTIME_TRACE_PERSIST_TOTAL.labels(status="failure").inc()
        RUNTIME_TRACE_PERSIST_DURATION_SECONDS.labels(status="failure").observe(
            time.perf_counter() - started
        )
        log.error("Runtime trace persistence skipped: PostgreSQL pool not configured")
        return False

    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        RUNTIME_TRACE_PERSIST_ATTEMPTS_TOTAL.inc()
        try:
            await _STORE.upsert_trace(pool, trace)
            if events:
                await _STORE.upsert_events(pool, trace_id, events)

            elapsed = time.perf_counter() - started
            RUNTIME_TRACE_PERSIST_TOTAL.labels(status="success").inc()
            RUNTIME_TRACE_PERSIST_DURATION_SECONDS.labels(status="success").observe(elapsed)
            log.info(
                "Runtime trace persisted session_id=%s trace_id=%s attempts=%s events=%s elapsed_ms=%.2f",
                session_id,
                trace_id,
                attempt,
                len(events),
                elapsed * 1000,
            )
            return True
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            log.warning(
                "Runtime trace persist attempt %s/%s failed for trace_id=%s: %s",
                attempt,
                max_attempts,
                trace_id,
                exc,
            )
            if attempt < max_attempts:
                RUNTIME_TRACE_PERSIST_RETRIES_TOTAL.inc()
                await asyncio.sleep(initial_backoff_seconds * attempt)

    elapsed = time.perf_counter() - started
    RUNTIME_TRACE_PERSIST_TOTAL.labels(status="failure").inc()
    RUNTIME_TRACE_PERSIST_DURATION_SECONDS.labels(status="failure").observe(elapsed)
    if last_error is not None:
        log.error(
            "Runtime trace persistence failed session_id=%s trace_id=%s attempts=%s elapsed_ms=%.2f error=%s",
            session_id,
            trace_id,
            max_attempts,
            elapsed * 1000,
            last_error,
        )
    return False
