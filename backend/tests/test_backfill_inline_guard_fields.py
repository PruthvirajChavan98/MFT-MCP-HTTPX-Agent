from __future__ import annotations

import pytest

import scripts.backfill_inline_guard_fields as backfill


@pytest.mark.asyncio
async def test_backfill_inline_guard_fields_is_idempotent(monkeypatch):
    batches = [
        [
            {
                "trace_id": "trace-1",
                "meta_json": {
                    "inline_guard": {
                        "decision": "degraded_allow",
                        "reason_code": "infra_degraded",
                        "risk_score": 0.12,
                    }
                },
            }
        ],
        [],
    ]
    writes: list[dict] = []

    async def _connect():
        return None

    async def _close():
        return None

    async def _execute_read(_query: str, _params=None):
        return batches.pop(0)

    async def _execute_write(_query: str, params=None):
        writes.append(params)
        return None

    monkeypatch.setattr(backfill.neo4j_mgr, "connect", _connect)
    monkeypatch.setattr(backfill.neo4j_mgr, "close", _close)
    monkeypatch.setattr(backfill.neo4j_mgr, "execute_read", _execute_read)
    monkeypatch.setattr(backfill.neo4j_mgr, "execute_write", _execute_write)

    total = await backfill.run(apply=True, batch_size=100)

    assert total == 1
    assert len(writes) == 1
    row = writes[0]["rows"][0]
    assert row["trace_id"] == "trace-1"
    assert row["inline_guard_decision"] == "degraded_allow"
    assert row["inline_guard_reason_code"] == "infra_degraded"
    assert row["inline_guard_risk_score"] == 0.12


@pytest.mark.asyncio
async def test_backfill_inline_guard_fields_dry_run_uses_count_only(monkeypatch):
    writes: list[dict] = []

    async def _connect():
        return None

    async def _close():
        return None

    async def _execute_read(_query: str, _params=None):
        return [{"total": 3}]

    async def _execute_write(_query: str, params=None):
        writes.append(params)
        return None

    monkeypatch.setattr(backfill.neo4j_mgr, "connect", _connect)
    monkeypatch.setattr(backfill.neo4j_mgr, "close", _close)
    monkeypatch.setattr(backfill.neo4j_mgr, "execute_read", _execute_read)
    monkeypatch.setattr(backfill.neo4j_mgr, "execute_write", _execute_write)

    total = await backfill.run(apply=False, batch_size=100)

    assert total == 3
    assert writes == []
