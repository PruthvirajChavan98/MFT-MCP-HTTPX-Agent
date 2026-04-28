"""Coverage for the `kind="result"` path of ``POST /api/eval/vector-search``.

The production bug was: the ``eval_results_emb`` Milvus collection was
created before ``eval_id`` was added to the writer's metadata schema,
so Milvus auto-inferred a field set that did not include ``eval_id``.
Runtime queries that project or filter by ``eval_id`` surfaced the
opaque ``MilvusException: field eval_id not exist`` and the endpoint
swallowed it into a 503 without a clear contract.

These tests lock the fix-forward behaviour:

1. Happy path — the endpoint accepts ``kind="result"``, calls the
   right Milvus collection, and projects ``eval_id`` into the
   response without falling back into the trace-metadata branch.
2. Store failure — a raised ``Exception`` produces the canonical 503
   ``store_unavailable`` error JSON, matching the trace-kind behaviour
   that existed before.
3. Metadata-shape drift — when the returned Milvus document is missing
   the ``eval_id`` metadata key (e.g. a collection re-rebuild was
   partial), the endpoint falls back to ``doc.id`` rather than
   projecting an empty id and 404-ing the Postgres join.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.agent_service.api import eval_read


class _FakeRequest:
    def __init__(self, pool):
        self.app = SimpleNamespace(state=SimpleNamespace(pool=pool))


class _ResultPgPool:
    """Postgres fake that serves the ``eval_results`` JOIN projection."""

    async def fetch(self, query: str, *args):
        assert "FROM eval_results" in query, "result-kind query must target eval_results"
        return [
            {
                "eval_id": "eval-1",
                "trace_id": "trace-1",
                "metric_name": "faithfulness",
                "score": 0.91,
                "passed": True,
                "reasoning": "good match",
                "provider": "openrouter",
                "model": "model-1",
                "session_id": "session-1",
                "case_id": "app-1",
                "status": "success",
            }
        ]


class _ResultStore:
    """Milvus fake for ``milvus_mgr.eval_results``."""

    def __init__(self, metadata: dict | None = None, raises: Exception | None = None):
        self._metadata = (
            {"eval_id": "eval-1", "trace_id": "trace-1"} if metadata is None else metadata
        )
        self._raises = raises

    async def asimilarity_search_with_score_by_vector(self, vector, **kwargs):
        if self._raises is not None:
            raise self._raises
        return [
            (SimpleNamespace(metadata=self._metadata, id=self._metadata.get("eval_id", "")), 0.87)
        ]

    async def asimilarity_search_with_score(self, query, **kwargs):
        if self._raises is not None:
            raise self._raises
        return [
            (SimpleNamespace(metadata=self._metadata, id=self._metadata.get("eval_id", "")), 0.87)
        ]


@pytest.mark.asyncio
async def test_kind_result_happy_path_projects_eval_id(monkeypatch):
    pool = _ResultPgPool()
    store = _ResultStore()
    monkeypatch.setattr(eval_read.milvus_mgr, "eval_results", store)

    result = await eval_read.eval_vector_search(
        request=_FakeRequest(pool),
        req=eval_read.VectorSearchRequest(kind="result", vector=[0.1, 0.2], k=1),
        x_openrouter_key=None,
    )

    assert result["kind"] == "result"
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["eval_id"] == "eval-1"
    assert item["trace_id"] == "trace-1"
    assert item["metric_name"] == "faithfulness"


@pytest.mark.asyncio
async def test_kind_result_surface_store_failure_as_503(monkeypatch):
    pool = _ResultPgPool()
    store = _ResultStore(raises=Exception("field eval_id not exist"))
    monkeypatch.setattr(eval_read.milvus_mgr, "eval_results", store)

    with pytest.raises(Exception) as ei:
        await eval_read.eval_vector_search(
            request=_FakeRequest(pool),
            req=eval_read.VectorSearchRequest(kind="result", vector=[0.1], k=1),
            x_openrouter_key=None,
        )
    # FastAPI raises HTTPException — assert the status_code + code carried
    # through the detail payload.
    err = ei.value
    status_code = getattr(err, "status_code", None)
    detail = getattr(err, "detail", None)
    assert status_code == 503
    assert isinstance(detail, dict)
    assert detail.get("code") == "store_unavailable"
    assert detail.get("operation") == "eval_vector_search"


@pytest.mark.asyncio
async def test_kind_result_falls_back_to_doc_id_when_metadata_missing(monkeypatch):
    """Defensive read: if Milvus returns a doc whose metadata lacks
    ``eval_id`` (e.g. a collection re-rebuild was partial), the endpoint
    reads the fallback id from ``doc.id`` / ``metadata.pk`` and continues
    instead of silently dropping the row.
    """
    pool = _ResultPgPool()
    store = _ResultStore(metadata={"pk": "eval-1"})  # no eval_id, no trace_id
    monkeypatch.setattr(eval_read.milvus_mgr, "eval_results", store)

    result = await eval_read.eval_vector_search(
        request=_FakeRequest(pool),
        req=eval_read.VectorSearchRequest(kind="result", vector=[0.1], k=1),
        x_openrouter_key=None,
    )

    assert result["items"][0]["eval_id"] == "eval-1"
