"""Regression tests for EvalEmbedder metadata sanitization.

Milvus varchar fields reject None with ``MilvusException(code=1100)``. Python's
``dict.get(k, default)`` returns None when the key exists with a None value — a
footgun because ``ShadowEvalCollector.build_trace_dict`` always emits
``case_id=None`` on non-eval sessions. The metadata now uses ``or ""`` to coerce
every field defensively.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agent_service.eval_store import embedder as embedder_mod


class _FakePool:
    def __init__(self) -> None:
        self.fetchrow = AsyncMock(return_value=None)
        self.execute = AsyncMock(return_value=None)
        self.fetch = AsyncMock(return_value=[])


@pytest.mark.asyncio
async def test_embed_trace_sanitizes_none_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Trace with None values must reach Milvus as empty strings, never None."""
    captured: dict[str, Any] = {}

    class _FakeMilvusCollection:
        async def aadd_documents(self, docs, ids):
            captured["metadata"] = docs[0].metadata
            captured["id"] = ids[0]

    fake_mgr = MagicMock()
    fake_mgr.eval_traces = _FakeMilvusCollection()
    monkeypatch.setattr(embedder_mod, "milvus_mgr", fake_mgr)

    em = embedder_mod.EvalEmbedder.__new__(embedder_mod.EvalEmbedder)
    em.enabled = True
    em.emb = object()  # non-None so the early-return guard passes
    em.key = "fake-key"

    trace = {
        "trace_id": "trace-123",
        "case_id": None,  # the historical bug trigger
        "session_id": None,
        "provider": None,
        "model": None,
        "status": "success",
        "inputs": {"question": "hello"},
        "final_output": "world",
    }

    await em.embed_trace_if_needed(_FakePool(), trace, events=[])

    assert "metadata" in captured, "aadd_documents was not called"
    meta = captured["metadata"]
    # Every varchar metadata field must be a string, never None.
    assert meta["trace_id"] == "trace-123"
    assert meta["case_id"] == ""
    assert meta["session_id"] == ""
    assert meta["provider"] == ""
    assert meta["model"] == ""
    assert meta["status"] == "success"
    assert all(v is not None for v in meta.values()), f"None leaked into metadata: {meta}"


@pytest.mark.asyncio
async def test_embed_trace_swallows_milvus_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Milvus insert failure must be logged and swallowed — never bubbles up.

    The agent stream depends on this: the trace-embed step runs after the user
    response, and any uncaught exception here would corrupt the request task.
    """

    class _BrokenCollection:
        async def aadd_documents(self, docs, ids):
            raise RuntimeError("simulated Milvus failure")

    fake_mgr = MagicMock()
    fake_mgr.eval_traces = _BrokenCollection()
    monkeypatch.setattr(embedder_mod, "milvus_mgr", fake_mgr)

    em = embedder_mod.EvalEmbedder.__new__(embedder_mod.EvalEmbedder)
    em.enabled = True
    em.emb = object()
    em.key = "fake-key"

    trace = {"trace_id": "t-err", "case_id": None, "inputs": {"question": "q"}}

    # Should NOT raise — the existing try/except must absorb the failure.
    await em.embed_trace_if_needed(_FakePool(), trace, events=[])
