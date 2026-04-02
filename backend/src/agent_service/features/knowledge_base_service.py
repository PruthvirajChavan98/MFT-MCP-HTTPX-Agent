from __future__ import annotations

import logging
from typing import Any, Iterable

from src.agent_service.features.faq_pdf_parser import coerce_json_items, parse_pdf_faqs
from src.agent_service.features.kb_milvus_store import kb_milvus_store
from src.agent_service.features.knowledge_base_repo import KnowledgeBaseRepo

log = logging.getLogger("knowledge_base_service")


class KnowledgeBaseService:
    def __init__(self) -> None:
        self.repo = KnowledgeBaseRepo()

    async def list_faqs(self, pool: Any, limit: int, skip: int) -> list[dict[str, Any]]:
        return await self.repo.list_faqs(pool, limit=limit, skip=skip)

    async def list_categories(self, pool: Any) -> list[dict[str, Any]]:
        return await self.repo.list_categories(pool)

    async def upsert_items(
        self,
        pool: Any,
        items: Iterable[dict[str, Any]],
        *,
        source: str,
        source_ref: str | None = None,
        sync_milvus: bool = True,
    ) -> int:
        rows = list(items)
        count = await self.repo.upsert_many(
            pool,
            rows,
            source=source,
            source_ref=source_ref,
        )
        if sync_milvus and count > 0:
            all_rows = await self.repo.dump_all(pool)
            await self._sync_to_milvus(pool, all_rows)
        return count

    async def update_faq(
        self,
        pool: Any,
        *,
        faq_id: str | None,
        original_question: str | None,
        new_question: str | None,
        new_answer: str | None,
        new_category: str | None,
        new_tags: list[str] | None,
    ) -> bool:
        updated = await self.repo.update_one(
            pool,
            faq_id=faq_id,
            original_question=original_question,
            new_question=new_question,
            new_answer=new_answer,
            new_category=new_category,
            new_tags=new_tags,
        )
        if updated:
            all_rows = await self.repo.dump_all(pool)
            await self._sync_to_milvus(pool, all_rows)
        return updated

    async def delete_faq(
        self,
        pool: Any,
        *,
        faq_id: str | None = None,
        question: str | None = None,
    ) -> int:
        deleted = await self.repo.delete_one(pool, faq_id=faq_id, question=question)
        if deleted > 0:
            all_rows = await self.repo.dump_all(pool)
            await self._sync_to_milvus(pool, all_rows)
        return deleted

    async def clear_all(self, pool: Any) -> int:
        deleted = await self.repo.delete_all(pool)
        await kb_milvus_store.clear()
        return deleted

    async def semantic_search(
        self, pool: Any, *, query: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        query_text = (query or "").strip()
        if not query_text:
            return []

        try:
            rows = await kb_milvus_store.semantic_search(query_text, limit=limit)
            if rows:
                return rows
        except Exception as exc:  # noqa: BLE001
            log.warning("Milvus semantic search failed, using local fallback: %s", exc)

        return await self.repo.search_local(pool, query_text, limit=limit)

    async def semantic_delete(self, pool: Any, *, query: str, threshold: float = 0.9) -> int:
        query_text = (query or "").strip().lower()
        if not query_text:
            return 0

        try:
            results = await kb_milvus_store.semantic_search(query_text, limit=100)
            to_delete = [r for r in results if r["score"] >= threshold]
        except Exception as exc:  # noqa: BLE001
            log.warning("Milvus semantic delete search failed, falling back to substring: %s", exc)
            rows = await self.repo.dump_all(pool)
            to_delete = [
                {"question": row["question"]}
                for row in rows
                if query_text in row["question"].lower()
            ]

        if not to_delete:
            return 0

        deleted = 0
        for item in to_delete:
            deleted += await self.repo.delete_one(pool, question=item["question"])

        all_rows = await self.repo.dump_all(pool)
        await self._sync_to_milvus(pool, all_rows)
        return deleted

    async def ingest_json_payload(self, pool: Any, payload: Any) -> int:
        items = coerce_json_items(payload)
        return await self.upsert_items(pool, items, source="json_batch")

    async def ingest_pdf_bytes(self, pool: Any, pdf_bytes: bytes, filename: str) -> int:
        items = parse_pdf_faqs(pdf_bytes)
        return await self.upsert_items(
            pool,
            items,
            source="pdf_upload",
            source_ref=filename,
        )

    async def _sync_to_milvus(self, pool: Any, items: list[dict[str, Any]]) -> None:
        """Full resync of all FAQ embeddings to Milvus kb_faqs collection."""
        try:
            await kb_milvus_store.sync_all(pool, items)
        except Exception as exc:  # noqa: BLE001
            log.warning("Milvus sync failed: %s", exc)


knowledge_base_service = KnowledgeBaseService()
