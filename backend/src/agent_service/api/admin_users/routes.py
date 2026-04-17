"""FastAPI router for admin user management.

All endpoints live under ``/agent/admin/admins/*``.

Authorization:
- GET    /admins       → super_admin (no MFA freshness requirement)
- POST   /admins       → super_admin + MFA fresh
- DELETE /admins/{id}  → super_admin + MFA fresh

CSRF: mutating endpoints reuse the admin_auth CSRF double-submit dependency.

Enrollment UX: POST returns the newly-created admin's TOTP secret in raw
base32 AND as an otpauth URI. This is the ONLY opportunity to read those
values — they are never returned again and never logged. The caller (the
super-admin UI) is responsible for handing them to the new admin out-of-band.
"""

from __future__ import annotations

import logging
import re
from uuid import UUID

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.agent_service.api.admin_auth import require_mfa_fresh, require_super_admin
from src.agent_service.api.admin_users.repo import admin_users_repo
from src.agent_service.api.admin_utils import get_admin_pool, parse_sub_as_uuid
from src.agent_service.api.endpoints.admin_auth_routes import require_csrf_token
from src.agent_service.core.rate_limiter_manager import (
    enforce_rate_limit,
    get_rate_limiter_manager,
)
from src.agent_service.security.admin_crypto import encrypt_secret
from src.agent_service.security.admin_jwt import AccessClaims
from src.agent_service.security.password_hash import hash_password

log = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MIN_PASSWORD_LENGTH = 12
_TOTP_ISSUER = "mft-agent-admin"

router = APIRouter(prefix="/agent/admin/admins", tags=["admin-users"])


async def _enforce_mutate_rate_limit(request: Request, caller_id: UUID) -> None:
    """Throttle POST/DELETE /admins per-caller so a compromised super-admin
    session cannot pin the worker pool by spamming the Argon2 hash on create."""
    manager = get_rate_limiter_manager()
    limiter = await manager.get_admin_users_mutate_limiter()
    await enforce_rate_limit(request, limiter, f"admin_users_mutate:{caller_id}")


# ─────────── request / response models ───────────


class CreateAdminRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=256)
    password: str = Field(..., min_length=_MIN_PASSWORD_LENGTH, max_length=4096)


class AdminUserResponse(BaseModel):
    id: str
    email: str
    is_super_admin: bool
    created_at: str
    created_by_admin_id: str | None


class CreateAdminResponse(AdminUserResponse):
    """Returned only once, on POST. totp_secret_base32 + otpauth_uri are
    never exposed again."""

    totp_secret_base32: str
    otpauth_uri: str


class ListAdminsResponse(BaseModel):
    items: list[AdminUserResponse]


# ─────────── helpers ───────────


def _validate_email(email: str) -> str:
    normalized = email.strip().lower()
    if not _EMAIL_RE.match(normalized):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_email",
                "operation": "create_admin",
                "message": "email must be a valid address",
            },
        )
    return normalized


def _to_response(row: object) -> AdminUserResponse:
    # Works for both AdminUserRow and AdminUserPublic — they share the
    # attributes listed here.
    return AdminUserResponse(
        id=str(row.id),  # type: ignore[attr-defined]
        email=row.email,  # type: ignore[attr-defined]
        is_super_admin=row.is_super_admin,  # type: ignore[attr-defined]
        created_at=row.created_at.isoformat(),  # type: ignore[attr-defined]
        created_by_admin_id=(
            str(row.created_by_admin_id)  # type: ignore[attr-defined]
            if row.created_by_admin_id is not None  # type: ignore[attr-defined]
            else None
        ),
    )


# ─────────── GET / ───────────


@router.get("")
async def list_admins(
    request: Request,
    claims: AccessClaims = Depends(require_super_admin),
) -> ListAdminsResponse:
    pool = get_admin_pool(request)
    rows = await admin_users_repo.list_active(pool)
    return ListAdminsResponse(items=[_to_response(r) for r in rows])


# ─────────── POST / ───────────


@router.post(
    "",
    dependencies=[Depends(require_csrf_token)],
)
async def create_admin(
    body: CreateAdminRequest,
    request: Request,
    claims: AccessClaims = Depends(require_mfa_fresh),
) -> CreateAdminResponse:
    creator_id = parse_sub_as_uuid(claims.sub, operation="create_admin")
    await _enforce_mutate_rate_limit(request, creator_id)

    email = _validate_email(body.email)
    pool = get_admin_pool(request)

    # Reject if an active row already exists — the partial unique index would
    # also raise, but this keeps the response shape consistent.
    if await admin_users_repo.find_by_email_active(pool, email) is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "email_in_use",
                "operation": "create_admin",
                "message": "an active admin with this email already exists",
            },
        )

    totp_secret_base32 = pyotp.random_base32()
    totp_secret_enc = encrypt_secret(totp_secret_base32)
    password_hashed = hash_password(body.password)

    created = await admin_users_repo.create(
        pool,
        email=email,
        password_hash=password_hashed,
        totp_secret_enc=totp_secret_enc,
        is_super_admin=False,
        created_by_admin_id=creator_id,
    )

    otpauth_uri = pyotp.totp.TOTP(totp_secret_base32).provisioning_uri(
        name=email,
        issuer_name=_TOTP_ISSUER,
    )

    log.info(
        "admin_users.create: admin=%s created by=%s",
        created.id,
        creator_id,
    )

    return CreateAdminResponse(
        id=str(created.id),
        email=created.email,
        is_super_admin=created.is_super_admin,
        created_at=created.created_at.isoformat(),
        created_by_admin_id=(
            str(created.created_by_admin_id) if created.created_by_admin_id else None
        ),
        totp_secret_base32=totp_secret_base32,
        otpauth_uri=otpauth_uri,
    )


# ─────────── DELETE /{id} ───────────


def _reject_self_revoke(caller_id: UUID, admin_id: UUID) -> None:
    """Prevent an admin from locking themselves out by revoking their own
    account. Raises 400 cannot_revoke_self."""
    if admin_id == caller_id:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "cannot_revoke_self",
                "operation": "revoke_admin",
                "message": "you cannot revoke your own account",
            },
        )


@router.delete(
    "/{admin_id}",
    dependencies=[Depends(require_csrf_token)],
)
async def revoke_admin(
    admin_id: UUID,
    request: Request,
    claims: AccessClaims = Depends(require_mfa_fresh),
) -> dict[str, object]:
    caller_id = parse_sub_as_uuid(claims.sub, operation="revoke_admin")
    _reject_self_revoke(caller_id, admin_id)

    await _enforce_mutate_rate_limit(request, caller_id)

    pool = get_admin_pool(request)
    # Atomic: the repo wraps lookup + last-super count + UPDATE in one
    # transaction with SELECT ... FOR UPDATE on the target row. Two
    # concurrent revokes of different super-admins serialize on the count
    # query inside the transaction, so the "last super" invariant holds.
    outcome = await admin_users_repo.revoke_if_not_last_super(pool, admin_id)

    if outcome == "not_found":
        raise HTTPException(
            status_code=404,
            detail={
                "code": "not_found",
                "operation": "revoke_admin",
                "message": "admin not found",
            },
        )
    if outcome == "last_super":
        raise HTTPException(
            status_code=400,
            detail={
                "code": "last_super_admin",
                "operation": "revoke_admin",
                "message": "cannot revoke the last active super_admin",
            },
        )

    log.info("admin_users.revoke: admin=%s revoked by=%s", admin_id, caller_id)
    return {"ok": True}
