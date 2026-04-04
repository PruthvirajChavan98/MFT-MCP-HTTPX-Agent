"""Admin analytics package -- re-exports a combined router from domain modules."""

from __future__ import annotations

from fastapi import APIRouter

from .conversations import router as conversations_router
from .guardrails import router as guardrails_router
from .overview import router as overview_router
from .traces import router as traces_router

router = APIRouter()
router.include_router(overview_router)
router.include_router(conversations_router)
router.include_router(traces_router)
router.include_router(guardrails_router)

__all__ = ["router"]
