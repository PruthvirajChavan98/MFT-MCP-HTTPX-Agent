from __future__ import annotations

import pytest

from src.agent_service.api import eval_read


@pytest.mark.asyncio
async def test_question_types_uses_canonical_category_field(monkeypatch):
    captured: dict[str, str] = {}

    async def _fake_schema(_operation: str) -> None:
        return None

    async def _fake_rows(query: str, params: dict, operation: str):
        captured["query"] = query
        assert params["limit"] == 50
        assert operation == "eval_question_types"
        return [
            {"reason": "loan_products_and_eligibility", "n": 8},
            {"reason": "Unknown", "n": 2},
        ]

    monkeypatch.setattr(eval_read, "_ensure_eval_schema", _fake_schema)
    monkeypatch.setattr(eval_read, "_run_rows_query", _fake_rows)

    result = await eval_read.question_types(limit=50)

    assert "question_category" in captured["query"]
    assert result["total"] == 10
    assert result["items"][0]["reason"] == "loan_products_and_eligibility"
    assert result["items"][0]["pct"] == 0.8
