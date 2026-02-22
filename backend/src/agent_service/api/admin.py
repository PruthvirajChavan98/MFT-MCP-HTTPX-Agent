import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from src.agent_service.api.admin_auth import require_admin_key
from src.agent_service.features.follow_up import follow_up_service

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


# --- Cognee-backed Knowledge APIs ---


@router.post("/agent/admin/faqs/semantic-search")
async def semantic_search_endpoint(
    query: str = Query(..., min_length=1),
):
    try:
        import cognee

        try:
            results = await cognee.search(
                query_text=query,
                query_type=cognee.SearchType.GRAPH_COMPLETION,
            )
        except TypeError:
            results = await cognee.search(
                query=query,
                search_type=cognee.SearchType.GRAPH_COMPLETION,
            )
        return {"status": "success", "results": results}
    except Exception as e:
        _raise_kb_http_error("semantic_search", str(e))


def _deprecated_kb_route(route: str) -> None:
    raise HTTPException(
        status_code=410,
        detail={
            "code": "kb_route_deprecated",
            "route": route,
            "message": "Legacy FAQ ingestion/edit/delete routes were removed during Cognee migration.",
        },
    )


@router.post("/agent/admin/faqs/batch-json")
async def update_faqs_json_stream():
    _deprecated_kb_route("batch-json")


@router.post("/agent/admin/faqs/upload-pdf")
async def update_faqs_pdf_stream():
    _deprecated_kb_route("upload-pdf")


@router.get("/agent/admin/faqs")
async def get_faqs():
    _deprecated_kb_route("list-faqs")


@router.put("/agent/admin/faqs")
async def edit_faq():
    _deprecated_kb_route("edit-faq")


@router.delete("/agent/admin/faqs")
async def delete_faq_endpoint():
    _deprecated_kb_route("delete-faq")


@router.delete("/agent/admin/faqs/all")
async def clear_all_faqs_endpoint():
    _deprecated_kb_route("clear-all-faqs")


@router.post("/agent/admin/faqs/semantic-delete")
async def semantic_delete_endpoint():
    _deprecated_kb_route("semantic-delete")
