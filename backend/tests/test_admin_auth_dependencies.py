"""Tests for the admin auth dependencies — JWT session cookie only.

The legacy ADMIN_AUTH_ENABLED feature flag and X-Admin-Key fallback tests were
deleted in Phase 6h alongside the legacy code they covered.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import jwt
import pytest
from fastapi import HTTPException

from src.agent_service.api.admin_auth import (
    require_admin,
    require_mfa_fresh,
    require_super_admin,
)
from src.agent_service.security import admin_jwt
from src.agent_service.security.admin_jwt import AccessClaims

_TEST_JWT_SECRET = "x" * 32


def _make_request(
    *,
    cookies: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> MagicMock:
    """Build a minimal mock Request object with the fields our dependencies read."""
    request = MagicMock()
    request.cookies = cookies or {}
    request.headers = headers or {}
    return request


def _issue_test_jwt(
    sub: str,
    roles: list[str],
    *,
    mfa_verified_at: int | None = None,
    exp_offset: int = 900,
) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": sub,
            "iss": "mft-agent-service",
            "aud": "mft-admin-console",
            "iat": now,
            "exp": now + exp_offset,
            "jti": f"test-jti-{now}",
            "roles": roles,
            "mfa_verified_at": mfa_verified_at,
        },
        _TEST_JWT_SECRET,
        algorithm="HS256",
    )


@pytest.fixture(autouse=True)
def _set_test_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_jwt, "JWT_SECRET", _TEST_JWT_SECRET)


# ─────────────── require_admin ───────────────


@pytest.mark.asyncio
async def test_require_admin_accepts_valid_cookie() -> None:
    token = _issue_test_jwt("super_admin", ["admin", "super_admin"])
    request = _make_request(cookies={"mft_admin_at": token})
    claims = await require_admin(request)
    assert isinstance(claims, AccessClaims)
    assert claims.sub == "super_admin"
    assert "admin" in claims.roles


@pytest.mark.asyncio
async def test_require_admin_rejects_missing_cookie() -> None:
    request = _make_request()
    with pytest.raises(HTTPException) as exc:
        await require_admin(request)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_require_admin_rejects_expired_cookie() -> None:
    token = _issue_test_jwt("super_admin", ["admin"], exp_offset=-1000)
    request = _make_request(cookies={"mft_admin_at": token})
    with pytest.raises(HTTPException) as exc:
        await require_admin(request)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_require_admin_rejects_tampered_cookie() -> None:
    token = _issue_test_jwt("super_admin", ["admin"])
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    request = _make_request(cookies={"mft_admin_at": tampered})
    with pytest.raises(HTTPException) as exc:
        await require_admin(request)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_require_admin_rejects_missing_admin_role() -> None:
    token = _issue_test_jwt("viewer", ["viewer"])
    request = _make_request(cookies={"mft_admin_at": token})
    with pytest.raises(HTTPException) as exc:
        await require_admin(request)
    assert exc.value.status_code == 403


# ─────────────── require_super_admin ───────────────


@pytest.mark.asyncio
async def test_require_super_admin_rejects_admin_only_role() -> None:
    admin_claims = AccessClaims(
        sub="anon",
        iss="mft-agent-service",
        aud="mft-admin-console",
        iat=0,
        exp=0,
        jti="",
        roles=("admin",),
        mfa_verified_at=None,
    )
    request = _make_request()
    with pytest.raises(HTTPException) as exc:
        await require_super_admin(request, claims=admin_claims)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_super_admin_accepts_super_admin_role() -> None:
    super_admin_claims = AccessClaims(
        sub="super_admin",
        iss="mft-agent-service",
        aud="mft-admin-console",
        iat=0,
        exp=0,
        jti="",
        roles=("admin", "super_admin"),
        mfa_verified_at=None,
    )
    request = _make_request()
    returned = await require_super_admin(request, claims=super_admin_claims)
    assert returned is super_admin_claims


# ─────────────── require_mfa_fresh ───────────────


@pytest.mark.asyncio
async def test_require_mfa_fresh_rejects_stale_mfa() -> None:
    now = int(time.time())
    stale_claims = AccessClaims(
        sub="super_admin",
        iss="mft-agent-service",
        aud="mft-admin-console",
        iat=0,
        exp=0,
        jti="",
        roles=("admin", "super_admin"),
        mfa_verified_at=now - 1000,  # 1000 sec > 300 sec freshness window
    )
    request = _make_request()
    with pytest.raises(HTTPException) as exc:
        await require_mfa_fresh(request, claims=stale_claims)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_mfa_fresh_accepts_fresh_mfa() -> None:
    now = int(time.time())
    fresh_claims = AccessClaims(
        sub="super_admin",
        iss="mft-agent-service",
        aud="mft-admin-console",
        iat=0,
        exp=0,
        jti="",
        roles=("admin", "super_admin"),
        mfa_verified_at=now - 60,
    )
    request = _make_request()
    returned = await require_mfa_fresh(request, claims=fresh_claims)
    assert returned is fresh_claims


@pytest.mark.asyncio
async def test_require_mfa_fresh_rejects_null_mfa() -> None:
    claims = AccessClaims(
        sub="super_admin",
        iss="mft-agent-service",
        aud="mft-admin-console",
        iat=0,
        exp=0,
        jti="",
        roles=("admin", "super_admin"),
        mfa_verified_at=None,
    )
    request = _make_request()
    with pytest.raises(HTTPException) as exc:
        await require_mfa_fresh(request, claims=claims)
    assert exc.value.status_code == 403
