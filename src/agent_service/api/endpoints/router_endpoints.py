"""NBFC router classification endpoints."""
import logging
from fastapi import APIRouter, HTTPException

from src.agent_service.core.schemas import RouterClassifyRequest
from src.agent_service.features.nbfc_router import nbfc_router_service

log = logging.getLogger(__name__)
router = APIRouter(prefix="/agent/router", tags=["router"])


@router.post("/classify")
async def router_classify(req: RouterClassifyRequest):
    """Classify query using NBFC router."""
    try:
        result = await nbfc_router_service.classify(
            req.text,
            openrouter_api_key=req.openrouter_api_key,
            mode=req.mode,
        )
        return result
    except Exception as e:
        log.error(f"Router classify error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def router_compare(req: RouterClassifyRequest):
    """Compare router classifications."""
    try:
        result = await nbfc_router_service.compare(
            req.text,
            openrouter_api_key=req.openrouter_api_key
        )
        return result
    except Exception as e:
        log.error(f"Router compare error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
