"""Shared helpers for admin routers.

Extracted from ``endpoints/admin_auth_routes.py`` so that sibling routers
(``admin_users/routes.py`` and any future admin module) can use them
without importing underscore-prefixed private symbols across packages.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request


def get_admin_pool(request: Request) -> Any:
    """Return the Postgres pool attached by app_factory, or raise 503 if
    the pool is unavailable (e.g., app booted without POSTGRES_DSN set)."""
    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "admin_auth_not_configured",
                "operation": "admin_auth",
                "message": "admin auth database unavailable",
            },
        )
    return pool


def parse_sub_as_uuid(sub: str, *, operation: str) -> UUID:
    """Parse a JWT sub claim as a UUID. Raise 401 for anything else (e.g.,
    a pre-migration token with sub=\"super_admin\")."""
    try:
        return UUID(sub)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "invalid_token",
                "operation": operation,
                "message": "session predates DB migration; please log in again",
            },
        ) from exc
