from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from pydantic import SecretStr

from src.agent_service.core.config import (
    MILVUS_TOKEN,
    MILVUS_URI,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
)

if TYPE_CHECKING:
    from langchain_core.documents import Document
    from langchain_milvus import Milvus

log = logging.getLogger("milvus_manager")

_EMBED_MODEL: str = "openai/text-embedding-3-small"


def _make_embeddings(api_key: str):  # type: ignore[return]  # circular import avoidance
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(
        model=_EMBED_MODEL,
        api_key=SecretStr(api_key),
        base_url=OPENROUTER_BASE_URL,
        # Disable context-length pre-check — not applicable to OpenRouter proxy
        check_embedding_ctx_length=False,
    )


def _make_store(collection_name: str, api_key: str) -> "Milvus":
    from langchain_milvus import Milvus
    from pymilvus import MilvusClient
    from pymilvus.orm.connections import connections as _orm_connections

    conn_args: dict = {"uri": MILVUS_URI}
    if MILVUS_TOKEN:
        conn_args["token"] = MILVUS_TOKEN

    # langchain-milvus 0.3.x + pymilvus 2.6.x compat:
    # MilvusClient._using = "cm-{id(handler)}" — NOT registered in the legacy ORM
    # connections._alias_handlers that Collection(using=alias) looks up.
    # ConnectionManager.get_or_create returns the same handler for identical args,
    # so the alias we register here equals the one Milvus() will use internally.
    _mc = MilvusClient(**conn_args)
    _orm_connections._alias_handlers[_mc._using] = _mc._handler

    return Milvus(
        embedding_function=_make_embeddings(api_key),
        collection_name=collection_name,
        connection_args=conn_args,
        # Never wipe existing data on startup
        drop_old=False,
        # Use document ID as primary key
        auto_id=False,
        # Cosine similarity — required for semantic search scores in [−1, 1]
        # (L2 default returns raw Euclidean distances, not interpretable as %)
        index_params={
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {"M": 16, "efConstruction": 200},
        },
        search_params={"metric_type": "COSINE", "params": {"ef": 50}},
    )


class MilvusManager:
    """Manages three Milvus LangChain VectorStore instances.

    Collections:
    - ``kb_faqs``         — FAQ knowledge base (replaces Cognee)
    - ``eval_traces_emb`` — eval trace embeddings
    - ``eval_results_emb``— eval result embeddings

    All collections use ``langchain-milvus`` async API:
    ``aadd_documents``, ``asimilarity_search_with_score``, ``adelete``.
    """

    def __init__(self) -> None:
        self.kb_faqs: "Milvus | None" = None
        self.eval_traces: "Milvus | None" = None
        self.eval_results: "Milvus | None" = None

    async def aconnect(self) -> None:
        """Initialize all three Milvus stores (runs blocking init in executor).

        Connectivity is implicitly validated by _init_stores — if Milvus is unreachable
        the Milvus() constructor raises and propagates to the lifespan handler.
        """
        api_key = OPENROUTER_API_KEY or ""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._init_stores, api_key)
        log.info(
            "Milvus stores ready — uri=%s collections=[kb_faqs, eval_traces_emb, eval_results_emb]",
            MILVUS_URI,
        )

    def _init_stores(self, api_key: str) -> None:
        self.kb_faqs = _make_store("kb_faqs", api_key)
        self.eval_traces = _make_store("eval_traces_emb", api_key)
        self.eval_results = _make_store("eval_results_emb", api_key)

    async def close(self) -> None:
        # langchain-milvus manages Milvus connections internally; nothing to close explicitly.
        pass

    async def semantic_search_raw(
        self,
        *,
        collection: str,
        query: str = "",
        query_vector: list[float] | None = None,
        limit: int = 5,
        output_fields: list[str] | None = None,
        expr: str | None = None,
    ) -> list[tuple["Document", float]]:
        """Bypass ``langchain-milvus`` async search — use raw pymilvus + executor.

        The ``asimilarity_search_with_score`` wrapper on ``langchain-milvus
        0.3.3`` + ``pymilvus 2.6.11`` hangs indefinitely on hot paths
        (confirmed live 2026-04-18 with 30 s timeout). Every sub-step works
        in isolation: OpenRouter embed (~2 s) + raw ``Collection.search``
        (~0.5 s) both return cleanly. This helper composes those working
        primitives so callers don't pay the hang.

        Return shape matches ``asimilarity_search_with_score`` so callers
        can substitute in-place: ``list[tuple[Document, float]]``.

        Args:
            collection: Milvus collection name (e.g. ``"kb_faqs"``).
            query: natural-language query text.
            limit: top-k matches to return.
            output_fields: scalar fields to project back as ``Document``
                metadata. Defaults to ``["question", "answer", "text"]``
                to cover both kb_faqs (question/answer) and the eval-trace
                embedders (text).
        """
        from langchain_core.documents import Document
        from pymilvus import Collection, connections

        # Caller can supply either a text query (we embed it) or a pre-computed
        # vector (we skip the embed). At least one must be meaningful.
        stripped = (query or "").strip()
        if query_vector is None and not stripped:
            return []

        conn_args: dict[str, Any] = {"uri": MILVUS_URI}
        if MILVUS_TOKEN:
            conn_args["token"] = MILVUS_TOKEN

        # Idempotent connection — pymilvus `connect` is safe to call repeatedly
        # with the same args on the same alias.
        try:
            connections.connect(alias="default", **conn_args)
        except Exception as exc:  # noqa: BLE001
            log.debug("milvus default alias already connected or connect failed: %s", exc)

        if query_vector is not None:
            query_vec = query_vector
        else:
            api_key = OPENROUTER_API_KEY or ""
            emb = _make_embeddings(api_key)
            query_vec = await emb.aembed_query(stripped)

        fields_to_project = output_fields or ["question", "answer", "text"]

        def _search_sync() -> list[tuple[Document, float]]:
            col = Collection(collection, using="default")
            col.load()  # safe to call if already loaded
            search_kwargs: dict[str, Any] = {
                "data": [query_vec],
                "anns_field": "vector",
                "param": {"metric_type": "COSINE", "params": {"ef": 50}},
                "limit": limit,
                "output_fields": fields_to_project,
            }
            if expr:
                search_kwargs["expr"] = expr
            hits = col.search(**search_kwargs)
            out: list[tuple[Document, float]] = []
            for hit in hits[0]:
                metadata: dict[str, Any] = {}
                for f in fields_to_project:
                    try:
                        metadata[f] = hit.entity.get(f)
                    except Exception:  # noqa: BLE001
                        metadata[f] = None
                metadata["pk"] = hit.id
                # Prefer "text" (eval traces) → "question" (kb_faqs) for page_content.
                page_content = metadata.get("text") or metadata.get("question") or ""
                out.append(
                    (Document(page_content=page_content, metadata=metadata), float(hit.score))
                )
            return out

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _search_sync)


milvus_mgr = MilvusManager()
