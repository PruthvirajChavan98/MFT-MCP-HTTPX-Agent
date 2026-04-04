from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from src.agent_service.core.config import SHADOW_JUDGE_POLL_SECONDS

TRACE_STATUS_GRACE_SECONDS = 15
SHADOW_WORKER_BACKLOG_SECONDS = max(2 * SHADOW_JUDGE_POLL_SECONDS, 120)
SHADOW_TIMED_OUT_SECONDS = max(10 * SHADOW_JUDGE_POLL_SECONDS, 600)


def json_load_maybe(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return value
    if (stripped.startswith("{") and stripped.endswith("}")) or (
        stripped.startswith("[") and stripped.endswith("]")
    ):
        try:
            return json.loads(stripped)
        except Exception:
            return value
    return value


def coerce_dt(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def eval_lifecycle_branch(meta_json: Any, branch: str) -> dict[str, Any]:
    meta = json_load_maybe(meta_json)
    if not isinstance(meta, dict):
        return {}
    lifecycle = meta.get("eval_lifecycle")
    if not isinstance(lifecycle, dict):
        return {}
    branch_payload = lifecycle.get(branch)
    return branch_payload if isinstance(branch_payload, dict) else {}


def build_inline_evals(result_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not result_rows:
        return None

    metrics = [
        {
            "metric_name": row["metric_name"],
            "score": float(row["score"]) if row["score"] is not None else None,
            "passed": bool(row["passed"]) if row["passed"] is not None else None,
        }
        for row in result_rows
    ]
    passed_count = sum(1 for metric in metrics if metric["passed"] is True)
    failed_count = sum(1 for metric in metrics if metric["passed"] is False)
    return {
        "count": len(metrics),
        "passed": passed_count,
        "failed": failed_count,
        "metrics": metrics,
    }


def build_shadow_judge(shadow_row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not shadow_row:
        return None

    return {
        "helpfulness": (
            float(shadow_row["helpfulness"]) if shadow_row["helpfulness"] is not None else None
        ),
        "faithfulness": (
            float(shadow_row["faithfulness"]) if shadow_row["faithfulness"] is not None else None
        ),
        "policy_adherence": (
            float(shadow_row["policy_adherence"])
            if shadow_row["policy_adherence"] is not None
            else None
        ),
        "summary": shadow_row["summary"],
        "evaluated_at": (
            shadow_row["evaluated_at"].isoformat() if shadow_row["evaluated_at"] else None
        ),
    }


def derive_eval_status(
    trace_row: dict[str, Any],
    *,
    has_inline: bool,
    has_shadow: bool,
) -> tuple[str, str | None]:
    if has_inline or has_shadow:
        return "complete", None

    inline_branch = eval_lifecycle_branch(trace_row.get("meta_json"), "inline")
    shadow_branch = eval_lifecycle_branch(trace_row.get("meta_json"), "shadow")

    inline_state = str(inline_branch.get("state") or "").strip().lower() or None
    shadow_state = str(shadow_branch.get("state") or "").strip().lower() or None

    now = datetime.now(timezone.utc)
    trace_updated_at = coerce_dt(trace_row.get("updated_at"))
    trace_ended_at = coerce_dt(trace_row.get("ended_at"))
    recent_ref = trace_updated_at or trace_ended_at
    recent_age_seconds = (
        (now - recent_ref).total_seconds()
        if recent_ref is not None
        else SHADOW_TIMED_OUT_SECONDS + 1
    )

    if shadow_state == "queued":
        queue_ref = coerce_dt(shadow_branch.get("queued_at")) or recent_ref
        queued_age_seconds = (
            (now - queue_ref).total_seconds()
            if queue_ref is not None
            else SHADOW_TIMED_OUT_SECONDS + 1
        )
        if queued_age_seconds >= SHADOW_TIMED_OUT_SECONDS:
            return "unavailable", "timed_out"
        if queued_age_seconds >= SHADOW_WORKER_BACKLOG_SECONDS:
            return "pending", "worker_backlog"
        return "pending", "queued"

    if recent_age_seconds < TRACE_STATUS_GRACE_SECONDS and inline_state is None:
        return "pending", "queued"

    if inline_state == "complete" or shadow_state == "complete":
        if recent_age_seconds < TRACE_STATUS_GRACE_SECONDS:
            return "pending", "queued"
        return "unavailable", None

    for reason in (
        inline_branch.get("reason"),
        inline_state,
        shadow_branch.get("reason"),
        shadow_state,
    ):
        normalized = str(reason or "").strip().lower() or None
        if normalized in {"disabled", "sampled_out", "failed", "timed_out"}:
            return "unavailable", normalized

    return "unavailable", None


def build_eval_status_payload(
    *,
    trace_id: str,
    trace_row: dict[str, Any] | None,
    result_rows: list[dict[str, Any]] | None = None,
    shadow_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if trace_row is None:
        return {
            "trace_id": trace_id,
            "status": "not_found",
            "reason": None,
            "inline_evals": None,
            "shadow_judge": None,
        }

    inline_evals = build_inline_evals(result_rows or [])
    shadow_judge = build_shadow_judge(shadow_row)
    status, reason = derive_eval_status(
        dict(trace_row),
        has_inline=inline_evals is not None,
        has_shadow=shadow_judge is not None,
    )
    return {
        "trace_id": trace_id,
        "status": status,
        "reason": reason,
        "inline_evals": inline_evals,
        "shadow_judge": shadow_judge,
    }
