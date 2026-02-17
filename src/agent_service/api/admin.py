import json
import logging
import os
import shutil
import tempfile
from typing import Optional

from fastapi import APIRouter, HTTPException, Header, File, UploadFile, Query, Request
from sse_starlette.sse import EventSourceResponse

# Enterprise Modules
from src.agent_service.core.schemas import (
    FAQEditRequest, FAQSemanticSearchRequest, FAQSemanticDeleteRequest
)
from src.agent_service.tools.knowledge import kb_service
from src.agent_service.features.follow_up import follow_up_service
from src.agent_service.faqs.pdf_parser import PDFQAParser

# Setup Logger
log = logging.getLogger("admin_api")

# Initialize Router
# We will mount this with prefix="" or "/agent" in main_agent.py
# For now, we keep full paths to ensure exact match with previous logic.
router = APIRouter()

@router.get("/agent/all-follow-ups")
async def get_stored_followups():
    try:
        results = await follow_up_service.get_all_cached_questions()
        return {"count": len(results), "data": results}
    except Exception as e:
        log.error(f"Admin Fetch Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Knowledge Base Management ---

@router.post("/agent/admin/faqs/batch-json")
async def update_faqs_json_stream(
    request: Request,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    x_groq_key: Optional[str] = Header(None, alias="X-Groq-Key"),
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
):
    try:
        body = await request.json()
        items = body.get("items", [])
        if not items:
            async def empty_gen(): yield {"event": "error", "data": "No items provided"}
            return EventSourceResponse(empty_gen())
        
        return EventSourceResponse(
            kb_service.ingest_faq_batch_gen(items, groq_key=x_groq_key or "", openrouter_key=x_openrouter_key or ""),
            headers={"Cache-Control": "no-cache"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agent/admin/faqs/upload-pdf")
async def update_faqs_pdf_stream(
    file: UploadFile = File(...),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
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
            yield {"event": "progress", "data": json.dumps({"percent": 2, "message": "Parsing PDF Structure..."})}
            
            parser = PDFQAParser(tmp_path)
            parsed_data = parser.parse()
            
            if not parsed_data:
                yield {"event": "error", "data": "No Q&A pairs found in PDF."}
                return
            
            yield {"event": "progress", "data": json.dumps({"percent": 5, "message": f"Found {len(parsed_data)} pairs. Starting ingestion..."})}
            
            async for event in kb_service.ingest_faq_batch_gen(parsed_data, groq_key=x_groq_key or "", openrouter_key=x_openrouter_key or ""):
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
        return {"status": "success", "count": len(data), "limit": limit, "skip": skip, "items": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/agent/admin/faqs")
async def edit_faq(
    request: FAQEditRequest,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
):
    result = await kb_service.edit_faq(
        original_question=request.original_question,
        new_question=request.new_question or "",
        new_answer=request.new_answer or "",
        openrouter_key=x_openrouter_key or "",
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result

@router.delete("/agent/admin/faqs")
async def delete_faq_endpoint(
    question: str = Query(..., description="The exact question text to delete"), 
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")
):
    result = await kb_service.delete_faq(question)
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))
    return result

@router.delete("/agent/admin/faqs/all")
async def clear_all_faqs_endpoint(x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")):
    result = await kb_service.clear_all_faqs()
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))
    return result

@router.post("/agent/admin/faqs/semantic-search")
async def semantic_search_endpoint(
    request: FAQSemanticSearchRequest, 
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key")
):
    try:
        results = await kb_service.semantic_search(request.query, request.limit, x_openrouter_key or "")
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agent/admin/faqs/semantic-delete")
async def semantic_delete_endpoint(
    request: FAQSemanticDeleteRequest, 
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"), 
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key")
):
    result = await kb_service.delete_faq_by_vector(request.query, request.threshold, x_openrouter_key or "")
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message"))
    return result
