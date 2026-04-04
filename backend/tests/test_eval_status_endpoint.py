"""Tests for GET /eval/trace/{trace_id}/eval-status endpoint."""

from __future__ import annotations

import importlib
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.agent_service.api import eval_read
from src.agent_service.api.eval_read import trace_eval_status


def _make_request(pool: AsyncMock) -> SimpleNamespace:
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pool=pool)))


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _trace_row(
    *,
    trace_id: str = "trace-1",
    meta_json: dict | None = None,
    ended_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> dict[str, object]:
    now = datetime.now(timezone.utc)
    return {
        "trace_id": trace_id,
        "meta_json": meta_json or {},
        "ended_at": ended_at or now,
        "updated_at": updated_at or now,
    }


def _pool_for(
    *,
    trace_row: dict[str, object] | None,
    result_rows: list[dict[str, object]] | None = None,
    shadow_row: dict[str, object] | None = None,
) -> AsyncMock:
    pool = AsyncMock()
    if trace_row is None:
        pool.fetchrow = AsyncMock(return_value=None)
    else:
        pool.fetchrow = AsyncMock(side_effect=[trace_row, shadow_row])
    pool.fetch = AsyncMock(return_value=result_rows or [])
    return pool


@pytest.mark.asyncio
async def test_trace_not_found_returns_not_found_status():
    pool = _pool_for(trace_row=None)
    request = _make_request(pool)

    result = await trace_eval_status(request, trace_id="missing")

    assert result == {
        "trace_id": "missing",
        "status": "not_found",
        "reason": None,
        "inline_evals": None,
        "shadow_judge": None,
    }
    pool.fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_trace_without_lifecycle_is_pending_during_grace_window():
    recent = datetime.now(timezone.utc)
    pool = _pool_for(trace_row=_trace_row(updated_at=recent, ended_at=recent))
    request = _make_request(pool)

    result = await trace_eval_status(request, trace_id="trace-grace")

    assert result["status"] == "pending"
    assert result["reason"] == "queued"


@pytest.mark.asyncio
async def test_trace_without_lifecycle_becomes_unavailable_after_grace_window():
    stale = datetime.now(timezone.utc) - timedelta(
        seconds=eval_read._TRACE_STATUS_GRACE_SECONDS + 5
    )
    pool = _pool_for(trace_row=_trace_row(updated_at=stale, ended_at=stale))
    request = _make_request(pool)

    result = await trace_eval_status(request, trace_id="trace-stale")

    assert result["status"] == "unavailable"
    assert result["reason"] is None


@pytest.mark.asyncio
async def test_trace_returns_pending_when_shadow_judge_is_queued():
    queued_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    pool = _pool_for(
        trace_row=_trace_row(
            meta_json={
                "eval_lifecycle": {
                    "shadow": {"state": "queued", "queued_at": _iso(queued_at)},
                }
            },
            updated_at=queued_at,
            ended_at=queued_at,
        )
    )
    request = _make_request(pool)

    result = await trace_eval_status(request, trace_id="trace-queued")

    assert result["status"] == "pending"
    assert result["reason"] == "queued"


@pytest.mark.asyncio
async def test_trace_returns_worker_backlog_for_old_queued_shadow_judge():
    queued_at = datetime.now(timezone.utc) - timedelta(
        seconds=eval_read._SHADOW_WORKER_BACKLOG_SECONDS + 5
    )
    pool = _pool_for(
        trace_row=_trace_row(
            meta_json={
                "eval_lifecycle": {
                    "shadow": {"state": "queued", "queued_at": _iso(queued_at)},
                }
            },
            updated_at=queued_at,
            ended_at=queued_at,
        )
    )
    request = _make_request(pool)

    result = await trace_eval_status(request, trace_id="trace-backlog")

    assert result["status"] == "pending"
    assert result["reason"] == "worker_backlog"


@pytest.mark.asyncio
async def test_trace_returns_timed_out_for_stale_queued_shadow_judge():
    queued_at = datetime.now(timezone.utc) - timedelta(
        seconds=eval_read._SHADOW_TIMED_OUT_SECONDS + 5
    )
    pool = _pool_for(
        trace_row=_trace_row(
            meta_json={
                "eval_lifecycle": {
                    "shadow": {"state": "queued", "queued_at": _iso(queued_at)},
                }
            },
            updated_at=queued_at,
            ended_at=queued_at,
        )
    )
    request = _make_request(pool)

    result = await trace_eval_status(request, trace_id="trace-timeout")

    assert result["status"] == "unavailable"
    assert result["reason"] == "timed_out"


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["disabled", "sampled_out", "failed"])
async def test_trace_returns_unavailable_for_terminal_inline_reasons(reason: str):
    stale = datetime.now(timezone.utc) - timedelta(
        seconds=eval_read._TRACE_STATUS_GRACE_SECONDS + 5
    )
    pool = _pool_for(
        trace_row=_trace_row(
            meta_json={
                "eval_lifecycle": {
                    "inline": {"state": reason, "reason": reason},
                    "shadow": {"state": "disabled", "reason": "disabled"},
                }
            },
            updated_at=stale,
            ended_at=stale,
        )
    )
    request = _make_request(pool)

    result = await trace_eval_status(request, trace_id=f"trace-{reason}")

    assert result["status"] == "unavailable"
    assert result["reason"] == reason


@pytest.mark.asyncio
async def test_complete_with_inline_evals_only():
    pool = _pool_for(
        trace_row=_trace_row(),
        result_rows=[
            {"metric_name": "faithfulness", "score": 0.95, "passed": True},
            {"metric_name": "hallucination", "score": 0.1, "passed": False},
            {"metric_name": "relevance", "score": 0.88, "passed": True},
        ],
    )
    request = _make_request(pool)

    result = await trace_eval_status(request, trace_id="trace-inline")

    assert result["status"] == "complete"
    assert result["reason"] is None
    assert result["shadow_judge"] is None
    assert result["inline_evals"] == {
        "count": 3,
        "passed": 2,
        "failed": 1,
        "metrics": [
            {"metric_name": "faithfulness", "score": 0.95, "passed": True},
            {"metric_name": "hallucination", "score": 0.1, "passed": False},
            {"metric_name": "relevance", "score": 0.88, "passed": True},
        ],
    }


@pytest.mark.asyncio
async def test_complete_with_shadow_judge_only():
    evaluated_at = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
    pool = _pool_for(
        trace_row=_trace_row(),
        shadow_row={
            "helpfulness": 0.9,
            "faithfulness": 0.85,
            "policy_adherence": 0.92,
            "summary": "Good response overall.",
            "evaluated_at": evaluated_at,
        },
    )
    request = _make_request(pool)

    result = await trace_eval_status(request, trace_id="trace-shadow")

    assert result["status"] == "complete"
    assert result["reason"] is None
    assert result["inline_evals"] is None
    assert result["shadow_judge"] == {
        "helpfulness": 0.9,
        "faithfulness": 0.85,
        "policy_adherence": 0.92,
        "summary": "Good response overall.",
        "evaluated_at": evaluated_at.isoformat(),
    }


@pytest.mark.asyncio
async def test_status_helper_keeps_eval_status_endpoint_contract():
    trace_row = _trace_row(
        trace_id="trace-helper",
        meta_json={
            "eval_lifecycle": {
                "shadow": {"state": "queued", "queued_at": _iso(datetime.now(timezone.utc))},
            }
        },
    )

    payload = eval_read.build_eval_status_payload(
        trace_id="trace-helper",
        trace_row=trace_row,
        result_rows=[],
        shadow_row=None,
    )

    assert payload == {
        "trace_id": "trace-helper",
        "status": "pending",
        "reason": "queued",
        "inline_evals": None,
        "shadow_judge": None,
    }


@pytest.mark.asyncio
async def test_db_error_raises_http_exception():
    pool = AsyncMock()
    pool.fetchrow = AsyncMock(side_effect=ConnectionError("connection refused"))
    request = _make_request(pool)

    with pytest.raises(HTTPException) as exc_info:
        await trace_eval_status(request, trace_id="trace-error")

    assert exc_info.value.status_code == 503
    assert "Database unavailable" in exc_info.value.detail
    assert "trace_eval_status" in exc_info.value.detail
    assert "connection refused" in exc_info.value.detail


def test_enable_llm_judge_accepts_numeric_truthy(monkeypatch: pytest.MonkeyPatch):
    from src.agent_service.core import config as config_module
    from src.agent_service.features import shadow_eval as shadow_eval_module

    original = os.environ.get("ENABLE_LLM_JUDGE")
    try:
        monkeypatch.setenv("ENABLE_LLM_JUDGE", "1")
        importlib.reload(config_module)
        importlib.reload(shadow_eval_module)
        assert config_module.ENABLE_LLM_JUDGE is True
        assert shadow_eval_module.ENABLE_LLM_JUDGE is True
    finally:
        if original is None:
            monkeypatch.delenv("ENABLE_LLM_JUDGE", raising=False)
        else:
            monkeypatch.setenv("ENABLE_LLM_JUDGE", original)
        importlib.reload(config_module)
        importlib.reload(shadow_eval_module)
