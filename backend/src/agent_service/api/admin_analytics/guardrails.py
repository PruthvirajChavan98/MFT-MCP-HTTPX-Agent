"""Guardrails analytics endpoints: events, summary, trends, queue-health, judge-summary."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from prometheus_client import Counter, Histogram

from src.agent_service.api.admin_auth import require_admin
from src.agent_service.core.config import SHADOW_TRACE_DLQ_KEY, SHADOW_TRACE_QUEUE_KEY
from src.agent_service.core.session_utils import get_redis

from .repo import analytics_repo
from .utils import _coerce_guardrail_float, _json_load_maybe, _parse_iso_timestamp

router = APIRouter(
    prefix="/agent/admin/analytics",
    tags=["admin-analytics"],
    dependencies=[Depends(require_admin)],
)
logger = logging.getLogger(__name__)

ADMIN_GUARDRAILS_QUERY_DURATION_SECONDS = Histogram(
    "agent_admin_guardrails_query_duration_seconds",
    "Guardrails analytics query latency.",
    ["endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

ADMIN_GUARDRAILS_QUERY_TOTAL = Counter(
    "agent_admin_guardrails_query_total",
    "Guardrails analytics query outcomes.",
    ["endpoint", "status"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _risk_level(score: float) -> str:
    if score >= 0.8:
        return "critical"
    if score >= 0.5:
        return "high"
    if score >= 0.3:
        return "medium"
    return "low"


def _extract_inline_guard_fields(row: dict[str, Any]) -> tuple[str | None, str | None, float]:
    decision = str(row.get("inline_guard_decision") or "").strip() or None
    reason_code = str(row.get("inline_guard_reason_code") or "").strip() or None
    risk_score = _coerce_guardrail_float(row.get("inline_guard_risk_score"), 0.0)

    if decision:
        return decision, reason_code, risk_score

    meta_obj = _json_load_maybe(row.get("meta_json"))
    inline_guard = meta_obj.get("inline_guard") if isinstance(meta_obj, dict) else None
    if isinstance(inline_guard, dict):
        decision = str(inline_guard.get("decision") or "").strip() or None
        reason_code = str(inline_guard.get("reason_code") or "").strip() or None
        risk_score = _coerce_guardrail_float(inline_guard.get("risk_score"), risk_score)
    return decision, reason_code, risk_score


def _as_guardrail_event(row: dict[str, Any]) -> dict[str, Any] | None:
    decision, reason_code, risk_score = _extract_inline_guard_fields(row)
    if not decision:
        return None

    event_time = _parse_iso_timestamp(row.get("started_at"))
    event_time_iso = event_time.isoformat() if event_time else None

    reasons: list[str] = [reason_code] if reason_code else []
    return {
        "trace_id": row.get("trace_id"),
        "event_time": event_time_iso,
        "session_id": row.get("session_id"),
        "risk_score": risk_score,
        "risk_decision": decision,
        "severity": _risk_level(risk_score),
        "request_path": row.get("endpoint"),
        "reasons": reasons,
    }


def _log_guardrails_query_failure(
    *,
    endpoint: str,
    tenant_id: str,
    exc: Exception,
    hours: int | None = None,
) -> None:
    logger.exception(
        "Guardrails analytics query failed",
        extra={
            "endpoint": endpoint,
            "tenant_id": tenant_id,
            "hours": hours,
            "error_class": exc.__class__.__name__,
            "error": str(exc),
        },
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/guardrails")
async def guardrails(
    request: Request,
    tenant_id: str = Query(default="default", description="Tenant ID to filter RLS policies"),
    decision: str | None = Query(default=None, description="Optional risk decision filter"),
    min_risk: float | None = Query(default=None, ge=0.0, le=1.0),
    session_id: str | None = Query(default=None),
    start: datetime | None = Query(default=None, description="ISO timestamp lower bound"),
    end: datetime | None = Query(default=None, description="ISO timestamp upper bound"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=120, ge=1, le=1000),
):
    endpoint = "guardrails_events"
    status = "success"
    started = time.perf_counter()

    try:
        pool = request.app.state.pool
        fetch_cap = min(max(offset + limit + 1000, 2000), 10000)
        rows = await analytics_repo.fetch_guardrail_trace_rows(
            pool,
            limit=fetch_cap,
            tenant_id=tenant_id,
            session_id=session_id.strip() if session_id else None,
            start=start,
            end=end,
        )
        events = [evt for row in rows if (evt := _as_guardrail_event(row)) is not None]

        decision_filter = (decision or "").strip().lower()
        if decision_filter and decision_filter != "all":
            events = [
                evt
                for evt in events
                if str(evt.get("risk_decision", "")).lower() == decision_filter
            ]

        if min_risk is not None:
            events = [
                evt for evt in events if _coerce_guardrail_float(evt.get("risk_score")) >= min_risk
            ]

        total = len(events)
        items = events[offset : offset + limit]
        return {
            "items": items,
            "count": len(items),
            "total": total,
            "offset": offset,
            "limit": limit,
        }
    except HTTPException:
        raise
    except Exception as exc:
        status = "error"
        _log_guardrails_query_failure(endpoint=endpoint, tenant_id=tenant_id, exc=exc)
        raise HTTPException(status_code=503, detail="Guardrail analytics unavailable") from exc
    finally:
        ADMIN_GUARDRAILS_QUERY_TOTAL.labels(endpoint=endpoint, status=status).inc()
        ADMIN_GUARDRAILS_QUERY_DURATION_SECONDS.labels(endpoint=endpoint).observe(
            time.perf_counter() - started
        )


@router.get("/guardrails/summary")
async def guardrails_summary(
    request: Request,
    tenant_id: str = Query(default="default"),
):
    endpoint = "guardrails_summary"
    status = "success"
    started = time.perf_counter()
    try:
        pool = request.app.state.pool
        rows = await analytics_repo.fetch_guardrail_trace_rows(
            pool, limit=20000, tenant_id=tenant_id
        )
        events = [evt for row in rows if (evt := _as_guardrail_event(row)) is not None]

        total_events = len(events)
        deny_events = sum(
            1
            for evt in events
            if any(
                token in str(evt.get("risk_decision", "")).lower() for token in ("deny", "block")
            )
        )
        avg_risk_score = (
            sum(_coerce_guardrail_float(evt.get("risk_score")) for evt in events) / total_events
            if total_events
            else 0.0
        )
        return {
            "total_events": total_events,
            "deny_events": deny_events,
            "allow_events": max(0, total_events - deny_events),
            "deny_rate": (deny_events / total_events) if total_events else 0.0,
            "avg_risk_score": avg_risk_score,
        }
    except HTTPException:
        raise
    except Exception as exc:
        status = "error"
        _log_guardrails_query_failure(endpoint=endpoint, tenant_id=tenant_id, exc=exc)
        raise HTTPException(status_code=503, detail="Guardrail analytics unavailable") from exc
    finally:
        ADMIN_GUARDRAILS_QUERY_TOTAL.labels(endpoint=endpoint, status=status).inc()
        ADMIN_GUARDRAILS_QUERY_DURATION_SECONDS.labels(endpoint=endpoint).observe(
            time.perf_counter() - started
        )


@router.get("/guardrails/trends")
async def guardrails_trends(
    request: Request,
    tenant_id: str = Query(default="default"),
    hours: int = Query(default=24, ge=1, le=24 * 14),
):
    endpoint = "guardrails_trends"
    status = "success"
    started = time.perf_counter()
    try:
        pool = request.app.state.pool
        start = datetime.now(timezone.utc) - timedelta(hours=hours)
        rows = await analytics_repo.fetch_guardrail_trace_rows(
            pool,
            limit=20000,
            tenant_id=tenant_id,
            start=start,
        )
        buckets: dict[str, dict[str, float | int]] = {}
        for row in rows:
            event = _as_guardrail_event(row)
            if not event:
                continue
            event_time = _parse_iso_timestamp(event.get("event_time"))
            if event_time is None:
                continue
            bucket_dt = event_time.astimezone(timezone.utc).replace(
                minute=0,
                second=0,
                microsecond=0,
            )
            bucket_key = bucket_dt.isoformat()
            agg = buckets.setdefault(
                bucket_key,
                {"total_events": 0, "deny_events": 0, "avg_risk_sum": 0.0},
            )
            agg["total_events"] = int(agg["total_events"]) + 1
            decision_text = str(event.get("risk_decision", "")).lower()
            if "deny" in decision_text or "block" in decision_text:
                agg["deny_events"] = int(agg["deny_events"]) + 1
            agg["avg_risk_sum"] = float(agg["avg_risk_sum"]) + _coerce_guardrail_float(
                event.get("risk_score")
            )

        items = []
        for bucket_key, agg in sorted(buckets.items(), key=lambda item: item[0]):
            total_events = int(agg["total_events"])
            avg_risk_score = (float(agg["avg_risk_sum"]) / total_events) if total_events else 0.0
            items.append(
                {
                    "bucket": bucket_key,
                    "total_events": total_events,
                    "deny_events": int(agg["deny_events"]),
                    "avg_risk_score": avg_risk_score,
                }
            )
        return {
            "items": items,
            "hours": hours,
        }
    except HTTPException:
        raise
    except Exception as exc:
        status = "error"
        _log_guardrails_query_failure(endpoint=endpoint, tenant_id=tenant_id, hours=hours, exc=exc)
        raise HTTPException(status_code=503, detail="Guardrail analytics unavailable") from exc
    finally:
        ADMIN_GUARDRAILS_QUERY_TOTAL.labels(endpoint=endpoint, status=status).inc()
        ADMIN_GUARDRAILS_QUERY_DURATION_SECONDS.labels(endpoint=endpoint).observe(
            time.perf_counter() - started
        )


@router.get("/guardrails/queue-health")
async def guardrails_queue_health():
    redis = await get_redis()
    depth = int(await redis.llen(SHADOW_TRACE_QUEUE_KEY))  # type: ignore[misc]
    dead_letter_depth = int(await redis.llen(SHADOW_TRACE_DLQ_KEY))  # type: ignore[misc]
    oldest = await redis.lindex(SHADOW_TRACE_QUEUE_KEY, -1)  # type: ignore[misc]

    oldest_age_seconds: int | None = None
    if oldest:
        try:
            payload = json.loads(oldest)
            enqueued_at_raw = payload.get("enqueued_at")
            if isinstance(enqueued_at_raw, str) and enqueued_at_raw:
                normalized = enqueued_at_raw.replace("Z", "+00:00")
                enqueued_at = datetime.fromisoformat(normalized)
                oldest_age_seconds = max(
                    0, int((datetime.now(timezone.utc) - enqueued_at).total_seconds())
                )
        except Exception as exc:
            logger.debug("Failed to parse oldest queue entry age: %s", exc)
            oldest_age_seconds = None

    return {
        "queue_key": SHADOW_TRACE_QUEUE_KEY,
        "depth": depth,
        "dead_letter_queue_key": SHADOW_TRACE_DLQ_KEY,
        "dead_letter_depth": dead_letter_depth,
        "oldest_age_seconds": oldest_age_seconds,
    }


@router.get("/guardrails/judge-summary")
async def guardrails_judge_summary(
    request: Request,
    limit_failures: int = Query(default=20, ge=1, le=100),
):
    pool = request.app.state.pool
    aggregate_rows = await analytics_repo.fetch_shadow_judge_aggregates(pool)
    failure_rows = await analytics_repo.fetch_shadow_judge_failures(pool, limit_failures)

    row = aggregate_rows[0] if aggregate_rows else {}
    return {
        "total_evals": int(row.get("total_evals") or 0),
        "avg_helpfulness": float(row.get("avg_helpfulness") or 0.0),
        "avg_faithfulness": float(row.get("avg_faithfulness") or 0.0),
        "avg_policy_adherence": float(row.get("avg_policy_adherence") or 0.0),
        "recent_failures": failure_rows,
    }
