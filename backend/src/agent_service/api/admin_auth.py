"""Admin authentication dependencies — JWT session cookie enforcement.

Three FastAPI dependencies, chained via ``Depends``:

- ``require_admin``         require valid JWT session cookie with 'admin' role
- ``require_super_admin``   chains on admin; additionally require 'super_admin' role
- ``require_mfa_fresh``     chains on super_admin; require fresh (<5 min) TOTP verification

The legacy ``require_admin_key`` / X-Admin-Key fallback was retired in Phase 6h
(see tasks/todo.md plan 2026-04-10). JWT cookie is now the only admin auth path.
"""

from __future__ import annotations

import logging

from fastapi import Depends, HTTPException, Request

from src.agent_service.core.config import ADMIN_AUTH_COOKIE_NAME_ACCESS
from src.agent_service.security.admin_jwt import (
    AccessClaims,
    ExpiredAccessToken,
    InvalidAccessToken,
    mfa_fresh,
    verify_access_token,
)

log = logging.getLogger(__name__)


async def require_admin(request: Request) -> AccessClaims:
    """Require a valid JWT session cookie with the 'admin' role.

    Raises HTTPException 401 on missing/invalid/expired token; 403 on role mismatch.
    """
    access = request.cookies.get(ADMIN_AUTH_COOKIE_NAME_ACCESS)
    if not access:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "no_session",
                "operation": "require_admin",
                "message": "no admin session cookie",
            },
        )
    try:
        claims = verify_access_token(access)
    except ExpiredAccessToken as e:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "token_expired",
                "operation": "require_admin",
                "message": "admin session expired",
            },
        ) from e
    except InvalidAccessToken as e:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "invalid_token",
                "operation": "require_admin",
                "message": "invalid admin session",
            },
        ) from e
    if "admin" not in claims.roles:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "not_admin",
                "operation": "require_admin",
                "message": "admin role required",
            },
        )
    return claims


async def require_super_admin(
    request: Request,
    claims: AccessClaims = Depends(require_admin),
) -> AccessClaims:
    """Chain dependency: require 'super_admin' role on top of admin."""
    if "super_admin" not in claims.roles:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "not_super_admin",
                "operation": "require_super_admin",
                "message": "super_admin role required",
            },
        )
    return claims


async def require_mfa_fresh(
    request: Request,
    claims: AccessClaims = Depends(require_super_admin),
) -> AccessClaims:
    """Chain dependency: require fresh (<5 min) TOTP verification on top of super_admin."""
    if not mfa_fresh(claims):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "mfa_required",
                "operation": "require_mfa_fresh",
                "message": "fresh MFA verification required for this operation",
            },
        )
    return claims
