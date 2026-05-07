"""Local CPU embedder for the inline-guard vector cache (Layer 2.5).

The OpenRouter `text-embedding-3-small` round-trip is ~325 ms p50 — the same
order of magnitude as the Groq Safeguard classifier the cache would front, so
that embedder makes the cache a wash on hits and a regression on misses.

`sentence-transformers/all-MiniLM-L6-v2` runs locally on CPU at ~10–15 ms with
no network round-trip, which is what makes the cache pay off.

Design notes:
  * `SentenceTransformer.encode` is synchronous — we run it in the asyncio
    default executor so the event loop stays responsive under concurrent load.
  * Lazy singleton — `get_local_embedder()` is the only public accessor. Tests
    mock at this boundary.
  * `enabled` is False whenever `INLINE_GUARD_CACHE_ENABLED` is False so the
    Dockerfile preload step is the only place the model gets loaded in that
    deployment shape; runtime never imports `sentence_transformers` when the
    cache is off.
  * `aembed_query` returns L2-normalised vectors so cosine similarity in
    Milvus reduces to a dot product (cheaper, semantically identical).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from prometheus_client import Histogram

from src.agent_service.core.config import (
    INLINE_GUARD_CACHE_ENABLED,
    LOCAL_EMBEDDER_MODEL,
    LOCAL_EMBEDDER_VERSION,
)

log = logging.getLogger(__name__)

LOCAL_EMBEDDER_SECONDS = Histogram(
    "agent_inline_guard_embedder_seconds",
    "Local embedder inference latency for the inline-guard vector cache.",
    ["model"],
)

EMBED_DIM = 384  # MiniLM-L6-v2


class LocalEmbedder:
    """Thin async wrapper over a CPU-resident SentenceTransformer."""

    def __init__(self) -> None:
        self.model_name = LOCAL_EMBEDDER_MODEL
        self.version = LOCAL_EMBEDDER_VERSION
        self.enabled = INLINE_GUARD_CACHE_ENABLED
        self._model: Any = None  # SentenceTransformer | None — typed Any to avoid hard import

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        # Defer the import so disabled deployments never pay the import cost.
        from sentence_transformers import SentenceTransformer  # noqa: WPS433

        log.info("[local_embedder] Loading %s onto CPU…", self.model_name)
        start = time.perf_counter()
        self._model = SentenceTransformer(self.model_name, device="cpu")
        elapsed_ms = (time.perf_counter() - start) * 1000
        log.info("[local_embedder] Loaded %s in %.0f ms", self.model_name, elapsed_ms)

    def _encode_sync(self, text: str) -> list[float]:
        self._ensure_loaded()
        # `encode` accepts a single string and returns a numpy array; .tolist()
        # gives us a Python list[float] suitable for Milvus.
        vec = self._model.encode(  # type: ignore[union-attr]
            text,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vec.tolist()

    def _encode_batch_sync(self, texts: list[str]) -> list[list[float]]:
        self._ensure_loaded()
        vecs = self._model.encode(  # type: ignore[union-attr]
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vecs.tolist()

    # ── langchain-core Embeddings protocol — sync + async, query + documents ──
    # langchain-milvus calls these, so LocalEmbedder is a drop-in
    # `embedding_function` for the Milvus wrapper without an adapter class.

    def embed_query(self, text: str) -> list[float]:
        if not text:
            raise ValueError("embed_query requires non-empty text")
        with LOCAL_EMBEDDER_SECONDS.labels(model=self.version).time():
            return self._encode_sync(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        with LOCAL_EMBEDDER_SECONDS.labels(model=self.version).time():
            return self._encode_batch_sync(texts)

    async def aembed_query(self, text: str) -> list[float]:
        """Embed a single short prompt; returns 384-dim L2-normalised float list."""
        if not text:
            raise ValueError("aembed_query requires non-empty text")
        loop = asyncio.get_running_loop()
        with LOCAL_EMBEDDER_SECONDS.labels(model=self.version).time():
            return await loop.run_in_executor(None, self._encode_sync, text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        loop = asyncio.get_running_loop()
        with LOCAL_EMBEDDER_SECONDS.labels(model=self.version).time():
            return await loop.run_in_executor(None, self._encode_batch_sync, texts)

    async def warm(self) -> float:
        """Run one inference at startup so the first request doesn't pay the
        cold-load cost. Returns elapsed seconds for telemetry."""
        if not self.enabled:
            return 0.0
        start = time.perf_counter()
        await self.aembed_query("warmup")
        elapsed = time.perf_counter() - start
        log.info("[local_embedder] Warm completed in %.3f s", elapsed)
        return elapsed


_singleton: LocalEmbedder | None = None


def get_local_embedder() -> LocalEmbedder:
    """Lazy singleton — instantiate on first call."""
    global _singleton
    if _singleton is None:
        _singleton = LocalEmbedder()
    return _singleton


def reset_local_embedder_for_tests() -> None:
    """Test-only: clear the singleton so tests can re-init with mocks."""
    global _singleton
    _singleton = None
