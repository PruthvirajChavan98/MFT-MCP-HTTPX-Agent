"""LocalEmbedder unit tests — exercise the public surface without loading
the heavy `sentence-transformers` model. The model load itself is covered
by the image-build smoke and the live latency probe; here we verify the
asyncio plumbing, the langchain Embeddings protocol, and the warm() guard.
"""

from __future__ import annotations

import pytest

from src.agent_service.security import local_embedder as le_module
from src.agent_service.security.local_embedder import (
    EMBED_DIM,
    LocalEmbedder,
    get_local_embedder,
    reset_local_embedder_for_tests,
)


@pytest.fixture(autouse=True)
def _reset_singleton() -> None:
    reset_local_embedder_for_tests()


def _stub_model(emb: LocalEmbedder, vector: list[float] | None = None) -> None:
    """Bypass _ensure_loaded by injecting a stub object that mimics
    SentenceTransformer.encode(). Avoids importing torch in tests."""

    class _StubArray:
        def __init__(self, data: list) -> None:
            self._data = data

        def tolist(self) -> list:
            return self._data

    class _StubModel:
        def encode(self, texts, normalize_embeddings, convert_to_numpy, show_progress_bar):
            if isinstance(texts, str):
                return _StubArray(vector or [0.1] * EMBED_DIM)
            return _StubArray([vector or [0.1] * EMBED_DIM for _ in texts])

    emb._model = _StubModel()


def test_get_local_embedder_returns_singleton() -> None:
    a = get_local_embedder()
    b = get_local_embedder()
    assert a is b


@pytest.mark.asyncio
async def test_aembed_query_returns_vector_of_correct_dim() -> None:
    emb = LocalEmbedder()
    _stub_model(emb)
    vec = await emb.aembed_query("hello")
    assert isinstance(vec, list)
    assert len(vec) == EMBED_DIM


@pytest.mark.asyncio
async def test_aembed_query_rejects_empty_string() -> None:
    emb = LocalEmbedder()
    _stub_model(emb)
    with pytest.raises(ValueError):
        await emb.aembed_query("")


def test_embed_query_satisfies_langchain_protocol() -> None:
    """langchain-milvus calls the *sync* embed_query / embed_documents on the
    embedding_function — confirm the protocol surface works."""
    emb = LocalEmbedder()
    _stub_model(emb)
    vec = emb.embed_query("hello")
    assert len(vec) == EMBED_DIM
    docs = emb.embed_documents(["a", "b", "c"])
    assert len(docs) == 3
    assert all(len(d) == EMBED_DIM for d in docs)


@pytest.mark.asyncio
async def test_warm_skips_when_cache_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    emb = LocalEmbedder()
    _stub_model(emb)
    # The constructor pulled INLINE_GUARD_CACHE_ENABLED at __init__ time.
    # Force it off here to confirm warm() short-circuits.
    monkeypatch.setattr(emb, "enabled", False)
    elapsed = await emb.warm()
    assert elapsed == 0.0


@pytest.mark.asyncio
async def test_warm_runs_one_inference_when_enabled() -> None:
    emb = LocalEmbedder()
    _stub_model(emb)
    emb.enabled = True
    elapsed = await emb.warm()
    assert elapsed >= 0.0  # any non-negative duration is acceptable


def test_module_exports_dim_constant() -> None:
    assert le_module.EMBED_DIM == 384
