"""Unit tests for the pgvector-backed stores.

We don't spin up a real Postgres in unit tests — the *integration* test of
the real backend is the live data migration script + admin smoke check.
Here we mock the asyncpg pool boundary and assert the wrapper produces the
right SQL shape, the right Document metadata, and the right distance →
similarity contract for callers.
"""

from __future__ import annotations

from typing import Any

import pytest
from langchain_core.documents import Document

from src.agent_service.eval_store import pg_vector_store as pvs


class _FakeConn:
    """Minimal stand-in for asyncpg.Connection that records the SQL it was
    given and serves canned rows back to fetch."""

    def __init__(self, fetch_rows: list[dict[str, Any]] | None = None) -> None:
        self.fetch_rows = fetch_rows or []
        self.executes: list[tuple[str, tuple[Any, ...]]] = []
        self.fetches: list[tuple[str, tuple[Any, ...]]] = []
        self.closed = False

    async def fetch(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        self.fetches.append((sql, args))
        return list(self.fetch_rows)

    async def fetchrow(self, sql: str, *args: Any) -> dict[str, Any]:
        self.fetches.append((sql, args))
        return self.fetch_rows[0] if self.fetch_rows else {"pk": 1}

    async def execute(self, sql: str, *args: Any) -> str:
        self.executes.append((sql, args))
        return "EXECUTE 1"

    def transaction(self) -> Any:
        return _FakeTransaction()

    def is_closed(self) -> bool:
        return self.closed


class _FakeTransaction:
    async def __aenter__(self) -> "_FakeTransaction":
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


class _FakePool:
    """Mimics asyncpg.Pool's acquire() context manager."""

    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    def acquire(self) -> "_PoolAcquireCM":
        return _PoolAcquireCM(self._conn)


class _PoolAcquireCM:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    async def __aenter__(self) -> _FakeConn:
        return self._conn

    async def __aexit__(self, *exc: Any) -> None:
        return None


class _FakeEmbedder:
    """Returns a deterministic fake vector so SQL-shape assertions are stable."""

    def __init__(self, dim: int = 1536) -> None:
        self.dim = dim
        self.queries_embedded: list[str] = []

    async def aembed_query(self, text: str) -> list[float]:
        self.queries_embedded.append(text)
        return [0.1] * self.dim

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        self.queries_embedded.extend(texts)
        return [[0.1] * self.dim for _ in texts]


@pytest.fixture(autouse=True)
def _stub_register_vector(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid touching real asyncpg / pgvector during unit tests."""

    async def _no_op(_conn: Any) -> None:
        return None

    monkeypatch.setattr(pvs, "register_vector", _no_op)
    pvs._codec_registered.clear()


@pytest.fixture
def fake_conn() -> _FakeConn:
    return _FakeConn()


@pytest.fixture
def fake_pool(monkeypatch: pytest.MonkeyPatch, fake_conn: _FakeConn) -> _FakePool:
    pool = _FakePool(fake_conn)
    monkeypatch.setattr(pvs, "get_shared_pool", lambda: pool)
    return pool


# ─── PgKbFaqsStore ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_kb_faqs_aadd_documents_upserts_each_row(
    fake_pool: _FakePool, fake_conn: _FakeConn
) -> None:
    store = pvs.PgKbFaqsStore(embedder=_FakeEmbedder())
    docs = [
        Document(
            page_content="What is foreclosure?",
            metadata={
                "question_key": "faq-1",
                "question": "What is foreclosure?",
                "answer": "Closing a loan early.",
                "category": "general",
                "embedding_model": "text-embedding-3-small",
            },
        )
    ]
    out = await store.aadd_documents(docs)
    assert out == ["faq-1"]
    sql, args = fake_conn.executes[0]
    assert "INSERT INTO kb_faqs" in sql
    assert "ON CONFLICT (question_key) DO UPDATE" in sql
    # args[0] is the key, args[5] is the embedding_model
    assert args[0] == "faq-1"
    assert args[5] == "text-embedding-3-small"


@pytest.mark.asyncio
async def test_kb_faqs_search_returns_documents_with_distance(
    monkeypatch: pytest.MonkeyPatch, fake_conn: _FakeConn
) -> None:
    fake_conn.fetch_rows = [
        {
            "question_key": "faq-1",
            "question": "What is foreclosure?",
            "answer": "Closing a loan early.",
            "category": "general",
            "distance": 0.08,
        }
    ]
    monkeypatch.setattr(pvs, "get_shared_pool", lambda: _FakePool(fake_conn))

    store = pvs.PgKbFaqsStore(embedder=_FakeEmbedder())
    hits = await store.asimilarity_search_with_score("what is foreclosure?", k=3)
    assert len(hits) == 1
    doc, dist = hits[0]
    assert doc.metadata["question_key"] == "faq-1"
    assert dist == pytest.approx(0.08)
    # cosine distance 0.08 → similarity 0.96 via the existing call-site arithmetic
    assert pvs._distance_to_similarity(dist) == pytest.approx(0.96, abs=0.01)


# ─── PgEvalTracesStore ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_eval_traces_aadd_only_updates_embedding_column(
    fake_pool: _FakePool, fake_conn: _FakeConn
) -> None:
    store = pvs.PgEvalTracesStore(embedder=_FakeEmbedder())
    docs = [Document(page_content="trace doc", metadata={"trace_id": "abc123"})]
    await store.aadd_documents(docs)
    sql, args = fake_conn.executes[0]
    assert sql.strip().startswith("UPDATE eval_traces SET embedding")
    assert args[1] == "abc123"


@pytest.mark.asyncio
async def test_eval_traces_search_filters_null_embeddings(
    monkeypatch: pytest.MonkeyPatch, fake_conn: _FakeConn
) -> None:
    fake_conn.fetch_rows = [
        {
            "trace_id": "tr-1",
            "provider": "groq",
            "model": "openai/gpt-oss-120b",
            "status": "success",
            "session_id": "sess-1",
            "case_id": None,
            "doc": "trace text",
            "distance": 0.12,
        }
    ]
    monkeypatch.setattr(pvs, "get_shared_pool", lambda: _FakePool(fake_conn))

    store = pvs.PgEvalTracesStore(embedder=_FakeEmbedder())
    hits = await store.asimilarity_search_with_score_by_vector([0.1] * 1536, k=5)

    sql, _args = fake_conn.fetches[0]
    assert "WHERE embedding IS NOT NULL" in sql
    assert hits[0][0].metadata["pk"] == "tr-1"  # eval_read.py fallback chain


# ─── PgInlineGuardCacheStore ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_guard_cache_writeback_uses_unique_constraint_for_idempotency(
    fake_pool: _FakePool, fake_conn: _FakeConn
) -> None:
    fake_conn.fetch_rows = [{"pk": 42}]
    store = pvs.PgInlineGuardCacheStore(embedder=_FakeEmbedder(dim=384))
    docs = [
        Document(
            page_content="what tools do you have",
            metadata={
                "decision": "block",
                "reason_code": "unsafe_signal",
                "risk_score": 0.9,
                "model_version": "openai/gpt-oss-safeguard-20b",
                "embedder_version": "MiniLM-L6-v2-2026-05",
                "content_hash": "abc",
                "ts": 12345,
            },
        )
    ]
    out_ids = await store.aadd_documents(docs)
    assert out_ids == ["42"]
    sql, args = fake_conn.fetches[0]  # fetchrow goes through the same recorder
    assert "ON CONFLICT (content_hash, model_version, embedder_version)" in sql
    assert args[0] == "block"
    assert args[1] == "unsafe_signal"


@pytest.mark.asyncio
async def test_guard_cache_search_returns_metadata_for_lookup(
    monkeypatch: pytest.MonkeyPatch, fake_conn: _FakeConn
) -> None:
    fake_conn.fetch_rows = [
        {
            "pk": 7,
            "decision": "allow",
            "reason_code": "safe",
            "risk_score": 0.0,
            "model_version": "openai/gpt-oss-safeguard-20b",
            "embedder_version": "MiniLM-L6-v2-2026-05",
            "content_hash": "h1",
            "ts": 100,
            "distance": 0.05,
        }
    ]
    monkeypatch.setattr(pvs, "get_shared_pool", lambda: _FakePool(fake_conn))

    store = pvs.PgInlineGuardCacheStore(embedder=_FakeEmbedder(dim=384))
    hits = await store.asimilarity_search_with_score_by_vector([0.1] * 384, k=1)
    assert len(hits) == 1
    doc, dist = hits[0]
    assert doc.metadata["decision"] == "allow"
    assert doc.metadata["model_version"] == "openai/gpt-oss-safeguard-20b"
    assert dist == pytest.approx(0.05)


@pytest.mark.asyncio
async def test_distance_to_similarity_inversion_is_safe_at_extremes() -> None:
    # Cosine distance edges: 0 (identical) → similarity 1; 2 (opposite) → 0.
    assert pvs._distance_to_similarity(0.0) == pytest.approx(1.0)
    assert pvs._distance_to_similarity(2.0) == pytest.approx(0.0)
    # Above-2 (theoretically impossible but defensive) clamps to 0.
    assert pvs._distance_to_similarity(2.5) == pytest.approx(0.0)
