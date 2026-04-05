import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from src.agent_service.api.admin_auth import require_admin_key
from src.agent_service.core.config import KB_FAQ_BATCH_MAX_ITEMS, KB_FAQ_PDF_MAX_BYTES
from src.agent_service.features.knowledge_base.service import knowledge_base_service

log = logging.getLogger("admin_api")
router = APIRouter(dependencies=[Depends(require_admin_key)])


class FaqItem(BaseModel):
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    category: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class BatchFaqRequest(BaseModel):
    items: list[FaqItem]


class EditFaqRequest(BaseModel):
    id: Optional[str] = Field(default=None, min_length=1)
    original_question: Optional[str] = Field(default=None, min_length=1)
    new_question: Optional[str] = None
    new_answer: Optional[str] = None
    new_category: Optional[str] = None
    new_tags: Optional[list[str]] = None


class SemanticDeleteRequest(BaseModel):
    query: str = Field(..., min_length=1)
    threshold: float = Field(default=0.9, ge=0.0, le=1.0)


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=5, ge=1, le=50)


def _classify_kb_error(message: str) -> tuple[int, str]:
    msg = (message or "").lower()
    if "openrouter key required" in msg or msg.strip() == "key required":
        return 400, "missing_openrouter_key"
    if "milvus" in msg and (
        "connection refused" in msg
        or "couldn't connect" in msg
        or "unavailable" in msg
        or "failed after" in msg
    ):
        return 503, "vector_store_unavailable"
    if "postgres" in msg or "pool unavailable" in msg:
        return 503, "postgres_unavailable"
    return 500, "kb_operation_failed"


def _raise_kb_http_error(operation: str, message: str) -> None:
    status_code, code = _classify_kb_error(message)
    raise HTTPException(
        status_code=status_code,
        detail={
            "code": code,
            "operation": operation,
            "message": message,
        },
    )


def _get_pool(request: Request):
    pool_manager = getattr(request.app.state, "postgres_pool", None)
    pool = getattr(pool_manager, "pool", None) if pool_manager else None
    if pool is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "postgres_unavailable",
                "operation": "knowledge_base",
                "message": "PostgreSQL pool unavailable. Configure POSTGRES_DSN for FAQ persistence.",
            },
        )
    return pool


def _sse_error_payload(
    *,
    message: str,
    code: str,
    operation: str,
    detail: Optional[str] = None,
) -> str:
    payload = {
        "message": message,
        "code": code,
        "operation": operation,
    }
    if detail:
        payload["detail"] = detail
    return json.dumps(payload)


@router.post("/agent/admin/faqs/semantic-search")
async def semantic_search_endpoint(
    request: Request,
    payload: SemanticSearchRequest | None = None,
    query: Optional[str] = Query(default=None, min_length=1),
    limit: Optional[int] = Query(default=None, ge=1, le=50),
):
    try:
        pool = _get_pool(request)
        final_query = (payload.query if payload else query) or ""
        final_limit = (payload.limit if payload else None) or limit or 5
        results = await knowledge_base_service.semantic_search(
            pool,
            query=final_query,
            limit=final_limit,
        )
        return {"status": "success", "results": results}
    except Exception as e:  # noqa: BLE001
        _raise_kb_http_error("semantic_search", str(e))


@router.post("/agent/admin/faqs/batch-json")
async def update_faqs_json_stream(payload: BatchFaqRequest, request: Request):
    pool = _get_pool(request)

    async def _events():
        try:
            if len(payload.items) > KB_FAQ_BATCH_MAX_ITEMS:
                raise ValueError(f"Batch size exceeds limit ({KB_FAQ_BATCH_MAX_ITEMS} items max).")

            yield {"event": "message", "data": "Validating FAQ payload..."}
            count = await knowledge_base_service.upsert_items(
                pool,
                [item.model_dump() for item in payload.items],
                source="json_batch",
            )
            yield {"event": "message", "data": f"Ingested {count} FAQ entries."}
            yield {"event": "done", "data": "complete"}
        except Exception as exc:  # noqa: BLE001
            log.exception("FAQ batch ingest failed: %s", exc)
            yield {
                "event": "error",
                "data": _sse_error_payload(
                    message="Batch FAQ ingest failed.",
                    code="faq_batch_ingest_failed",
                    operation="batch_json",
                    detail=str(exc),
                ),
            }
            yield {"event": "done", "data": "failed"}

    return EventSourceResponse(_events(), headers={"Cache-Control": "no-cache"})


@router.post("/agent/admin/faqs/upload-pdf")
async def update_faqs_pdf_stream(request: Request, file: UploadFile = File(...)):
    pool = _get_pool(request)

    async def _events():
        try:
            if file.content_type not in {"application/pdf", "application/octet-stream"}:
                raise ValueError("Only PDF files are supported.")

            yield {"event": "message", "data": "Reading PDF..."}
            payload = await file.read()
            if not payload:
                raise ValueError("Uploaded PDF is empty.")
            if len(payload) > KB_FAQ_PDF_MAX_BYTES:
                raise ValueError(f"PDF exceeds size limit ({KB_FAQ_PDF_MAX_BYTES} bytes max).")

            yield {"event": "message", "data": "Extracting Question/Answer pairs..."}
            count = await knowledge_base_service.ingest_pdf_bytes(
                pool,
                payload,
                filename=file.filename or "upload.pdf",
            )
            yield {"event": "message", "data": f"Ingested {count} FAQ entries from PDF."}
            yield {"event": "done", "data": "complete"}
        except Exception as exc:  # noqa: BLE001
            log.exception("FAQ PDF ingest failed: %s", exc)
            code = "faq_pdf_ingest_failed"
            if "Only PDF files are supported." in str(exc):
                code = "unsupported_file_type"
            elif "empty" in str(exc).lower():
                code = "empty_pdf"
            elif "size limit" in str(exc).lower():
                code = "pdf_too_large"

            yield {
                "event": "error",
                "data": _sse_error_payload(
                    message="PDF FAQ ingest failed.",
                    code=code,
                    operation="upload_pdf",
                    detail=str(exc),
                ),
            }
            yield {"event": "done", "data": "failed"}

    return EventSourceResponse(_events(), headers={"Cache-Control": "no-cache"})


@router.get("/agent/admin/faqs")
async def get_faqs(
    request: Request,
    limit: int = Query(default=200, ge=1, le=500),
    skip: int = Query(default=0, ge=0),
):
    try:
        pool = _get_pool(request)
        items = await knowledge_base_service.list_faqs(pool, limit=limit, skip=skip)
        return {"items": items, "count": len(items), "limit": limit, "skip": skip}
    except Exception as e:  # noqa: BLE001
        _raise_kb_http_error("list_faqs", str(e))


@router.get("/agent/admin/faq-categories")
async def get_faq_categories(request: Request):
    try:
        pool = _get_pool(request)
        items = await knowledge_base_service.list_categories(pool)
        return {"items": items, "count": len(items)}
    except Exception as e:  # noqa: BLE001
        _raise_kb_http_error("list_faq_categories", str(e))


@router.put("/agent/admin/faqs")
async def edit_faq(request: Request, payload: EditFaqRequest):
    try:
        if not payload.id and not payload.original_question:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "missing_identifier",
                    "operation": "edit_faq",
                    "message": "Provide either `id` or `original_question`.",
                },
            )
        pool = _get_pool(request)
        updated = await knowledge_base_service.update_faq(
            pool,
            faq_id=payload.id,
            original_question=payload.original_question,
            new_question=payload.new_question,
            new_answer=payload.new_answer,
            new_category=payload.new_category,
            new_tags=payload.new_tags,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="FAQ not found")
        return {"status": "success", "message": "FAQ updated"}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        _raise_kb_http_error("edit_faq", str(e))


@router.delete("/agent/admin/faqs")
async def delete_faq_endpoint(
    request: Request,
    question: Optional[str] = Query(default=None, min_length=1),
    id: Optional[str] = Query(default=None, min_length=1),
):
    try:
        if not id and not question:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "missing_identifier",
                    "operation": "delete_faq",
                    "message": "Provide either `id` or `question`.",
                },
            )
        pool = _get_pool(request)
        deleted = await knowledge_base_service.delete_faq(pool, faq_id=id, question=question)
        if deleted <= 0:
            raise HTTPException(status_code=404, detail="FAQ not found")
        return {"status": "success", "message": "FAQ deleted"}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        _raise_kb_http_error("delete_faq", str(e))


@router.delete("/agent/admin/faqs/all")
async def clear_all_faqs_endpoint(request: Request):
    try:
        pool = _get_pool(request)
        deleted = await knowledge_base_service.clear_all(pool)
        return {"status": "success", "message": f"Cleared {deleted} FAQ entries"}
    except Exception as e:  # noqa: BLE001
        _raise_kb_http_error("clear_all_faqs", str(e))


@router.post("/agent/admin/faqs/semantic-delete")
async def semantic_delete_endpoint(request: Request, payload: SemanticDeleteRequest):
    try:
        pool = _get_pool(request)
        deleted = await knowledge_base_service.semantic_delete(
            pool,
            query=payload.query,
            threshold=payload.threshold,
        )
        return {"status": "success", "message": f"Deleted {deleted} FAQ entries"}
    except Exception as e:  # noqa: BLE001
        _raise_kb_http_error("semantic_delete", str(e))
