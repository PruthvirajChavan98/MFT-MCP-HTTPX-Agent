"""Model catalog and listing endpoints."""

import logging

from fastapi import APIRouter, HTTPException

from src.agent_service.llm.catalog import model_service

log = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["models"])


@router.get("/models")
async def list_models():
    """List all available models from catalog."""
    try:
        data = await model_service.get_cached_data()
        total_models = sum(len(cat["models"]) for cat in data)
        return {"count": total_models, "categories": data}
    except Exception as e:
        log.error(f"Model fetch error: {e}")
        raise HTTPException(status_code=502, detail=str(e)) from e
