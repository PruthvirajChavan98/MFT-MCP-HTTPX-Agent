import json
import logging
import os
import shutil
import tempfile
from typing import Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Request, UploadFile
from sse_starlette.sse import EventSourceResponse

from src.agent_service.api.admin_auth import require_admin_key

# Enterprise Modules
from src.agent_service.core.schemas import (
    FAQEditRequest,
    FAQSemanticDeleteRequest,
    FAQSemanticSearchRequest,
)
from src.agent_service.faqs.pdf_parser import PDFQAParser
from src.agent_service.features.follow_up import follow_up_service
from src.agent_service.tools.knowledge import kb_service

# Setup Logger
log = logging.getLogger("admin_api")

# Initialize Router
router = APIRouter(dependencies=[Depends(require_admin_key)])


def _classify_kb_error(message: str) -> tuple[int, str]:
    msg = (message or "").lower()
    if "openrouter key required" in msg or msg.strip() == "key required":
        return 400, "missing_openrouter_key"
    if "neo4j" in msg and (
        "connection refused" in msg
        or "couldn't connect" in msg
        or "serviceunavailable" in msg
        or "failed after" in msg
    ):
        return 503, "neo4j_unavailable"
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


@router.get("/agent/all-follow-ups")
async def get_stored_followups():
    try:
        results = await follow_up_service.get_all_cached_questions()
        return {"count": len(results), "data": results}
    except Exception as e:
        log.error(f"Admin Fetch Error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# --- Knowledge Base Management ---


@router.post("/agent/admin/faqs/batch-json")
async def update_faqs_json_stream(
    request: Request,
    x_groq_key: Optional[str] = Header(None, alias="X-Groq-Key"),
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
):
    try:
        body = await request.json()
        items = body.get("items", [])
        if not items:

            async def empty_gen():
                yield {"event": "error", "data": "No items provided"}

            return EventSourceResponse(empty_gen())

        return EventSourceResponse(
            kb_service.ingest_faq_batch_gen(
                items, groq_key=x_groq_key or "", openrouter_key=x_openrouter_key or ""
            ),
            headers={"Cache-Control": "no-cache"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/agent/admin/faqs/upload-pdf")
async def update_faqs_pdf_stream(
    file: UploadFile = File(...),
    x_groq_key: Optional[str] = Header(None, alias="X-Groq-Key"),
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        shutil.copyfileobj(file.file, tmp_file)
        tmp_path = tmp_file.name

    async def pdf_ingestion_generator():
        try:
            yield {
                "event": "progress",
                "data": json.dumps({"percent": 2, "message": "Parsing PDF Structure..."}),
            }

            parser = PDFQAParser(tmp_path)
            parsed_data = parser.parse()

            if not parsed_data:
                yield {"event": "error", "data": "No Q&A pairs found in PDF."}
                return

            yield {
                "event": "progress",
                "data": json.dumps(
                    {
                        "percent": 5,
                        "message": f"Found {len(parsed_data)} pairs. Starting ingestion...",
                    }
                ),
            }

            async for event in kb_service.ingest_faq_batch_gen(
                parsed_data, groq_key=x_groq_key or "", openrouter_key=x_openrouter_key or ""
            ):
                yield event
        except Exception as e:
            yield {"event": "error", "data": str(e)}
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    return EventSourceResponse(pdf_ingestion_generator(), headers={"Cache-Control": "no-cache"})


@router.get("/agent/admin/faqs")
async def get_faqs(limit: int = Query(100, ge=1, le=1000), skip: int = Query(0, ge=0)):
    try:
        data = await kb_service.get_all_faqs(limit=limit, skip=skip)
        return {
            "status": "success",
            "count": len(data),
            "limit": limit,
            "skip": skip,
            "items": data,
        }
    except Exception as e:
        _raise_kb_http_error("get_faqs", str(e))


@router.put("/agent/admin/faqs")
async def edit_faq(
    request: FAQEditRequest,
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
):
    result = await kb_service.edit_faq(
        original_question=request.original_question,
        new_question=request.new_question or "",
        new_answer=request.new_answer or "",
        openrouter_key=x_openrouter_key or "",
    )
    if result.get("status") == "error":
        _raise_kb_http_error("edit_faq", result.get("message", "Unknown FAQ edit error"))
    return result


@router.delete("/agent/admin/faqs")
async def delete_faq_endpoint(
    question: str = Query(..., description="The exact question text to delete"),
):
    result = await kb_service.delete_faq(question)
    if result.get("status") == "error":
        _raise_kb_http_error("delete_faq", result.get("message", "Unknown FAQ delete error"))
    return result


@router.delete("/agent/admin/faqs/all")
async def clear_all_faqs_endpoint():
    result = await kb_service.clear_all_faqs()
    if result.get("status") == "error":
        _raise_kb_http_error("clear_all_faqs", result.get("message", "Unknown FAQ clear error"))
    return result


@router.post("/agent/admin/faqs/semantic-search")
async def semantic_search_endpoint(
    request: FAQSemanticSearchRequest,
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
):
    try:
        results = await kb_service.semantic_search(
            request.query, request.limit, x_openrouter_key or ""
        )
        return {"status": "success", "results": results}
    except Exception as e:
        _raise_kb_http_error("semantic_search", str(e))


@router.post("/agent/admin/faqs/semantic-delete")
async def semantic_delete_endpoint(
    request: FAQSemanticDeleteRequest,
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
):
    result = await kb_service.delete_faq_by_vector(
        request.query, request.threshold, x_openrouter_key or ""
    )
    if result.get("status") == "error":
        _raise_kb_http_error(
            "semantic_delete",
            result.get("message", "Unknown FAQ semantic delete error"),
        )
    return result
