"""pgvector-backed replacement for langchain-milvus stores.

One concrete class per collection:

  - `PgKbFaqsStore`         → kb_faqs           (1536-dim, OpenRouter embedder)
  - `PgEvalTracesStore`     → eval_traces       (1536-dim, embedding column on existing table)
  - `PgEvalResultsStore`    → eval_results      (1536-dim, embedding column on existing table)
  - `PgInlineGuardCacheStore` → inline_guard_cache  (384-dim, local MiniLM)

Each class exposes the langchain-milvus async surface used by callers today:

  - `aadd_documents(docs, ids=None) -> list[str]`
  - `asimilarity_search_with_score(query, k=10) -> list[(Document, float)]`
  - `asimilarity_search_with_score_by_vector(vec, k=10) -> list[(Document, float)]`
  - `adelete(ids=None, expr=None) -> bool`

The float returned alongside Document is the **cosine distance** in [0, 2],
matching the langchain-milvus shape — call sites already convert to similarity
via `1 - dist / 2` and that arithmetic stays correct.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Sequence

from langchain_core.documents import Document
from pgvector.asyncpg import register_vector

from src.agent_service.eval_store.pg_store import get_shared_pool

log = logging.getLogger("pg_vector_store")


@dataclass(frozen=True, slots=True)
class _Hit:
    """Internal: a single search hit."""

    document: Document
    distance: float


# ─── pool helpers ─────────────────────────────────────────────────────────────


# Track connection objects that have had the pgvector codec registered.
# A WeakSet would be ideal but asyncpg connections aren't always weakref-able;
# a regular set works because connections are reused from the pool, and
# a stale-id collision would just trigger one harmless extra register call.
_codec_registered: set[int] = set()


async def _acquire_with_codec(pool: Any) -> Any:
    """Acquire a pool connection and ensure the pgvector codec is registered.

    Returns an async context manager — caller does
    `async with await _acquire_with_codec(pool) as conn: ...`.
    Registering is idempotent per asyncpg Connection object, so we cache
    by `id(conn)` to avoid the few-ms hit on hot paths.
    """
    return _CodecAwareAcquire(pool)


class _CodecAwareAcquire:
    """Async context manager that acquires a pool connection and registers
    the pgvector codec on first use of each connection."""

    def __init__(self, pool: Any) -> None:
        self._pool = pool
        self._cm: Any = None
        self._conn: Any = None

    async def __aenter__(self) -> Any:
        self._cm = self._pool.acquire()
        self._conn = await self._cm.__aenter__()
        cid = id(self._conn)
        if cid not in _codec_registered:
            await register_vector(self._conn)
            _codec_registered.add(cid)
        return self._conn

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._cm is not None:
            await self._cm.__aexit__(exc_type, exc, tb)


async def _pool_or_raise() -> Any:
    pool = get_shared_pool()
    if pool is None:
        raise RuntimeError("Shared Postgres pool not configured")
    return pool


def _vector_to_param(vec: Sequence[float]) -> list[float]:
    """asyncpg with the pgvector codec accepts a list[float] directly.
    Cast to list to handle numpy arrays / tuples returned by embedders."""
    return list(vec)


def _distance_to_similarity(distance: float) -> float:
    """Cosine distance in [0, 2] → similarity in [0, 1]. Mirrors the
    conversion already used at every call site."""
    return max(0.0, 1.0 - float(distance) / 2.0)


# ─── per-collection stores ────────────────────────────────────────────────────


class PgKbFaqsStore:
    """kb_faqs — replaces the Milvus collection of the same name."""

    table = "kb_faqs"
    dim = 1536

    def __init__(self, embedder: Any) -> None:
        self._embedder = embedder

    async def _pool(self) -> Any:
        return await _pool_or_raise()

    async def aadd_documents(
        self, docs: Sequence[Document], ids: Sequence[str] | None = None
    ) -> list[str]:
        if not docs:
            return []
        if ids is None:
            ids = [d.metadata.get("question_key") or d.metadata.get("id") or "" for d in docs]
        if any(not i for i in ids):
            raise ValueError("kb_faqs aadd_documents requires non-empty ids/question_keys")

        texts = [d.page_content for d in docs]
        # Embed in one batch — kb_faqs ingest is small and bulk-friendly.
        embeddings = await self._embedder.aembed_documents(texts)

        pool = await self._pool()
        async with await _acquire_with_codec(pool) as conn:
            async with conn.transaction():
                for doc, key, vec in zip(docs, ids, embeddings, strict=True):
                    meta = doc.metadata or {}
                    await conn.execute(
                        """
                        INSERT INTO kb_faqs (
                            question_key, question, answer, category, embedding, embedding_model
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (question_key) DO UPDATE SET
                            question = EXCLUDED.question,
                            answer = EXCLUDED.answer,
                            category = EXCLUDED.category,
                            embedding = EXCLUDED.embedding,
                            embedding_model = EXCLUDED.embedding_model,
                            updated_at = NOW()
                        """,
                        key,
                        meta.get("question") or doc.page_content,
                        meta.get("answer") or "",
                        meta.get("category") or "",
                        _vector_to_param(vec),
                        meta.get("embedding_model") or "",
                    )
        return list(ids)

    async def asimilarity_search_with_score(
        self, query: str, k: int = 10, **_: Any
    ) -> list[tuple[Document, float]]:
        vec = await self._embedder.aembed_query(query)
        return await self.asimilarity_search_with_score_by_vector(vec, k=k)

    async def asimilarity_search_with_score_by_vector(
        self, embedding: Sequence[float], k: int = 10, **_: Any
    ) -> list[tuple[Document, float]]:
        pool = await self._pool()
        async with await _acquire_with_codec(pool) as conn:
            rows = await conn.fetch(
                """
                SELECT question_key, question, answer, category,
                       embedding <=> $1 AS distance
                FROM kb_faqs
                ORDER BY distance
                LIMIT $2
                """,
                _vector_to_param(embedding),
                k,
            )
        out: list[tuple[Document, float]] = []
        for r in rows:
            doc = Document(
                page_content=r["question"],
                metadata={
                    "question_key": r["question_key"],
                    "question": r["question"],
                    "answer": r["answer"],
                    "category": r["category"],
                },
            )
            out.append((doc, float(r["distance"])))
        return out

    async def adelete(
        self, ids: Sequence[str] | None = None, expr: str | None = None, **_: Any
    ) -> bool:
        pool = await self._pool()
        async with await _acquire_with_codec(pool) as conn:
            if ids:
                await conn.execute("DELETE FROM kb_faqs WHERE question_key = ANY($1)", list(ids))
                return True
            if expr is None:
                # Wipe-everything is the langchain-milvus semantic for `expr=None`,
                # but we explicitly require an opt-in `*` to avoid accidents.
                return False
            if expr.strip() in {"*", "1=1", "true"}:
                await conn.execute("TRUNCATE kb_faqs")
                return True
        # Other Milvus-flavoured exprs aren't translated — caller must use ids.
        raise NotImplementedError(f"Unsupported delete expression: {expr!r}")


class PgEvalTracesStore:
    """eval_traces.embedding — embedding lives as a column on the existing
    eval_traces table, so this store does not insert/update other trace fields
    (those are managed by EvalPgStore.upsert_trace). Only the embedding
    column and a light read shape are touched here."""

    table = "eval_traces"
    dim = 1536

    def __init__(self, embedder: Any) -> None:
        self._embedder = embedder

    async def _pool(self) -> Any:
        return await _pool_or_raise()

    async def aadd_documents(
        self, docs: Sequence[Document], ids: Sequence[str] | None = None
    ) -> list[str]:
        if not docs:
            return []
        if ids is None:
            ids = [d.metadata.get("trace_id") or "" for d in docs]
        if any(not i for i in ids):
            raise ValueError("eval_traces aadd_documents requires non-empty trace_id")

        texts = [d.page_content for d in docs]
        embeddings = await self._embedder.aembed_documents(texts)

        pool = await self._pool()
        async with await _acquire_with_codec(pool) as conn:
            async with conn.transaction():
                for trace_id, vec in zip(ids, embeddings, strict=True):
                    # Row already exists (created by EvalPgStore.upsert_trace).
                    # We only populate the embedding column.
                    await conn.execute(
                        "UPDATE eval_traces SET embedding = $1 WHERE trace_id = $2",
                        _vector_to_param(vec),
                        trace_id,
                    )
        return list(ids)

    async def asimilarity_search_with_score(
        self, query: str, k: int = 10, **_: Any
    ) -> list[tuple[Document, float]]:
        vec = await self._embedder.aembed_query(query)
        return await self.asimilarity_search_with_score_by_vector(vec, k=k)

    async def asimilarity_search_with_score_by_vector(
        self, embedding: Sequence[float], k: int = 10, **_: Any
    ) -> list[tuple[Document, float]]:
        pool = await self._pool()
        async with await _acquire_with_codec(pool) as conn:
            rows = await conn.fetch(
                """
                SELECT trace_id, provider, model, status, session_id, case_id,
                       COALESCE(doc, '') AS doc,
                       embedding <=> $1 AS distance
                FROM eval_traces
                WHERE embedding IS NOT NULL
                ORDER BY distance
                LIMIT $2
                """,
                _vector_to_param(embedding),
                k,
            )
        out: list[tuple[Document, float]] = []
        for r in rows:
            doc = Document(
                page_content=r["doc"],
                metadata={
                    "trace_id": r["trace_id"],
                    "provider": r["provider"] or "",
                    "model": r["model"] or "",
                    "status": r["status"] or "",
                    "session_id": r["session_id"] or "",
                    "case_id": r["case_id"] or "",
                    "pk": r["trace_id"],  # eval_read.py falls back to "pk" then doc.id
                },
            )
            out.append((doc, float(r["distance"])))
        return out

    async def adelete(
        self, ids: Sequence[str] | None = None, expr: str | None = None, **_: Any
    ) -> bool:
        # Don't delete trace rows here — that's owned by EvalPgStore.
        # Only clear the embedding column.
        pool = await self._pool()
        async with await _acquire_with_codec(pool) as conn:
            if ids:
                await conn.execute(
                    "UPDATE eval_traces SET embedding = NULL WHERE trace_id = ANY($1)",
                    list(ids),
                )
                return True
            if expr and expr.strip() in {"*", "1=1", "true"}:
                await conn.execute("UPDATE eval_traces SET embedding = NULL")
                return True
        return False


class PgEvalResultsStore:
    """eval_results.embedding — same shape as PgEvalTracesStore."""

    table = "eval_results"
    dim = 1536

    def __init__(self, embedder: Any) -> None:
        self._embedder = embedder

    async def _pool(self) -> Any:
        return await _pool_or_raise()

    async def aadd_documents(
        self, docs: Sequence[Document], ids: Sequence[str] | None = None
    ) -> list[str]:
        if not docs:
            return []
        if ids is None:
            ids = [d.metadata.get("eval_id") or "" for d in docs]
        if any(not i for i in ids):
            raise ValueError("eval_results aadd_documents requires non-empty eval_id")

        texts = [d.page_content for d in docs]
        embeddings = await self._embedder.aembed_documents(texts)

        pool = await self._pool()
        async with await _acquire_with_codec(pool) as conn:
            async with conn.transaction():
                for eval_id, vec in zip(ids, embeddings, strict=True):
                    await conn.execute(
                        "UPDATE eval_results SET embedding = $1 WHERE eval_id = $2",
                        _vector_to_param(vec),
                        eval_id,
                    )
        return list(ids)

    async def asimilarity_search_with_score(
        self, query: str, k: int = 10, **_: Any
    ) -> list[tuple[Document, float]]:
        vec = await self._embedder.aembed_query(query)
        return await self.asimilarity_search_with_score_by_vector(vec, k=k)

    async def asimilarity_search_with_score_by_vector(
        self, embedding: Sequence[float], k: int = 10, **_: Any
    ) -> list[tuple[Document, float]]:
        pool = await self._pool()
        async with await _acquire_with_codec(pool) as conn:
            rows = await conn.fetch(
                """
                SELECT eval_id, trace_id, metric_name, passed, score,
                       COALESCE(doc, '') AS doc,
                       embedding <=> $1 AS distance
                FROM eval_results
                WHERE embedding IS NOT NULL
                ORDER BY distance
                LIMIT $2
                """,
                _vector_to_param(embedding),
                k,
            )
        out: list[tuple[Document, float]] = []
        for r in rows:
            doc = Document(
                page_content=r["doc"],
                metadata={
                    "eval_id": r["eval_id"],
                    "trace_id": r["trace_id"] or "",
                    "metric_name": r["metric_name"] or "",
                    "passed": str(r["passed"]) if r["passed"] is not None else "",
                    "score": str(r["score"]) if r["score"] is not None else "",
                    "pk": r["eval_id"],
                },
            )
            out.append((doc, float(r["distance"])))
        return out

    async def adelete(
        self, ids: Sequence[str] | None = None, expr: str | None = None, **_: Any
    ) -> bool:
        pool = await self._pool()
        async with await _acquire_with_codec(pool) as conn:
            if ids:
                await conn.execute(
                    "UPDATE eval_results SET embedding = NULL WHERE eval_id = ANY($1)",
                    list(ids),
                )
                return True
            if expr and expr.strip() in {"*", "1=1", "true"}:
                await conn.execute("UPDATE eval_results SET embedding = NULL")
                return True
        return False


class PgInlineGuardCacheStore:
    """inline_guard_cache — auto-id table; UNIQUE on (content_hash,
    model_version, embedder_version) makes the writeback ON CONFLICT idempotent.

    Unlike the other stores, this one does NOT take an external embedder for
    `aadd_documents` — the caller (inline_guard_cache.py) hands us the prompt
    text and asimilarity_search_with_score embeds it via the local MiniLM
    embedder, then the writeback shortcuts to writing the precomputed vector
    via aadd_documents_with_vector."""

    table = "inline_guard_cache"
    dim = 384

    def __init__(self, embedder: Any) -> None:
        self._embedder = embedder

    async def _pool(self) -> Any:
        return await _pool_or_raise()

    async def aadd_documents(
        self, docs: Sequence[Document], ids: Sequence[str] | None = None
    ) -> list[str]:
        if not docs:
            return []
        # Embed page_content with the local embedder; then UPSERT.
        texts = [d.page_content for d in docs]
        embeddings = await self._embedder.aembed_documents(texts)

        pool = await self._pool()
        out_ids: list[str] = []
        async with await _acquire_with_codec(pool) as conn:
            async with conn.transaction():
                for doc, vec in zip(docs, embeddings, strict=True):
                    meta = doc.metadata or {}
                    row = await conn.fetchrow(
                        """
                        INSERT INTO inline_guard_cache (
                            decision, reason_code, risk_score,
                            model_version, embedder_version, content_hash,
                            ts, embedding
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (content_hash, model_version, embedder_version)
                        DO UPDATE SET
                            decision = EXCLUDED.decision,
                            reason_code = EXCLUDED.reason_code,
                            risk_score = EXCLUDED.risk_score,
                            ts = EXCLUDED.ts,
                            embedding = EXCLUDED.embedding
                        RETURNING pk
                        """,
                        str(meta.get("decision") or ""),
                        str(meta.get("reason_code") or ""),
                        float(meta.get("risk_score") or 0.0),
                        str(meta.get("model_version") or ""),
                        str(meta.get("embedder_version") or ""),
                        str(meta.get("content_hash") or ""),
                        int(meta.get("ts") or 0),
                        _vector_to_param(vec),
                    )
                    out_ids.append(str(row["pk"]))
        return out_ids

    async def asimilarity_search_with_score(
        self, query: str, k: int = 1, **_: Any
    ) -> list[tuple[Document, float]]:
        vec = await self._embedder.aembed_query(query)
        return await self.asimilarity_search_with_score_by_vector(vec, k=k)

    async def asimilarity_search_with_score_by_vector(
        self, embedding: Sequence[float], k: int = 1, **_: Any
    ) -> list[tuple[Document, float]]:
        pool = await self._pool()
        async with await _acquire_with_codec(pool) as conn:
            rows = await conn.fetch(
                """
                SELECT pk, decision, reason_code, risk_score,
                       model_version, embedder_version, content_hash, ts,
                       embedding <=> $1 AS distance
                FROM inline_guard_cache
                ORDER BY distance
                LIMIT $2
                """,
                _vector_to_param(embedding),
                k,
            )
        out: list[tuple[Document, float]] = []
        for r in rows:
            doc = Document(
                page_content="",
                metadata={
                    "pk": r["pk"],
                    "decision": r["decision"],
                    "reason_code": r["reason_code"],
                    "risk_score": float(r["risk_score"]),
                    "model_version": r["model_version"],
                    "embedder_version": r["embedder_version"],
                    "content_hash": r["content_hash"],
                    "ts": int(r["ts"]),
                },
            )
            out.append((doc, float(r["distance"])))
        return out

    async def adelete(
        self, ids: Sequence[str] | None = None, expr: str | None = None, **_: Any
    ) -> bool:
        pool = await self._pool()
        async with await _acquire_with_codec(pool) as conn:
            if ids:
                int_ids = [int(i) for i in ids]
                await conn.execute("DELETE FROM inline_guard_cache WHERE pk = ANY($1)", int_ids)
                return True
            if expr and expr.strip() in {"*", "1=1", "true"}:
                await conn.execute("TRUNCATE inline_guard_cache")
                return True
        return False
