"""Backend-agnostic vector store manager.

Replaces the hard Milvus dependency in `milvus_mgr.py` with a runtime-pickable
backend (`VECTOR_STORE_BACKEND=milvus|pgvector`). Same singleton shape as
the old MilvusManager, so call sites swap one import and nothing else.

Default is **milvus** to keep merge risk-free. Flip the env to **pgvector**
once the live Postgres has the extension installed and the data migration
script has populated the `embedding` columns / new pgvector tables.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.agent_service.core.config import (
    INLINE_GUARD_CACHE_ENABLED,
    OPENROUTER_API_KEY,
    VECTOR_STORE_BACKEND,
)

log = logging.getLogger("vector_store_manager")


class VectorStoreManager:
    """Singleton container of four vector-store handles.

    Attributes (`kb_faqs`, `eval_traces`, `eval_results`, `guard_cache`)
    expose the langchain-milvus async surface (`aadd_documents`,
    `asimilarity_search_with_score`, `asimilarity_search_with_score_by_vector`,
    `adelete`) regardless of which backend is wired underneath.
    """

    def __init__(self) -> None:
        self.kb_faqs: Any = None
        self.eval_traces: Any = None
        self.eval_results: Any = None
        self.guard_cache: Any = None
        self._backend: str = ""

    @property
    def backend(self) -> str:
        return self._backend

    async def aconnect(self) -> None:
        backend = VECTOR_STORE_BACKEND
        if backend == "pgvector":
            await self._init_pgvector()
        else:
            # Anything else (including the explicit "milvus" default) routes
            # to the Milvus backend. We keep this branch wide so a typo in
            # the env doesn't accidentally break prod.
            if backend != "milvus":
                log.warning(
                    "VECTOR_STORE_BACKEND=%r unrecognised — falling back to milvus",
                    backend,
                )
            await self._init_milvus()
        self._backend = backend if backend in {"milvus", "pgvector"} else "milvus"
        log.info(
            "Vector store manager ready — backend=%s collections=[kb_faqs, eval_traces_emb, eval_results_emb%s]",
            self._backend,
            (
                ", inline_guard_cache"
                if (INLINE_GUARD_CACHE_ENABLED or self._backend == "pgvector")
                else ""
            ),
        )

    async def _init_milvus(self) -> None:
        # Re-use the existing manager to keep the milvus path identical.
        from src.common.milvus_mgr import milvus_mgr

        await milvus_mgr.aconnect()
        self.kb_faqs = milvus_mgr.kb_faqs
        self.eval_traces = milvus_mgr.eval_traces
        self.eval_results = milvus_mgr.eval_results
        self.guard_cache = milvus_mgr.guard_cache

    async def _init_pgvector(self) -> None:
        # Build the four pgvector stores. Each uses a different embedder:
        #   kb_faqs / eval_traces / eval_results → owner OpenRouter embedder
        #   inline_guard_cache → local MiniLM (only loaded if cache enabled)
        from src.agent_service.eval_store.pg_vector_store import (
            PgEvalResultsStore,
            PgEvalTracesStore,
            PgInlineGuardCacheStore,
            PgKbFaqsStore,
        )
        from src.agent_service.llm.client import get_owner_embeddings

        if not OPENROUTER_API_KEY:
            raise RuntimeError(
                "VECTOR_STORE_BACKEND=pgvector requires OPENROUTER_API_KEY for the "
                "1536-dim embedder used by kb_faqs / eval_traces / eval_results."
            )

        owner_embedder = get_owner_embeddings()

        # Run the lazy embedder load off the event loop so we don't block
        # FastAPI startup behind langchain initialisation.
        loop = asyncio.get_running_loop()

        def _build_owner_stores() -> tuple[Any, Any, Any]:
            return (
                PgKbFaqsStore(embedder=owner_embedder),
                PgEvalTracesStore(embedder=owner_embedder),
                PgEvalResultsStore(embedder=owner_embedder),
            )

        kb, ev_t, ev_r = await loop.run_in_executor(None, _build_owner_stores)
        self.kb_faqs = kb
        self.eval_traces = ev_t
        self.eval_results = ev_r

        if INLINE_GUARD_CACHE_ENABLED:
            from src.agent_service.security.local_embedder import get_local_embedder

            self.guard_cache = PgInlineGuardCacheStore(embedder=get_local_embedder())
        else:
            self.guard_cache = None

    async def close(self) -> None:
        if self._backend == "milvus":
            from src.common.milvus_mgr import milvus_mgr

            await milvus_mgr.close()
        # pgvector path uses the shared Postgres pool — closed by app lifespan.


vector_store_mgr = VectorStoreManager()
