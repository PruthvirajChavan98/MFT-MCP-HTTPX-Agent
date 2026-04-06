from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException

from src.agent_service.core.config import ADMIN_API_KEY


def require_admin_key(x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")) -> None:
    """
    Validate X-Admin-Key header against the configured ADMIN_API_KEY.

    Fail-closed: if ADMIN_API_KEY is not set, all admin endpoints are unavailable
    (returns 503) rather than silently allowing unauthenticated access.
    """
    if not ADMIN_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Admin API key not configured. Set ADMIN_API_KEY environment variable.",
        )

    if not x_admin_key or x_admin_key.strip() != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Admin-Key")
