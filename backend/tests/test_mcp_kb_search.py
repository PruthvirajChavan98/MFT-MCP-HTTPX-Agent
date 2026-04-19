"""Unit tests for mcp_service.kb_search — semantic FAQ search for MCP tools.

2026-04-18: kb_search swapped from langchain-milvus async wrapper
(``asimilarity_search_with_score``) to ``milvus_mgr.semantic_search_raw`` —
raw pymilvus via executor. These tests mock the new call site.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.documents import Document

from src.mcp_service import kb_search


@pytest.fixture(autouse=True)
def _reset_milvus_mgr(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test starts with a fresh mocked milvus_mgr."""
    mock_mgr = MagicMock()
    mock_mgr.semantic_search_raw = AsyncMock(return_value=[])
    monkeypatch.setattr(kb_search, "milvus_mgr", mock_mgr)


def _doc(question: str, answer: str) -> Document:
    return Document(
        page_content=f"Question: {question}\nAnswer: {answer}",
        metadata={"question": question, "answer": answer},
    )


# ─────────── semantic_search ───────────


@pytest.mark.asyncio
async def test_semantic_search_returns_empty_on_empty_query() -> None:
    assert await kb_search.semantic_search("") == []
    assert await kb_search.semantic_search("   ") == []


@pytest.mark.asyncio
async def test_semantic_search_returns_empty_when_raw_helper_raises() -> None:
    kb_search.milvus_mgr.semantic_search_raw.side_effect = RuntimeError("milvus unreachable")
    results = await kb_search.semantic_search("how do I pay my loan?")
    assert results == []


@pytest.mark.asyncio
async def test_semantic_search_returns_formatted_results_on_hit() -> None:
    kb_search.milvus_mgr.semantic_search_raw = AsyncMock(
        return_value=[
            (_doc("How do I pay my loan?", "Visit the payments page."), 0.92),
            (_doc("When is my EMI due?", "Monthly on the 5th."), 0.78),
        ]
    )

    results = await kb_search.semantic_search("how to pay loan")
    assert len(results) == 2
    assert results[0] == {
        "question": "How do I pay my loan?",
        "answer": "Visit the payments page.",
        "score": pytest.approx(0.92),
    }
    assert results[1]["question"] == "When is my EMI due?"
    assert results[1]["score"] == pytest.approx(0.78)


@pytest.mark.asyncio
async def test_semantic_search_respects_limit_parameter() -> None:
    kb_search.milvus_mgr.semantic_search_raw = AsyncMock(return_value=[])

    await kb_search.semantic_search("anything", limit=3)
    kb_search.milvus_mgr.semantic_search_raw.assert_awaited_once_with(
        collection="kb_faqs", query="anything", limit=3
    )


@pytest.mark.asyncio
async def test_semantic_search_default_limit_is_five() -> None:
    kb_search.milvus_mgr.semantic_search_raw = AsyncMock(return_value=[])

    await kb_search.semantic_search("anything")
    kb_search.milvus_mgr.semantic_search_raw.assert_awaited_once_with(
        collection="kb_faqs", query="anything", limit=5
    )


@pytest.mark.asyncio
async def test_semantic_search_strips_whitespace_before_calling_raw_helper() -> None:
    kb_search.milvus_mgr.semantic_search_raw = AsyncMock(return_value=[])

    await kb_search.semantic_search("  what are loan products?  ")
    kb_search.milvus_mgr.semantic_search_raw.assert_awaited_once_with(
        collection="kb_faqs", query="what are loan products?", limit=5
    )


# ─────────── format_results ───────────


def test_format_results_empty_list_returns_no_match_message() -> None:
    output = kb_search.format_results([])
    assert "No matching FAQs found" in output


def test_format_results_single_hit_includes_question_answer_score() -> None:
    results = [{"question": "How do I pay?", "answer": "Use the portal.", "score": 0.85}]
    output = kb_search.format_results(results)
    assert "How do I pay?" in output
    assert "Use the portal." in output
    assert "0.85" in output
    assert "1." in output  # numbered list


def test_format_results_multiple_hits_numbered_and_sorted() -> None:
    results = [
        {"question": "Q1?", "answer": "A1.", "score": 0.91},
        {"question": "Q2?", "answer": "A2.", "score": 0.72},
        {"question": "Q3?", "answer": "A3.", "score": 0.55},
    ]
    output = kb_search.format_results(results)
    assert "Found 3 matching FAQ(s)" in output
    assert "1. Q: Q1?" in output
    assert "2. Q: Q2?" in output
    assert "3. Q: Q3?" in output
    assert "A1." in output and "A2." in output and "A3." in output


def test_format_results_handles_missing_metadata_gracefully() -> None:
    results = [{"question": "", "answer": "", "score": 0.5}]
    output = kb_search.format_results(results)
    # Should not crash or render "None" — uses a fallback
    assert "None" not in output
    assert "no question" in output.lower() or "(no question)" in output
