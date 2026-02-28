from __future__ import annotations

import io
import json

import pytest
from starlette.datastructures import Headers, UploadFile

from src.agent_service.api import admin


@pytest.mark.asyncio
async def test_get_faqs_contract(monkeypatch):
    async def _list(_pool, *, limit: int, skip: int):
        assert limit == 100
        assert skip == 0
        return [
            {
                "id": "faq-1",
                "question": "Q1",
                "answer": "A1",
                "category": "Billing",
                "tags": ["billing"],
                "vector_status": "synced",
                "vectorized": True,
            }
        ]

    monkeypatch.setattr(admin, "_get_pool", lambda request: object())
    monkeypatch.setattr(admin.knowledge_base_service, "list_faqs", _list)

    result = await admin.get_faqs(request=object(), limit=100, skip=0)

    assert result["count"] == 1
    assert result["items"][0]["question"] == "Q1"
    assert result["items"][0]["id"] == "faq-1"
    assert result["items"][0]["vector_status"] == "synced"


@pytest.mark.asyncio
async def test_get_faq_categories_contract(monkeypatch):
    async def _list_categories(_pool):
        return [
            {"id": "billing", "slug": "billing", "label": "Billing", "is_active": True},
            {"id": "technical", "slug": "technical", "label": "Technical", "is_active": True},
        ]

    monkeypatch.setattr(admin, "_get_pool", lambda request: object())
    monkeypatch.setattr(admin.knowledge_base_service, "list_categories", _list_categories)

    result = await admin.get_faq_categories(request=object())

    assert result["count"] == 2
    assert result["items"][0]["id"] == "billing"


@pytest.mark.asyncio
async def test_semantic_search_accepts_json_body(monkeypatch):
    async def _search(_pool, *, query: str, limit: int):
        assert query == "loan closure"
        assert limit == 7
        return [{"question": "Q", "answer": "A", "score": 0.9}]

    monkeypatch.setattr(admin, "_get_pool", lambda request: object())
    monkeypatch.setattr(admin.knowledge_base_service, "semantic_search", _search)

    payload = admin.SemanticSearchRequest(query="loan closure", limit=7)
    result = await admin.semantic_search_endpoint(
        request=object(),
        payload=payload,
        query=None,
        limit=None,
    )

    assert result["status"] == "success"
    assert len(result["results"]) == 1


@pytest.mark.asyncio
async def test_semantic_search_accepts_query_param(monkeypatch):
    async def _search(_pool, *, query: str, limit: int):
        assert query == "emi"
        assert limit == 5
        return [{"question": "Q", "answer": "A", "score": 0.9}]

    monkeypatch.setattr(admin, "_get_pool", lambda request: object())
    monkeypatch.setattr(admin.knowledge_base_service, "semantic_search", _search)

    result = await admin.semantic_search_endpoint(
        request=object(),
        payload=None,
        query="emi",
        limit=5,
    )

    assert result["status"] == "success"
    assert len(result["results"]) == 1


@pytest.mark.asyncio
async def test_upload_pdf_stream_contract(monkeypatch):
    async def _ingest_pdf(_pool, pdf_bytes: bytes, filename: str):
        assert filename == "faqs.pdf"
        assert pdf_bytes.startswith(b"%PDF")
        return 3

    monkeypatch.setattr(admin, "_get_pool", lambda request: object())
    monkeypatch.setattr(admin.knowledge_base_service, "ingest_pdf_bytes", _ingest_pdf)

    upload = UploadFile(
        file=io.BytesIO(b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF"),
        filename="faqs.pdf",
        headers=Headers({"content-type": "application/pdf"}),
    )

    response = await admin.update_faqs_pdf_stream(request=object(), file=upload)
    events = []
    async for evt in response.body_iterator:
        events.append(evt)

    assert events[-1]["event"] == "done"


@pytest.mark.asyncio
async def test_batch_json_enforces_limit_and_emits_structured_error(monkeypatch):
    monkeypatch.setattr(admin, "_get_pool", lambda request: object())
    monkeypatch.setattr(admin, "KB_FAQ_BATCH_MAX_ITEMS", 1)

    payload = admin.BatchFaqRequest(
        items=[
            admin.FaqItem(question="Q1", answer="A1"),
            admin.FaqItem(question="Q2", answer="A2"),
        ]
    )

    response = await admin.update_faqs_json_stream(payload=payload, request=object())
    events = []
    async for evt in response.body_iterator:
        events.append(evt)

    error_event = next(evt for evt in events if evt["event"] == "error")
    parsed = json.loads(error_event["data"])
    assert parsed["code"] == "faq_batch_ingest_failed"
    assert "exceeds limit" in parsed["detail"].lower()


@pytest.mark.asyncio
async def test_upload_pdf_enforces_size_limit_and_emits_structured_error(monkeypatch):
    monkeypatch.setattr(admin, "_get_pool", lambda request: object())
    monkeypatch.setattr(admin, "KB_FAQ_PDF_MAX_BYTES", 4)

    upload = UploadFile(
        file=io.BytesIO(b"%PDF-1.4\n"),
        filename="faqs.pdf",
        headers=Headers({"content-type": "application/pdf"}),
    )

    response = await admin.update_faqs_pdf_stream(request=object(), file=upload)
    events = []
    async for evt in response.body_iterator:
        events.append(evt)

    error_event = next(evt for evt in events if evt["event"] == "error")
    parsed = json.loads(error_event["data"])
    assert parsed["code"] == "pdf_too_large"
    assert "size limit" in parsed["detail"].lower()


@pytest.mark.asyncio
async def test_edit_faq_accepts_id_identifier(monkeypatch):
    async def _update(
        _pool,
        *,
        faq_id: str | None,
        original_question: str | None,
        new_question: str | None,
        new_answer: str | None,
        new_category: str | None,
        new_tags: list[str] | None,
    ):
        assert faq_id == "faq-1"
        assert original_question is None
        assert new_question == "Q2"
        assert new_answer == "A2"
        assert new_category == "Billing"
        assert new_tags == ["billing", "refund"]
        return True

    monkeypatch.setattr(admin, "_get_pool", lambda request: object())
    monkeypatch.setattr(admin.knowledge_base_service, "update_faq", _update)

    result = await admin.edit_faq(
        request=object(),
        payload=admin.EditFaqRequest(
            id="faq-1",
            new_question="Q2",
            new_answer="A2",
            new_category="Billing",
            new_tags=["billing", "refund"],
        ),
    )

    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_edit_faq_requires_identifier(monkeypatch):
    with pytest.raises(admin.HTTPException) as exc_info:
        await admin.edit_faq(
            request=object(),
            payload=admin.EditFaqRequest(new_answer="A2"),
        )

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_delete_faq_accepts_id_identifier(monkeypatch):
    async def _delete(_pool, *, faq_id: str | None, question: str | None):
        assert faq_id == "faq-1"
        assert question is None
        return 1

    monkeypatch.setattr(admin, "_get_pool", lambda request: object())
    monkeypatch.setattr(admin.knowledge_base_service, "delete_faq", _delete)

    result = await admin.delete_faq_endpoint(request=object(), id="faq-1", question=None)

    assert result["status"] == "success"
