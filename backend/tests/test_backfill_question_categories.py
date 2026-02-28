from __future__ import annotations

import pytest

import scripts.backfill_question_categories as backfill


@pytest.mark.asyncio
async def test_backfill_question_categories_is_idempotent(monkeypatch):
    batches = [
        [
            {
                "trace_id": "trace-1",
                "inputs_json": {"question": "How do I foreclose my loan?"},
                "router_reason": "foreclosure_partpayment",
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
    assert row["question_category"] == "foreclosure_and_closure"
    assert row["question_category_source"] in {"keyword", "router_reason"}


@pytest.mark.asyncio
async def test_backfill_question_categories_dry_run_uses_count_only(monkeypatch):
    writes: list[dict] = []

    async def _connect():
        return None

    async def _close():
        return None

    async def _execute_read(_query: str, _params=None):
        return [{"total": 7}]

    async def _execute_write(_query: str, params=None):
        writes.append(params)
        return None

    monkeypatch.setattr(backfill.neo4j_mgr, "connect", _connect)
    monkeypatch.setattr(backfill.neo4j_mgr, "close", _close)
    monkeypatch.setattr(backfill.neo4j_mgr, "execute_read", _execute_read)
    monkeypatch.setattr(backfill.neo4j_mgr, "execute_write", _execute_write)

    total = await backfill.run(apply=False, batch_size=100)

    assert total == 7
    assert writes == []
