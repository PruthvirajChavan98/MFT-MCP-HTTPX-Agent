"""Regression test: EmbeddingsRouter.classify must always return a reason dict.

Before the fix, ``reason_res`` was left as ``None`` whenever ``need_reason``
evaluated False (non-ops intent + non-negative sentiment). The downstream
collector projected that None into ``router_reason=NULL`` in eval_traces,
which the dashboard's SQL CASE then bucketed as "other" — producing the 98%
Uncategorized dashboard.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.agent_service.features.routing.nbfc_router import (
    EmbeddingsRouter,
    _ProtoBank,
)


def _fake_bank(labels: list[str], dim: int = 8) -> _ProtoBank:
    # Each label gets a distinct unit vector so cosine similarity is deterministic.
    vectors = {}
    for i, lab in enumerate(labels):
        v = np.zeros(dim, dtype=np.float32)
        v[i % dim] = 1.0
        vectors[lab] = [v]
    return _ProtoBank(vectors=vectors)


@pytest.mark.asyncio
async def test_classify_returns_reason_dict_even_without_ops_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-ops-intent + positive sentiment query must still yield a reason dict."""
    router = EmbeddingsRouter(embed_model="stub")

    # Pre-fill banks and mark ready so ensure_ready is a no-op.
    router._sent_bank = _fake_bank(["positive", "negative", "neutral", "mixed"])
    router._reason_bank = _fake_bank(["lead_intent_new_loan", "fraud_security", "unknown"])
    router._ready = True

    # Stub _embed_query to return a vector that maximally overlaps with "positive"
    async def _fake_embed_query(self: EmbeddingsRouter, text: str, api_key: str) -> np.ndarray:
        v = np.zeros(8, dtype=np.float32)
        v[0] = 1.0  # aligns with first label (positive)
        return v

    monkeypatch.setattr(EmbeddingsRouter, "_embed_query", _fake_embed_query)

    async def _noop_ensure_ready(self: EmbeddingsRouter, api_key: str) -> None:
        return None

    monkeypatch.setattr(EmbeddingsRouter, "ensure_ready", _noop_ensure_ready)

    # A benign query that does NOT trigger OPS_INTENT_RE and should yield
    # positive sentiment → need_reason=False → pre-fix returned reason=None.
    result = await router.classify("hello there, how are you?", api_key="fake-key")

    assert result["backend"] == "embeddings"
    assert isinstance(
        result["reason"], dict
    ), f"reason must always be a dict (never None); got {result['reason']!r}"
    assert result["reason"].get("label"), "reason.label must be present"
    # When need_reason=False, the canonical placeholder is 'unknown'.
    assert result["reason"]["label"] == "unknown"
    assert result["reason"]["score"] == 0.0
    assert result["reason"]["topk"] == []
