"""FastAPI router for the admin enrollment-token flow.

Endpoints under ``/agent/admin/enrollment/*``:

- ``POST /tokens``              — super-admin + MFA fresh + CSRF. Issues a
                                  plaintext token returned ONCE.
- ``GET  /tokens/{plaintext}``  — **public** metadata lookup (email, role,
                                  status). Per-IP rate-limited.
- ``POST /tokens/{plaintext}/redeem`` — **public** atomic redemption. Body
                                  carries ``password``, ``totp_secret_base32``
                                  (client-generated), and ``totp_code`` (proof
                                  of scan). On success, admin_users row is
                                  created and JWT cookies are set — the user
                                  lands authenticated.

Security model: the plaintext token is the capability; it appears in the
redeem URL handed to the new admin out-of-band. The DB stores only its
SHA-256 hash. Atomic redemption (SELECT ... FOR UPDATE) guarantees single-use.
"""

from __future__ import annotations

import hashlib
import logging
import re
import secrets as pysecrets
import time
from typing import Literal
from uuid import UUID

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from src.agent_service.api.admin_auth import require_mfa_fresh
from src.agent_service.api.admin_enrollment.repo import admin_enrollment_repo
from src.agent_service.api.admin_users.repo import admin_users_repo
from src.agent_service.api.admin_utils import get_admin_pool, parse_sub_as_uuid
from src.agent_service.api.endpoints.admin_auth_routes import (
    _client_ip_from_request,
    _set_auth_cookies,
    require_csrf_token,
)
from src.agent_service.core.config import (
    ADMIN_ENROLLMENT_TOKEN_TTL_HOURS_DEFAULT,
    ADMIN_ENROLLMENT_TOKEN_TTL_HOURS_MAX,
    ADMIN_PUBLIC_BASE_URL,
)
from src.agent_service.core.rate_limiter_manager import (
    enforce_rate_limit,
    get_rate_limiter_manager,
)
from src.agent_service.core.session_utils import get_redis
from src.agent_service.security.admin_crypto import encrypt_secret
from src.agent_service.security.admin_jwt import (
    AccessClaims,
    issue_access_token,
    issue_refresh_token,
)
from src.agent_service.security.password_hash import hash_password

log = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MIN_PASSWORD_LENGTH = 12
_TOTP_ISSUER = "mft-agent-admin"
_TOTP_SECRET_RE = re.compile(r"^[A-Z2-7]{16,128}$")  # base32 alphabet, length-bounded

router = APIRouter(prefix="/agent/admin/enrollment", tags=["admin-enrollment"])


# ─────────── request / response models ───────────


class IssueTokenRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=256)
    role: Literal["admin", "super_admin"] = "admin"
    ttl_hours: int | None = None


class IssueTokenResponse(BaseModel):
    """Returned ONCE by POST /tokens — plaintext is not retrievable again."""

    token: str
    redeem_url: str
    email: str
    role: str
    expires_at: str


class TokenMetadataResponse(BaseModel):
    """Public metadata — never exposes the token hash or internal fields."""

    email: str
    role: str
    expires_at: str
    status: Literal["pending", "consumed", "expired"]


class RedeemRequest(BaseModel):
    password: str = Field(..., min_length=_MIN_PASSWORD_LENGTH, max_length=4096)
    totp_secret_base32: str = Field(..., min_length=16, max_length=128)
    totp_code: str = Field(..., min_length=6, max_length=8)


class RedeemResponse(BaseModel):
    ok: bool
    admin_id: str


# ─────────── helpers ───────────


def _validate_email(email: str) -> str:
    normalized = email.strip().lower()
    if not _EMAIL_RE.match(normalized):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_email",
                "operation": "admin_enrollment",
                "message": "email must be a valid address",
            },
        )
    return normalized


def _clamp_ttl_hours(requested: int | None) -> int:
    if requested is None:
        return ADMIN_ENROLLMENT_TOKEN_TTL_HOURS_DEFAULT
    if requested < 1:
        return 1
    if requested > ADMIN_ENROLLMENT_TOKEN_TTL_HOURS_MAX:
        return ADMIN_ENROLLMENT_TOKEN_TTL_HOURS_MAX
    return requested


def _build_redeem_url(plaintext: str) -> str:
    base = (ADMIN_PUBLIC_BASE_URL or "").rstrip("/")
    # If no public base URL is configured, return a relative path; the issuer
    # can append their own origin in the UI.
    path = f"/admin/enroll?token={plaintext}"
    return f"{base}{path}" if base else path


async def _enforce_issue_rate_limit(request: Request, caller_id: UUID) -> None:
    manager = get_rate_limiter_manager()
    limiter = await manager.get_admin_enrollment_issue_limiter()
    await enforce_rate_limit(request, limiter, f"admin_enrollment_issue:{caller_id}")


async def _enforce_public_rate_limit(request: Request, endpoint: str) -> None:
    """Per-IP rate limit on public metadata + redeem endpoints.

    Tight limits are essential: these are unauthenticated and the only thing
    preventing an attacker from enumerating valid tokens or brute-forcing
    redemption is this rate limit plus SHA-256 preimage resistance.
    """
    manager = get_rate_limiter_manager()
    limiter = await manager.get_admin_enrollment_public_limiter()
    ip = _client_ip_from_request(request)
    await enforce_rate_limit(request, limiter, f"admin_enrollment_{endpoint}:{ip}")


def _status_for(row) -> Literal["pending", "consumed", "expired"]:
    from datetime import datetime, timezone

    if row.consumed_at is not None:
        return "consumed"
    if row.expires_at <= datetime.now(timezone.utc):
        return "expired"
    return "pending"


# ─────────── POST /tokens ───────────


@router.post(
    "/tokens",
    dependencies=[Depends(require_csrf_token)],
)
async def issue_token(
    body: IssueTokenRequest,
    request: Request,
    claims: AccessClaims = Depends(require_mfa_fresh),
) -> IssueTokenResponse:
    # require_mfa_fresh already chains through require_super_admin → require_admin,
    # so a plain-admin is rejected with 403 not_super_admin before we run.
    creator_id = parse_sub_as_uuid(claims.sub, operation="issue_enrollment_token")
    await _enforce_issue_rate_limit(request, creator_id)

    email = _validate_email(body.email)
    ttl_hours = _clamp_ttl_hours(body.ttl_hours)
    pool = get_admin_pool(request)

    issued = await admin_enrollment_repo.create_token(
        pool,
        email=email,
        role=body.role,
        created_by=creator_id,
        ttl_hours=ttl_hours,
    )

    log.info(
        "admin_enrollment.issue: email=%s role=%s ttl_hours=%s by=%s",
        email,
        body.role,
        ttl_hours,
        creator_id,
    )

    return IssueTokenResponse(
        token=issued.plaintext,
        redeem_url=_build_redeem_url(issued.plaintext),
        email=issued.email,
        role=issued.role,
        expires_at=issued.expires_at.isoformat(),
    )


# ─────────── GET /tokens/{plaintext} ───────────


@router.get("/tokens/{plaintext}")
async def get_token_metadata(
    plaintext: str,
    request: Request,
) -> TokenMetadataResponse:
    await _enforce_public_rate_limit(request, "lookup")

    pool = get_admin_pool(request)
    row = await admin_enrollment_repo.find_by_plaintext(pool, plaintext)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "not_found",
                "operation": "admin_enrollment_lookup",
                "message": "token not found",
            },
        )

    return TokenMetadataResponse(
        email=row.email,
        role=row.role,
        expires_at=row.expires_at.isoformat(),
        status=_status_for(row),
    )


# ─────────── POST /tokens/{plaintext}/redeem ───────────


def _verify_totp_code_matches_secret(secret_base32: str, code: str) -> bool:
    """Verify a TOTP code against a client-supplied base32 secret.

    The client generates its own TOTP secret in-browser and stores it in the
    user's authenticator app. Submitting a valid code alongside the secret
    proves the user actually scanned the QR before redeeming (not just
    attempted to bypass MFA by submitting a fresh secret they never scanned).

    One-step window tolerance matches the admin_totp login behavior.
    """
    if not _TOTP_SECRET_RE.match(secret_base32):
        return False
    try:
        totp = pyotp.TOTP(secret_base32)
    except Exception:
        return False
    return bool(totp.verify(code, valid_window=1))


@router.post("/tokens/{plaintext}/redeem")
async def redeem_token(
    plaintext: str,
    body: RedeemRequest,
    request: Request,
    response: Response,
) -> RedeemResponse:
    await _enforce_public_rate_limit(request, "redeem")

    if not _verify_totp_code_matches_secret(body.totp_secret_base32, body.totp_code):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_totp",
                "operation": "admin_enrollment_redeem",
                "message": "TOTP code does not match the submitted secret",
            },
        )

    # Replay guard — even though consume_token_atomic serialises on the
    # token row, the *same* (secret, code) pair can be submitted against
    # the *same* token in a race window before the row lock acquires.
    # Reject the second observation of any (secret, code) pair within the
    # 90-second code validity window. (security review H2)
    redis = await get_redis()
    code_fp = hashlib.sha256(
        f"{body.totp_secret_base32}:{body.totp_code}".encode("utf-8")
    ).hexdigest()
    redis_nonce_key = f"agent:enroll_code_seen:{code_fp}"
    first_seen = await redis.set(redis_nonce_key, "1", ex=90, nx=True)
    if not first_seen:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "totp_code_replayed",
                "operation": "admin_enrollment_redeem",
                "message": (
                    "This TOTP code has already been submitted. Wait for the "
                    "authenticator to generate a new code and try again."
                ),
            },
        )

    pool = get_admin_pool(request)
    password_hashed = hash_password(body.password)
    totp_secret_enc = encrypt_secret(body.totp_secret_base32)
    client_ip = _client_ip_from_request(request)

    outcome, new_admin_id = await admin_enrollment_repo.consume_token_atomic(
        pool,
        plaintext=plaintext,
        password_hash=password_hashed,
        totp_secret_enc=totp_secret_enc,
        consumed_ip=client_ip if client_ip != "unknown" else None,
    )

    if outcome == "not_found":
        raise HTTPException(
            status_code=404,
            detail={
                "code": "not_found",
                "operation": "admin_enrollment_redeem",
                "message": "token not found",
            },
        )
    if outcome == "expired":
        raise HTTPException(
            status_code=410,
            detail={
                "code": "expired",
                "operation": "admin_enrollment_redeem",
                "message": "enrollment token has expired",
            },
        )
    if outcome == "consumed":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "consumed",
                "operation": "admin_enrollment_redeem",
                "message": "enrollment token has already been used",
            },
        )

    assert new_admin_id is not None  # outcome == "ok" guarantees this
    admin = await admin_users_repo.find_by_id(pool, new_admin_id)
    if admin is None:
        # Should be impossible — we just inserted the row in the same txn.
        raise HTTPException(
            status_code=500,
            detail={
                "code": "post_redeem_inconsistency",
                "operation": "admin_enrollment_redeem",
                "message": "admin row missing after successful redeem",
            },
        )

    # Issue a full login session so the user lands authenticated at /admin.
    # Match the login endpoint's cookie shape (access + refresh + CSRF).
    # The TOTP code was just verified for this exact redeem, so mark MFA
    # fresh — otherwise any super-admin mutation in the same 5-minute
    # window would prompt for MFA again after the user literally just
    # proved possession. (security review M3)
    sub = str(admin.id)
    roles = ["admin", "super_admin"] if admin.is_super_admin else ["admin"]
    access_token, _ = issue_access_token(sub=sub, roles=roles, mfa_verified_at=int(time.time()))
    refresh_token, _ = await issue_refresh_token(redis, sub=sub)
    csrf_token = pysecrets.token_urlsafe(32)
    _set_auth_cookies(response, access_token, refresh_token, csrf_token)

    log.info(
        "admin_enrollment.redeem: admin=%s email=%s ip=%s",
        admin.id,
        admin.email,
        client_ip,
    )

    return RedeemResponse(ok=True, admin_id=str(admin.id))
