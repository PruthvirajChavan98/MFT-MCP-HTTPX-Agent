"""Health check and system status endpoints."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """System health check endpoint."""
    return {"status": "healthy", "service": "agent", "version": "2.0.0"}
