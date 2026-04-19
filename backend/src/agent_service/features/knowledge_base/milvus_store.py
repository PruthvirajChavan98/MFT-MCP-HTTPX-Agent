from __future__ import annotations

import logging
from typing import Any

from langchain_core.documents import Document

from src.common.milvus_mgr import milvus_mgr

from .repo import (
    VECTOR_STATUS_FAILED,
    VECTOR_STATUS_SYNCED,
    VECTOR_STATUS_SYNCING,
    KnowledgeBaseRepo,
    normalize_question,
)

log = logging.getLogger("kb_milvus_store")

_repo = KnowledgeBaseRepo()


class KBMilvusStore:
    """Thin async wrapper around ``milvus_mgr.kb_faqs`` for FAQ vector ops.

    All public methods are fully async — no executor wrappers needed because
    langchain-milvus implements native async via ``aadd_documents``,
    ``asimilarity_search_with_score``, and ``adelete``.
    """

    async def sync_faq(self, pool: Any, item: dict[str, Any]) -> None:
        """Upsert a single FAQ embedding into Milvus and update vector_status in PostgreSQL."""
        question_key: str = str(
            item.get("question_key") or normalize_question(str(item.get("question") or ""))
        )
        if not question_key:
            return

        await _repo.set_vector_status_for_question_keys(
            pool, [question_key], status=VECTOR_STATUS_SYNCING, error=None
        )
        try:
            doc = Document(
                page_content=(f"Question: {item['question']}\nAnswer: {item['answer']}"),
                metadata={
                    "question_key": question_key,
                    "question": item.get("question", ""),
                    "answer": item.get("answer", ""),
                    "category": item.get("category", ""),
                },
            )
            await milvus_mgr.kb_faqs.aadd_documents([doc], ids=[question_key])  # type: ignore[union-attr]
            await _repo.set_vector_status_for_question_keys(
                pool, [question_key], status=VECTOR_STATUS_SYNCED, error=None
            )
        except Exception as exc:
            log.error("Milvus sync_faq failed for key=%s: %s", question_key, exc)
            await _repo.set_vector_status_for_question_keys(
                pool, [question_key], status=VECTOR_STATUS_FAILED, error=str(exc)[:1000]
            )
            raise

    async def sync_all(self, pool: Any, items: list[dict[str, Any]]) -> None:
        """Full resync — clear collection then batch-upsert all FAQs."""
        await self.clear()
        for item in items:
            if item.get("question") and item.get("answer"):
                try:
                    await self.sync_faq(pool, item)
                except Exception:
                    # Individual failures are already logged and status-tracked by sync_faq; continue bulk sync
                    continue

    async def semantic_search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Return top-k FAQ matches by cosine similarity (score 0–1, higher = better).

        Phase F4 (2026-04-18): swapped from langchain-milvus async wrapper to
        raw pymilvus + executor. See milvus_mgr.semantic_search_raw and the
        kb_search.py swap for context.
        """
        results = await milvus_mgr.semantic_search_raw(
            collection="kb_faqs", query=query, limit=limit
        )
        return [
            {
                "question": doc.metadata.get("question", ""),
                "answer": doc.metadata.get("answer", ""),
                "score": float(score),
            }
            for doc, score in results
        ]

    async def clear(self) -> None:
        """Delete all documents from the kb_faqs Milvus collection."""
        try:
            # adelete with expr="" deletes everything (Milvus boolean expr on metadata field)
            await milvus_mgr.kb_faqs.adelete(expr="question_key != ''")  # type: ignore[union-attr]
        except Exception as exc:
            log.warning("Milvus clear (kb_faqs) failed: %s", exc)


_kb_store_instance: KBMilvusStore | None = None


def get_kb_milvus_store() -> KBMilvusStore:
    """Lazy factory for KBMilvusStore singleton. Mockable in tests."""
    global _kb_store_instance
    if _kb_store_instance is None:
        _kb_store_instance = KBMilvusStore()
    return _kb_store_instance


# Backward-compat: existing importers use this module-level name
kb_milvus_store = get_kb_milvus_store()
