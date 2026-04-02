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
            {"reason": "Unknown", "n": 2},
        ]

    fake_pool = AsyncMock()
    fake_pool.fetch = _fake_fetch

    fake_request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pool=fake_pool)))

    result = await eval_read.question_types(request=fake_request, limit=50)

    assert "question_category" in captured["query"]
    assert result["total"] == 10
    assert result["items"][0]["reason"] == "loan_products_and_eligibility"
    assert result["items"][0]["pct"] == 0.8
