"""NBFC router classification endpoints."""

import logging

from fastapi import APIRouter, HTTPException

from src.agent_service.core.schemas import RouterClassifyRequest
from src.agent_service.core.session_utils import valid_session_id
from src.agent_service.features.routing.nbfc_router import nbfc_router_service
from src.agent_service.tools.mcp_manager import mcp_manager

log = logging.getLogger(__name__)
router = APIRouter(prefix="/agent/router", tags=["router"])


async def _resolve_tools_for_request(req: RouterClassifyRequest):
    if not req.session_id:
        return None
    sid = valid_session_id(req.session_id)
    return await mcp_manager.rebuild_tools_for_user(sid, openrouter_api_key=req.openrouter_api_key)


@router.post("/classify")
async def router_classify(req: RouterClassifyRequest):
    """Classify query using NBFC router."""
    try:
        tools = await _resolve_tools_for_request(req)
        result = await nbfc_router_service.classify(
            req.text,
            openrouter_api_key=req.openrouter_api_key,
            mode=req.mode,
            tools=tools,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error("Router classify error: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/compare")
async def router_compare(req: RouterClassifyRequest):
    """Compare router classifications."""
    try:
        tools = await _resolve_tools_for_request(req)
        result = await nbfc_router_service.compare(
            req.text,
            openrouter_api_key=req.openrouter_api_key,
            tools=tools,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.error("Router compare error: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
