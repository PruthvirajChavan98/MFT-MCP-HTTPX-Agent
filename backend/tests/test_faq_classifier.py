"""Tests for src.agent_service.features.faq_classifier."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agent_service.features import faq_classifier

CATEGORY_LABELS = ["billing", "account", "data", "technical", "sales"]

_SYSTEM_PROMPT_STUB = (
    "You are an FAQ categorizer for a fintech NBFC company. "
    "Classify each FAQ into exactly one of the provided categories."
)


def _make_items(*categories: str) -> list[dict[str, Any]]:
    """Build FAQ items, one per category string (empty = needs classification)."""
    items: list[dict[str, Any]] = []
    for i, cat in enumerate(categories):
        items.append(
            {
                "question": f"Question {i}",
                "answer": f"Answer {i}",
                "category": cat,
            }
        )
    return items


def _groq_response_body(classifications: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a mock Groq chat/completions response body."""
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps({"classifications": classifications}),
                }
            }
        ],
    }


def _mock_http_response(body: dict[str, Any], status_code: int = 200) -> MagicMock:
    """Create a mock httpx.Response with synchronous .json() and .raise_for_status().

    httpx.Response.json() and .raise_for_status() are synchronous methods,
    so we use MagicMock (not AsyncMock) to avoid returning coroutines.
    """
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = body
    response.raise_for_status.return_value = None
    return response


# ---------- 1. Successful classification ----------


@pytest.mark.asyncio
async def test_classify_faqs_populates_categories(monkeypatch: pytest.MonkeyPatch) -> None:
    items = _make_items("", "", "")

    groq_body = _groq_response_body(
        [
            {"index": 0, "category": "billing"},
            {"index": 1, "category": "sales"},
            {"index": 2, "category": "account"},
        ]
    )

    mock_client = AsyncMock()
    mock_client.post.return_value = _mock_http_response(groq_body)

    monkeypatch.setattr(faq_classifier, "GROQ_API_KEYS", ["fake-key"])
    monkeypatch.setattr(faq_classifier, "get_http_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr(
        faq_classifier.prompt_manager, "get_template", lambda *_a, **_kw: _SYSTEM_PROMPT_STUB
    )

    result = await faq_classifier.classify_faqs(items, CATEGORY_LABELS)

    assert result[0]["category"] == "billing"
    assert result[1]["category"] == "sales"
    assert result[2]["category"] == "account"
    # Original items are not mutated
    assert items[0]["category"] == ""


# ---------- 2. Groq failure — items returned unchanged ----------


@pytest.mark.asyncio
async def test_classify_faqs_returns_unchanged_on_groq_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    items = _make_items("", "")

    mock_client = AsyncMock()
    mock_client.post.side_effect = RuntimeError("Groq is down")

    monkeypatch.setattr(faq_classifier, "GROQ_API_KEYS", ["fake-key"])
    monkeypatch.setattr(faq_classifier, "get_http_client", AsyncMock(return_value=mock_client))

    result = await faq_classifier.classify_faqs(items, CATEGORY_LABELS)

    assert result[0]["category"] == ""
    assert result[1]["category"] == ""


# ---------- 3. Partial response — only some items classified ----------


@pytest.mark.asyncio
async def test_classify_faqs_handles_partial_response(monkeypatch: pytest.MonkeyPatch) -> None:
    items = _make_items("", "", "")

    # Only index 0 classified; index 1 and 2 missing from response
    groq_body = _groq_response_body([{"index": 0, "category": "data"}])

    mock_client = AsyncMock()
    mock_client.post.return_value = _mock_http_response(groq_body)

    monkeypatch.setattr(faq_classifier, "GROQ_API_KEYS", ["fake-key"])
    monkeypatch.setattr(faq_classifier, "get_http_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr(
        faq_classifier.prompt_manager, "get_template", lambda *_a, **_kw: _SYSTEM_PROMPT_STUB
    )

    result = await faq_classifier.classify_faqs(items, CATEGORY_LABELS)

    assert result[0]["category"] == "data"
    assert result[1]["category"] == ""
    assert result[2]["category"] == ""


# ---------- 4. Already categorized items are not re-classified ----------


@pytest.mark.asyncio
async def test_classify_faqs_skips_already_categorized(monkeypatch: pytest.MonkeyPatch) -> None:
    items = _make_items("billing", "sales")

    # Should not even call Groq since all items have categories
    mock_client = AsyncMock()
    monkeypatch.setattr(faq_classifier, "GROQ_API_KEYS", ["fake-key"])
    monkeypatch.setattr(faq_classifier, "get_http_client", AsyncMock(return_value=mock_client))

    result = await faq_classifier.classify_faqs(items, CATEGORY_LABELS)

    assert result[0]["category"] == "billing"
    assert result[1]["category"] == "sales"
    mock_client.post.assert_not_called()


# ---------- 5. Empty input returns empty list ----------


@pytest.mark.asyncio
async def test_classify_faqs_empty_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(faq_classifier, "GROQ_API_KEYS", ["fake-key"])
    result = await faq_classifier.classify_faqs([], CATEGORY_LABELS)
    assert result == []


# ---------- 6. No API keys — items returned unchanged ----------


@pytest.mark.asyncio
async def test_classify_faqs_no_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    items = _make_items("", "")
    monkeypatch.setattr(faq_classifier, "GROQ_API_KEYS", [])

    result = await faq_classifier.classify_faqs(items, CATEGORY_LABELS)

    assert result[0]["category"] == ""
    assert result[1]["category"] == ""


# ---------- 7. Invalid category in response is discarded ----------


@pytest.mark.asyncio
async def test_classify_faqs_rejects_invalid_category(monkeypatch: pytest.MonkeyPatch) -> None:
    items = _make_items("")

    groq_body = _groq_response_body([{"index": 0, "category": "nonexistent_category"}])

    mock_client = AsyncMock()
    mock_client.post.return_value = _mock_http_response(groq_body)

    monkeypatch.setattr(faq_classifier, "GROQ_API_KEYS", ["fake-key"])
    monkeypatch.setattr(faq_classifier, "get_http_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr(
        faq_classifier.prompt_manager, "get_template", lambda *_a, **_kw: _SYSTEM_PROMPT_STUB
    )

    result = await faq_classifier.classify_faqs(items, CATEGORY_LABELS)

    # Invalid category discarded — item unchanged
    assert result[0]["category"] == ""


# ---------- 8. Mixed items — only uncategorized get classified ----------


@pytest.mark.asyncio
async def test_classify_faqs_mixed_items(monkeypatch: pytest.MonkeyPatch) -> None:
    items = _make_items("billing", "", "sales", "")

    # Only indices 1 and 3 (the uncategorized ones) get sent; they become batch indices 0 and 1
    groq_body = _groq_response_body(
        [
            {"index": 0, "category": "account"},
            {"index": 1, "category": "data"},
        ]
    )

    mock_client = AsyncMock()
    mock_client.post.return_value = _mock_http_response(groq_body)

    monkeypatch.setattr(faq_classifier, "GROQ_API_KEYS", ["fake-key"])
    monkeypatch.setattr(faq_classifier, "get_http_client", AsyncMock(return_value=mock_client))
    monkeypatch.setattr(
        faq_classifier.prompt_manager, "get_template", lambda *_a, **_kw: _SYSTEM_PROMPT_STUB
    )

    result = await faq_classifier.classify_faqs(items, CATEGORY_LABELS)

    assert result[0]["category"] == "billing"  # kept
    assert result[1]["category"] == "account"  # classified
    assert result[2]["category"] == "sales"  # kept
    assert result[3]["category"] == "data"  # classified
