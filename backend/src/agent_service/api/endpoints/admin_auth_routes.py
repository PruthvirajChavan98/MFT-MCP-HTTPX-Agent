"""FastAPI router for admin authentication: login, MFA step-up, refresh, logout, me.

All endpoints live under `/admin/auth/*`. Dormant until ADMIN_AUTH_ENABLED=True
flips in Phase 6 — Phase 3b just mounts the router alongside the legacy
X-Admin-Key path.

Cookies:
- mft_admin_at   (httpOnly, Secure, SameSite=Strict, path="/",            15 min)
- mft_admin_rt   (httpOnly, Secure, SameSite=Strict, path="/admin/auth",   8 h)
- mft_admin_csrf (NOT httpOnly — JS must read it,    SameSite=Strict, path="/", 8 h)

CSRF: random double-submit cookie. Every state-changing endpoint except /login
(which issues the token) requires X-CSRF-Token header == mft_admin_csrf cookie.

Rate limiting: deferred to Phase 4. Security is preserved via TOTP lockout
(Phase 3a admin_totp.verify_totp_code) and refresh token replay detection
(Phase 2 admin_jwt.rotate_refresh_token).
"""

from __future__ import annotations

import hmac
import logging
import secrets
import time
from typing import Any
from uuid import UUID

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from src.agent_service.api.admin_users.repo import AdminUserRow, admin_users_repo
from src.agent_service.core.config import (
    ADMIN_AUTH_COOKIE_NAME_ACCESS,
    ADMIN_AUTH_COOKIE_NAME_REFRESH,
    ADMIN_AUTH_COOKIE_SECURE,
    JWT_ACCESS_TTL_SECONDS,
    JWT_REFRESH_TTL_SECONDS,
)
from src.agent_service.core.rate_limiter_manager import (
    enforce_rate_limit,
    get_rate_limiter_manager,
)
from src.agent_service.core.session_utils import get_redis
from src.agent_service.security.admin_jwt import (
    ExpiredAccessToken,
    InvalidAccessToken,
    InvalidRefreshToken,
    RefreshTokenReplayDetected,
    issue_access_token,
    issue_refresh_token,
    mfa_fresh,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_access_token,
)
from src.agent_service.security.admin_totp import (
    TOTPInvalidCode,
    TOTPLockedOut,
    verify_totp_code,
)
from src.agent_service.security.password_hash import hash_password, verify_password

# Dummy password hash used for constant-time "email not found" branches in
# /login. Computing an Argon2 verify against this preserves the timing shape
# of a real verify_password call, preventing user-enumeration timing attacks.
# Generated once at import time because Argon2 hashing is intentionally slow.
_DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing-equivalence")

log = logging.getLogger(__name__)

_CSRF_COOKIE_NAME = "mft_admin_csrf"


def _client_ip_from_request(request: Request) -> str:
    """Extract client IP using the project's canonical pattern.

    Prefers ``request.state.client_ip`` (populated by the Tor block middleware
    from X-Forwarded-For / X-Real-IP), falling back to ``request.client.host``.
    Returns "unknown" when neither is available so rate limiting still operates
    with a single stable identifier for the malformed-request case.
    """
    client_ip = getattr(request.state, "client_ip", None)
    if not client_ip and request.client is not None:
        client_ip = request.client.host
    return client_ip or "unknown"


router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


# ─────────── request models ───────────


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=1, max_length=256)
    password: str = Field(..., min_length=1, max_length=4096)


class MfaVerifyRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=16)


# ─────────── cookie helpers ───────────


def _set_auth_cookies(response: Response, access: str, refresh: str, csrf: str) -> None:
    response.set_cookie(
        ADMIN_AUTH_COOKIE_NAME_ACCESS,
        access,
        httponly=True,
        secure=ADMIN_AUTH_COOKIE_SECURE,
        samesite="strict",
        max_age=JWT_ACCESS_TTL_SECONDS,
        path="/",
    )
    response.set_cookie(
        ADMIN_AUTH_COOKIE_NAME_REFRESH,
        refresh,
        httponly=True,
        secure=ADMIN_AUTH_COOKIE_SECURE,
        samesite="strict",
        max_age=JWT_REFRESH_TTL_SECONDS,
        path="/admin/auth",
    )
    response.set_cookie(
        _CSRF_COOKIE_NAME,
        csrf,
        httponly=False,
        secure=ADMIN_AUTH_COOKIE_SECURE,
        samesite="strict",
        max_age=JWT_REFRESH_TTL_SECONDS,
        path="/",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ADMIN_AUTH_COOKIE_NAME_ACCESS, path="/")
    response.delete_cookie(ADMIN_AUTH_COOKIE_NAME_REFRESH, path="/admin/auth")
    response.delete_cookie(_CSRF_COOKIE_NAME, path="/")


# ─────────── DB pool + user lookup helpers ───────────


def _get_pool(request: Request) -> Any:
    """Return the Postgres pool attached by app_factory, or 503 if missing."""
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


def _parse_sub_as_uuid(sub: str, *, operation: str) -> UUID:
    """JWT sub is the admin's UUID (stringified). Anything else is an invalid
    session (e.g., a pre-migration token with sub=\"super_admin\")."""
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


def _roles_for(user: AdminUserRow) -> list[str]:
    return ["admin", "super_admin"] if user.is_super_admin else ["admin"]


# ─────────── CSRF dependency ───────────


async def require_csrf_token(request: Request) -> None:
    """Enforce CSRF double-submit on state-changing endpoints (not /login, not GET /me)."""
    cookie = request.cookies.get(_CSRF_COOKIE_NAME)
    header = request.headers.get("X-CSRF-Token")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "csrf_mismatch",
                "operation": "admin_auth",
                "message": "CSRF token missing or mismatched",
            },
        )


# ─────────── /login ───────────


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response) -> dict[str, object]:
    # Per-IP rate limit: ~5 req/min fail-closed. Fires before credential check
    # to prevent body-processing cost from being a brute-force vector.
    manager = get_rate_limiter_manager()
    limiter = await manager.get_admin_auth_login_limiter()
    await enforce_rate_limit(
        request, limiter, f"admin_auth_login:{_client_ip_from_request(request)}"
    )

    pool = _get_pool(request)
    user = await admin_users_repo.find_by_email_active(pool, body.email)

    # Constant-time password verification regardless of whether the user
    # exists — prevents user-enumeration via response timing.
    hash_to_check = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    password_valid = verify_password(body.password, hash_to_check)

    if user is None or not password_valid:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "invalid_credentials",
                "operation": "login",
                "message": "invalid email or password",
            },
        )

    redis = await get_redis()
    sub = str(user.id)

    access_token, _ = issue_access_token(
        sub=sub,
        roles=_roles_for(user),
        mfa_verified_at=None,
    )
    refresh_token, _ = await issue_refresh_token(redis, sub=sub)
    csrf_token = secrets.token_urlsafe(32)

    _set_auth_cookies(response, access_token, refresh_token, csrf_token)

    return {"ok": True, "mfa_required": True}


# ─────────── /mfa/verify ───────────


@router.post("/mfa/verify", dependencies=[Depends(require_csrf_token)])
async def mfa_verify(
    body: MfaVerifyRequest, request: Request, response: Response
) -> dict[str, object]:
    # Per-IP rate limit: belt-and-braces on top of admin_totp's built-in lockout.
    # 5 req/min per-IP fail-closed.
    manager = get_rate_limiter_manager()
    limiter = await manager.get_admin_auth_mfa_limiter()
    await enforce_rate_limit(request, limiter, f"admin_auth_mfa:{_client_ip_from_request(request)}")

    access = request.cookies.get(ADMIN_AUTH_COOKIE_NAME_ACCESS)
    if not access:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "no_session",
                "operation": "mfa_verify",
                "message": "no access token",
            },
        )
    try:
        claims = verify_access_token(access)
    except ExpiredAccessToken as e:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "token_expired",
                "operation": "mfa_verify",
                "message": "access token expired",
            },
        ) from e
    except InvalidAccessToken as e:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "invalid_token",
                "operation": "mfa_verify",
                "message": "invalid access token",
            },
        ) from e

    pool = _get_pool(request)
    user_id = _parse_sub_as_uuid(claims.sub, operation="mfa_verify")
    user = await admin_users_repo.find_by_id(pool, user_id)
    if user is None or user.revoked_at is not None:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "invalid_token",
                "operation": "mfa_verify",
                "message": "account not found or revoked",
            },
        )

    redis = await get_redis()
    try:
        await verify_totp_code(
            redis,
            sub=str(user.id),
            encrypted_secret=user.totp_secret_enc,
            code=body.code,
        )
    except TOTPLockedOut as e:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "locked_out",
                "operation": "mfa_verify",
                "message": "account locked due to failed MFA attempts",
            },
        ) from e
    except TOTPInvalidCode as e:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "invalid_code",
                "operation": "mfa_verify",
                "message": "invalid TOTP code",
            },
        ) from e
    except InvalidToken as e:
        log.error(
            "mfa_verify: TOTP secret decryption failed — master key rotated without re-encryption"
        )
        raise HTTPException(
            status_code=503,
            detail={
                "code": "admin_auth_misconfigured",
                "operation": "mfa_verify",
                "message": "TOTP secret cannot be decrypted",
            },
        ) from e

    now_ts = int(time.time())
    new_access, _ = issue_access_token(
        sub=str(user.id),
        roles=_roles_for(user),
        mfa_verified_at=now_ts,
    )
    response.set_cookie(
        ADMIN_AUTH_COOKIE_NAME_ACCESS,
        new_access,
        httponly=True,
        secure=ADMIN_AUTH_COOKIE_SECURE,
        samesite="strict",
        max_age=JWT_ACCESS_TTL_SECONDS,
        path="/",
    )

    return {"ok": True}


# ─────────── /refresh ───────────


@router.post("/refresh", dependencies=[Depends(require_csrf_token)])
async def refresh(request: Request, response: Response) -> dict[str, object]:
    refresh_token_str = request.cookies.get(ADMIN_AUTH_COOKIE_NAME_REFRESH)
    if not refresh_token_str:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "no_refresh",
                "operation": "refresh",
                "message": "no refresh token",
            },
        )

    redis = await get_redis()
    try:
        new_refresh, new_handle = await rotate_refresh_token(redis, refresh_token_str)
    except RefreshTokenReplayDetected as e:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "refresh_replay",
                "operation": "refresh",
                "message": "refresh token replay detected; please log in again",
            },
        ) from e
    except InvalidRefreshToken as e:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "invalid_refresh",
                "operation": "refresh",
                "message": "invalid refresh token",
            },
        ) from e

    # Re-fetch user on every refresh so revoked accounts can no longer mint
    # fresh access tokens — the old access token still works until its 15 min
    # TTL expires, which is an acceptable window for a soft-delete model.
    pool = _get_pool(request)
    user_id = _parse_sub_as_uuid(new_handle.sub, operation="refresh")
    user = await admin_users_repo.find_by_id(pool, user_id)
    if user is None or user.revoked_at is not None:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "invalid_refresh",
                "operation": "refresh",
                "message": "account not found or revoked",
            },
        )

    # Per D7: refresh always resets mfa_verified_at to None — forces re-MFA
    # before the next mutation even if the previous access token was MFA-fresh.
    new_access, _ = issue_access_token(
        sub=str(user.id),
        roles=_roles_for(user),
        mfa_verified_at=None,
    )
    csrf_token = secrets.token_urlsafe(32)
    _set_auth_cookies(response, new_access, new_refresh, csrf_token)

    return {"ok": True}


# ─────────── /logout ───────────


@router.post("/logout", dependencies=[Depends(require_csrf_token)])
async def logout(request: Request, response: Response) -> dict[str, object]:
    refresh_token_str = request.cookies.get(ADMIN_AUTH_COOKIE_NAME_REFRESH)
    if refresh_token_str:
        redis = await get_redis()
        await revoke_refresh_token(redis, refresh_token_str)
    _clear_auth_cookies(response)
    return {"ok": True}


# ─────────── /me ───────────


@router.get("/me")
async def me(request: Request) -> dict[str, object]:
    access = request.cookies.get(ADMIN_AUTH_COOKIE_NAME_ACCESS)
    if not access:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "no_session",
                "operation": "me",
                "message": "no access token",
            },
        )
    try:
        claims = verify_access_token(access)
    except ExpiredAccessToken as e:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "token_expired",
                "operation": "me",
                "message": "access token expired",
            },
        ) from e
    except InvalidAccessToken as e:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "invalid_token",
                "operation": "me",
                "message": "invalid access token",
            },
        ) from e

    # Resolve email from DB when possible — tolerate pre-migration tokens
    # (sub="super_admin") and pool absence by returning email=None rather
    # than tearing down an otherwise valid session.
    email: str | None = None
    try:
        user_id = UUID(claims.sub)
    except (ValueError, TypeError):
        user_id = None
    if user_id is not None:
        pool = getattr(request.app.state, "pool", None)
        if pool is not None:
            user = await admin_users_repo.find_by_id(pool, user_id)
            if user is not None:
                email = user.email

    return {
        "sub": claims.sub,
        "email": email,
        "roles": list(claims.roles),
        "mfa_fresh": mfa_fresh(claims),
        "exp": claims.exp,
    }
