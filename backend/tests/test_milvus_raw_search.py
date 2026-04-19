"""Unit tests for MilvusManager.semantic_search_raw.

Routes around the langchain-milvus 0.3.3 async-wrapper hang by composing the
OpenRouter embed step with raw pymilvus Collection.search. This test locks
the result shape + metadata projection so callers can substitute cleanly for
``asimilarity_search_with_score``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.documents import Document

from src.common import milvus_mgr as mm


class _FakeHit:
    def __init__(self, pk: str, score: float, entity_data: dict[str, Any]) -> None:
        self.id = pk
        self.score = score
        self._entity_data = entity_data
        self.entity = self

    def get(self, field: str) -> Any:
        return self._entity_data.get(field)


class _FakeCollection:
    def __init__(self, hits: list[_FakeHit]) -> None:
        self._hits = hits
        self.load_calls = 0
        self.search_calls: list[dict[str, Any]] = []

    def load(self) -> None:
        self.load_calls += 1

    def search(self, **kwargs: Any) -> list[list[_FakeHit]]:
        self.search_calls.append(kwargs)
        return [self._hits]


@pytest.mark.asyncio
async def test_semantic_search_raw_returns_document_score_tuples(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy path: embedder + raw search compose into (Document, score) tuples."""
    fake_hits = [
        _FakeHit(
            pk="faq-1",
            score=0.92,
            entity_data={"question": "What loans do you offer?", "answer": "Two-wheeler loans."},
        ),
        _FakeHit(
            pk="faq-2",
            score=0.71,
            entity_data={"question": "How do I check eligibility?", "answer": "Use the app."},
        ),
    ]
    fake_collection = _FakeCollection(fake_hits)

    monkeypatch.setattr(
        mm,
        "_make_embeddings",
        lambda _api_key: MagicMock(aembed_query=AsyncMock(return_value=[0.1] * 1536)),
    )

    captured_args: dict[str, Any] = {}

    def _fake_connect(**kwargs: Any) -> None:
        captured_args.update(kwargs)

    def _fake_collection_ctor(name: str, using: str = "default") -> _FakeCollection:
        captured_args["collection_name"] = name
        captured_args["using"] = using
        return fake_collection

    fake_pymilvus = MagicMock()
    fake_pymilvus.Collection = _fake_collection_ctor
    fake_pymilvus.connections.connect = _fake_connect

    # Patch the imports that happen inside the method.
    monkeypatch.setitem(
        __import__("sys").modules,
        "pymilvus",
        fake_pymilvus,
    )

    results = await mm.milvus_mgr.semantic_search_raw(
        collection="kb_faqs", query="loan products", limit=3
    )

    assert len(results) == 2
    first_doc, first_score = results[0]
    assert isinstance(first_doc, Document)
    assert first_doc.page_content == "What loans do you offer?"
    assert first_doc.metadata["question"] == "What loans do you offer?"
    assert first_doc.metadata["answer"] == "Two-wheeler loans."
    assert first_doc.metadata["pk"] == "faq-1"
    assert first_score == pytest.approx(0.92)

    second_doc, second_score = results[1]
    assert second_doc.metadata["pk"] == "faq-2"
    assert second_score == pytest.approx(0.71)

    # Raw search was invoked with the expected params.
    assert fake_collection.load_calls == 1
    assert len(fake_collection.search_calls) == 1
    search_call = fake_collection.search_calls[0]
    assert search_call["anns_field"] == "vector"
    assert search_call["limit"] == 3
    assert search_call["param"]["metric_type"] == "COSINE"
    assert captured_args["collection_name"] == "kb_faqs"


@pytest.mark.asyncio
async def test_semantic_search_raw_returns_empty_on_blank_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Whitespace-only query short-circuits before any network call."""
    embed_calls: list[str] = []

    def _make_embedder(_api_key: str) -> Any:
        async def _embed(text: str) -> list[float]:
            embed_calls.append(text)
            return [0.0] * 1536

        return MagicMock(aembed_query=AsyncMock(side_effect=_embed))

    monkeypatch.setattr(mm, "_make_embeddings", _make_embedder)

    results = await mm.milvus_mgr.semantic_search_raw(collection="kb_faqs", query="   ")
    assert results == []
    assert embed_calls == []


@pytest.mark.asyncio
async def test_semantic_search_raw_uses_text_field_for_page_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eval-trace collections project 'text' as page_content (kb_faqs uses 'question')."""
    hit = _FakeHit(
        pk="trace-xyz",
        score=0.5,
        entity_data={"text": "Agent reasoned about loan eligibility.", "question": None},
    )
    fake_collection = _FakeCollection([hit])

    monkeypatch.setattr(
        mm,
        "_make_embeddings",
        lambda _api_key: MagicMock(aembed_query=AsyncMock(return_value=[0.5] * 1536)),
    )

    fake_pymilvus = MagicMock()
    fake_pymilvus.Collection = lambda name, using="default": fake_collection
    fake_pymilvus.connections.connect = lambda **_: None
    monkeypatch.setitem(__import__("sys").modules, "pymilvus", fake_pymilvus)

    results = await mm.milvus_mgr.semantic_search_raw(
        collection="eval_traces_emb", query="what did the agent do"
    )
    assert len(results) == 1
    doc, _ = results[0]
    assert doc.page_content == "Agent reasoned about loan eligibility."
