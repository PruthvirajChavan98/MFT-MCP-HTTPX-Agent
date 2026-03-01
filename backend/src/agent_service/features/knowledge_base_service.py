from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Iterable

from src.agent_service.features.faq_pdf_parser import coerce_json_items, parse_pdf_faqs
from src.agent_service.features.knowledge_base_repo import (
    VECTOR_STATUS_FAILED,
    VECTOR_STATUS_SYNCED,
    VECTOR_STATUS_SYNCING,
    KnowledgeBaseRepo,
    normalize_question,
)

log = logging.getLogger("knowledge_base_service")


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _normalize_cognee_results(raw: Any, limit: int) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    rows: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            question = _to_text(item.get("question") or item.get("title") or item.get("query"))
            answer = _to_text(item.get("answer") or item.get("content") or item.get("text"))
            score = item.get("score")
            try:
                score_val = float(score) if score is not None else 0.75
            except Exception:
                score_val = 0.75
            if question or answer:
                rows.append(
                    {
                        "question": question,
                        "answer": answer,
                        "score": score_val,
                    }
                )
                continue
        text = _to_text(item)
        if text:
            rows.append({"question": "", "answer": text, "score": 0.5})

    return rows[:limit]


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
        sync_cognee: bool = True,
    ) -> int:
        rows = list(items)
        count = await self.repo.upsert_many(
            pool,
            rows,
            source=source,
            source_ref=source_ref,
        )
        if sync_cognee and count > 0:
            all_rows = await self.repo.dump_all(pool)
            await self._sync_to_cognee(pool, all_rows)
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
            asyncio.create_task(
                self._sync_to_cognee(pool, all_rows),
                name="cognee_sync_after_update",
            )
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
            asyncio.create_task(
                self._sync_to_cognee(pool, all_rows),
                name="cognee_sync_after_delete",
            )
        return deleted

    async def clear_all(self, pool: Any) -> int:
        deleted = await self.repo.delete_all(pool)
        await self._reset_cognee_index()
        return deleted

    async def semantic_search(
        self, pool: Any, *, query: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        query_text = (query or "").strip()
        if not query_text:
            return []

        try:
            import cognee

            try:
                raw = await cognee.search(
                    query_text=query_text,
                    query_type=cognee.SearchType.GRAPH_COMPLETION,
                )
            except TypeError:
                raw = await cognee.search(
                    query=query_text,
                    search_type=cognee.SearchType.GRAPH_COMPLETION,
                )

            rows = _normalize_cognee_results(raw, limit)
            if rows:
                return rows
        except Exception as exc:  # noqa: BLE001
            log.warning("Cognee semantic search failed, using local fallback: %s", exc)

        return await self.repo.search_local(pool, query_text, limit=limit)

    async def semantic_delete(self, pool: Any, *, query: str, threshold: float = 0.9) -> int:
        query_text = (query or "").strip().lower()
        if not query_text:
            return 0

        rows = await self.repo.dump_all(pool)
        to_delete = []
        for row in rows:
            score = 1.0 if query_text in row["question"].lower() else 0.0
            if score >= threshold:
                to_delete.append(row)
        if not to_delete:
            return 0

        deleted = 0
        for row in to_delete:
            deleted += await self.repo.delete_one(pool, question=row["question"])

        all_rows = await self.repo.dump_all(pool)
        await self._sync_to_cognee(pool, all_rows)
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

    async def _sync_to_cognee(self, pool: Any, items: list[dict[str, Any]]) -> None:
        question_keys = [
            str(item.get("question_key") or normalize_question(str(item.get("question") or "")))
            for item in items
            if str(item.get("question") or "").strip() and str(item.get("answer") or "").strip()
        ]
        if question_keys:
            await self.repo.set_vector_status_for_question_keys(
                pool,
                question_keys,
                status=VECTOR_STATUS_SYNCING,
                error=None,
            )

        try:
            import cognee

            await self._reset_cognee_index()
            if not items:
                return

            docs = [
                f"Question: {i['question']}\nAnswer: {i['answer']}"
                for i in items
                if i.get("question") and i.get("answer")
            ]
            if not docs:
                return

            try:
                await cognee.add(data=docs)
            except TypeError:
                await cognee.add(docs)

            try:
                await cognee.cognify()
            except TypeError:
                await cognee.cognify(data=docs)

            if question_keys:
                await self.repo.set_vector_status_for_question_keys(
                    pool,
                    question_keys,
                    status=VECTOR_STATUS_SYNCED,
                    error=None,
                )
        except Exception as exc:  # noqa: BLE001
            if question_keys:
                await self.repo.set_vector_status_for_question_keys(
                    pool,
                    question_keys,
                    status=VECTOR_STATUS_FAILED,
                    error=str(exc)[:1000],
                )
            log.warning("Cognee sync failed: %s", exc)

    async def _reset_cognee_index(self) -> None:
        try:
            import cognee

            # API compatibility across versions.
            try:
                await cognee.delete()
            except TypeError:
                try:
                    await cognee.delete(dataset_name="default")
                except TypeError:
                    pass
        except Exception as exc:  # noqa: BLE001
            log.warning("Cognee reset failed: %s", exc)


knowledge_base_service = KnowledgeBaseService()
