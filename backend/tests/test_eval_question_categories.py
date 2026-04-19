from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.agent_service.api import eval_read


@pytest.mark.asyncio
async def test_question_types_uses_canonical_category_field():
    captured: dict[str, object] = {}

    async def _fake_fetch(query: str, *args):
        captured["query"] = query
        return [
            {"reason": "loan_products_and_eligibility", "n": 8},
            {"reason": "other", "n": 2},
        ]

    fake_pool = AsyncMock()
    fake_pool.fetch = _fake_fetch

    fake_request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pool=fake_pool)))

    result = await eval_read.question_types(request=fake_request, limit=50)

    assert "question_category" in captured["query"]
    assert result["total"] == 10
    assert result["items"][0]["reason"] == "loan_products_and_eligibility"
    assert result["items"][0]["pct"] == 0.8


@pytest.mark.asyncio
async def test_question_types_aggregator_emits_canonical_other_slug():
    """Aggregator's NULL-fallback must be the canonical 'other' slug (not a display label).

    The trace-filter predicate in admin_analytics/repo.py falls back to 'other' when both
    question_category and router_reason_to_category resolve NULL. If the aggregator emits
    a different string (e.g. 'Unknown'), clicking the chart segment yields 0 matches.
    """
    captured: dict[str, object] = {}

    async def _fake_fetch(query: str, *args):
        captured["query"] = query
        return []

    fake_pool = AsyncMock()
    fake_pool.fetch = _fake_fetch
    fake_request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pool=fake_pool)))

    await eval_read.question_types(request=fake_request, limit=50)

    sql = captured["query"]
    assert isinstance(sql, str)
    # Fallback slug must be canonical — must round-trip back through the filter.
    assert "'other'" in sql
    assert "'Unknown'" not in sql
