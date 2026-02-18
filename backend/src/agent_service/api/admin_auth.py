from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException

from src.agent_service.core.config import ADMIN_API_KEY


def require_admin_key(x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")) -> None:
    """
    Validate X-Admin-Key when ADMIN_API_KEY is configured.

    If ADMIN_API_KEY is not set, the service remains backward-compatible and does not
    enforce header validation.
    """
    if not ADMIN_API_KEY:
        return

    if not x_admin_key or x_admin_key.strip() != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Admin-Key")
