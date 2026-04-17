"""Tests for the `category` filter on GET /agent/admin/analytics/traces.

Guards the end-to-end contract between the QuestionCategories "View Traces"
link and the traces endpoint. Before this filter shipped, clicking a category
on the categories page navigated to /admin/traces?search=<slug> and returned
zero results — the endpoint only did free-text search and ignored the
category taxonomy. These tests pin:

1. The SQL query the repo emits actually contains the router_reason →
   category CASE mapping so the filter hits both `question_category` and
   derived slugs.
2. The category SQL param is positional index 4 (shifted cursor to 5/6, limit to 7).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.agent_service.api.admin_analytics import repo as repo_module
from src.agent_service.api.admin_analytics import traces as traces_module
from src.agent_service.api.admin_analytics.category_map import (
    ROUTER_REASON_TO_CATEGORY_CASE,
)


@pytest.mark.asyncio
async def test_repo_fetch_traces_page_injects_category_case_mapping() -> None:
    """The generated SQL contains the shared CASE expression so router_reason
    values like 'lead_intent_new_loan' resolve to the 'loan_products_and_eligibility'
    slug and match the filter without explicitly storing question_category."""
    captured: dict[str, object] = {}

    async def _fake_pg_rows(pool, sql, *args):
        captured["sql"] = sql
        captured["args"] = args
        return []

    # Monkey-patch the pg rows executor to capture the exact SQL + args.
    original = repo_module._pg_rows
    repo_module._pg_rows = _fake_pg_rows
    try:
        await repo_module.analytics_repo.fetch_traces_page(
            pool=AsyncMock(),
            status=None,
            model=None,
            search_pat=None,
            category="loan_products_and_eligibility",
            cursor_started_at=None,
            cursor_trace_id="",
            limit=50,
        )
    finally:
        repo_module._pg_rows = original

    sql = captured["sql"]
    assert isinstance(sql, str)

    # The shared CASE expression must be embedded in the generated SQL.
    assert ROUTER_REASON_TO_CATEGORY_CASE in sql, (
        "fetch_traces_page must inline the shared router_reason→category mapping "
        "so the category filter matches traces whose question_category is unset "
        "but whose router_reason maps to the requested slug."
    )
    assert "question_category = $4" in sql
    # Cursor shifted to positions 5/6 and limit to 7 after adding the category param.
    assert "started_at < $5" in sql
    assert "LIMIT $7" in sql

    # Category passed through as the 4th positional arg.
    args = captured["args"]
    assert args[3] == "loan_products_and_eligibility"


@pytest.mark.asyncio
async def test_traces_endpoint_forwards_category_to_repo() -> None:
    """The HTTP handler normalises + forwards the `category` Query param."""
    captured: dict[str, object] = {}

    async def _fake_fetch_traces_page(pool, *, category, **kwargs):
        captured["category"] = category
        captured["kwargs"] = kwargs
        return []

    original = traces_module.analytics_repo.fetch_traces_page
    traces_module.analytics_repo.fetch_traces_page = _fake_fetch_traces_page
    try:
        fake_request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pool=AsyncMock())))
        await traces_module.traces(
            request=fake_request,
            limit=10,
            cursor=None,
            search=None,
            status=None,
            model=None,
            category="  loan_products_and_eligibility  ",  # whitespace gets stripped
        )
    finally:
        traces_module.analytics_repo.fetch_traces_page = original

    assert captured["category"] == "loan_products_and_eligibility"


@pytest.mark.asyncio
async def test_traces_endpoint_treats_empty_category_as_none() -> None:
    """Empty/whitespace-only category must become None so the filter is bypassed."""
    captured: dict[str, object] = {}

    async def _fake_fetch_traces_page(pool, *, category, **kwargs):
        captured["category"] = category
        return []

    original = traces_module.analytics_repo.fetch_traces_page
    traces_module.analytics_repo.fetch_traces_page = _fake_fetch_traces_page
    try:
        fake_request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pool=AsyncMock())))
        await traces_module.traces(
            request=fake_request,
            limit=10,
            cursor=None,
            search=None,
            status=None,
            model=None,
            category="   ",
        )
    finally:
        traces_module.analytics_repo.fetch_traces_page = original

    assert captured["category"] is None
