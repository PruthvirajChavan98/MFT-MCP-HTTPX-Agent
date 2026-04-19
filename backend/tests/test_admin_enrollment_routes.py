from __future__ import annotations

import time
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pyotp
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from fakeredis.aioredis import FakeRedis
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.agent_service.api.admin_enrollment import routes as admin_enrollment_routes
from src.agent_service.api.admin_enrollment.repo import (
    EnrollmentTokenRow,
    IssuedToken,
    admin_enrollment_repo,
)
from src.agent_service.api.admin_users import routes as admin_users_routes
from src.agent_service.api.admin_users.repo import AdminUserRow, admin_users_repo
from src.agent_service.api.endpoints import admin_auth_routes
from src.agent_service.core import session_utils
from src.agent_service.security import admin_crypto, admin_jwt, password_hash

_TEST_JWT_SECRET = "z" * 32
_SUPER_ID = UUID("33333333-3333-3333-3333-333333333333")
_SUPER_EMAIL = "super@example.com"
_SUPER_PASSWORD = "super-admin-strong-password-33+"


class _FakeEnrollmentRepo:
    """In-memory mirror of AdminEnrollmentRepo for route tests.

    The atomic consume semantics (exactly-once, FOR UPDATE) are collapsed into
    a boolean flag — sufficient because pytest-asyncio doesn't truly run two
    coroutines concurrently against the same dict.
    """

    def __init__(self) -> None:
        # Keyed by token_hash so find_by_plaintext can hash first then look up.
        self.tokens: dict[str, EnrollmentTokenRow] = {}
        self.admin_users_created: list[UUID] = []

    def _hash(self, plaintext: str) -> str:
        import hashlib

        return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()

    async def create_token(
        self,
        pool: Any,
        *,
        email: str,
        role: str,
        created_by: UUID,
        ttl_hours: int,
    ) -> IssuedToken:
        import secrets as pysecrets

        plaintext = pysecrets.token_urlsafe(32)
        h = self._hash(plaintext)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        self.tokens[h] = EnrollmentTokenRow(
            token_hash=h,
            email=email.strip().lower(),
            role=role,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            consumed_at=None,
            consumed_ip=None,
        )
        return IssuedToken(
            plaintext=plaintext,
            token_hash=h,
            email=email.strip().lower(),
            role=role,
            expires_at=expires_at,
        )

    async def find_by_plaintext(self, pool: Any, plaintext: str) -> EnrollmentTokenRow | None:
        return self.tokens.get(self._hash(plaintext))

    async def consume_token_atomic(
        self,
        pool: Any,
        *,
        plaintext: str,
        password_hash: str,
        totp_secret_enc: str,
        consumed_ip: str | None,
    ) -> tuple[str, UUID | None]:
        h = self._hash(plaintext)
        row = self.tokens.get(h)
        if row is None:
            return ("not_found", None)
        if row.consumed_at is not None:
            return ("consumed", None)
        if row.expires_at <= datetime.now(timezone.utc):
            return ("expired", None)

        # Create the admin_users row via the faked repo so downstream find_by_id
        # works for the redeem handler's cookie-issuing step.
        new_admin = await admin_users_repo.create(
            pool,
            email=row.email,
            password_hash=password_hash,
            totp_secret_enc=totp_secret_enc,
            is_super_admin=(row.role == "super_admin"),
            created_by_admin_id=None,
        )
        self.admin_users_created.append(new_admin.id)

        self.tokens[h] = EnrollmentTokenRow(
            token_hash=row.token_hash,
            email=row.email,
            role=row.role,
            created_by=row.created_by,
            created_at=row.created_at,
            expires_at=row.expires_at,
            consumed_at=datetime.now(timezone.utc),
            consumed_ip=consumed_ip,
        )
        return ("ok", new_admin.id)

    def force_consume(self, plaintext: str) -> None:
        """Test helper: mark a token as already-consumed to test 409."""
        h = self._hash(plaintext)
        row = self.tokens[h]
        self.tokens[h] = EnrollmentTokenRow(
            token_hash=row.token_hash,
            email=row.email,
            role=row.role,
            created_by=row.created_by,
            created_at=row.created_at,
            expires_at=row.expires_at,
            consumed_at=datetime.now(timezone.utc),
            consumed_ip=row.consumed_ip,
        )

    def force_expire(self, plaintext: str) -> None:
        """Test helper: move expires_at into the past."""
        h = self._hash(plaintext)
        row = self.tokens[h]
        self.tokens[h] = EnrollmentTokenRow(
            token_hash=row.token_hash,
            email=row.email,
            role=row.role,
            created_by=row.created_by,
            created_at=row.created_at,
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            consumed_at=row.consumed_at,
            consumed_ip=row.consumed_ip,
        )


class _FakeAdminUsersRepo:
    """Minimal admin_users_repo mock — just enough for the enrollment flow."""

    def __init__(self) -> None:
        self.rows: dict[UUID, AdminUserRow] = {}

    def install(self, row: AdminUserRow) -> None:
        self.rows[row.id] = row

    async def find_by_email_active(self, pool: Any, email: str) -> AdminUserRow | None:
        e = email.strip().lower()
        for r in self.rows.values():
            if r.email == e and r.revoked_at is None:
                return r
        return None

    async def find_by_id(self, pool: Any, user_id: UUID) -> AdminUserRow | None:
        return self.rows.get(user_id)

    async def create(
        self,
        pool: Any,
        *,
        email: str,
        password_hash: str,
        totp_secret_enc: str,
        is_super_admin: bool = False,
        created_by_admin_id: UUID | None = None,
    ) -> AdminUserRow:
        now = datetime.now(timezone.utc)
        row = AdminUserRow(
            id=uuid4(),
            email=email.strip().lower(),
            password_hash=password_hash,
            totp_secret_enc=totp_secret_enc,
            is_super_admin=is_super_admin,
            created_at=now,
            updated_at=now,
            revoked_at=None,
            created_by_admin_id=created_by_admin_id,
        )
        self.rows[row.id] = row
        return row


@pytest_asyncio.fixture
async def env(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[AsyncClient, _FakeEnrollmentRepo, _FakeAdminUsersRepo, str]]:
    fernet_key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr(admin_crypto, "FERNET_MASTER_KEY", fernet_key)
    admin_crypto._reset_for_testing()
    monkeypatch.setattr(admin_jwt, "JWT_SECRET", _TEST_JWT_SECRET)
    monkeypatch.setattr(admin_auth_routes, "ADMIN_AUTH_COOKIE_SECURE", False)

    super_totp_secret = pyotp.random_base32()
    users = _FakeAdminUsersRepo()
    users.install(
        AdminUserRow(
            id=_SUPER_ID,
            email=_SUPER_EMAIL,
            password_hash=password_hash.hash_password(_SUPER_PASSWORD),
            totp_secret_enc=admin_crypto.encrypt_secret(super_totp_secret),
            is_super_admin=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            revoked_at=None,
            created_by_admin_id=None,
        )
    )

    for method_name in ("find_by_email_active", "find_by_id", "create"):
        monkeypatch.setattr(admin_users_repo, method_name, getattr(users, method_name))

    enrollment = _FakeEnrollmentRepo()
    for method_name in ("create_token", "find_by_plaintext", "consume_token_atomic"):
        monkeypatch.setattr(admin_enrollment_repo, method_name, getattr(enrollment, method_name))

    fake_redis = FakeRedis(decode_responses=True)

    async def _fake_get_redis() -> FakeRedis:
        return fake_redis

    monkeypatch.setattr(session_utils, "get_redis", _fake_get_redis)
    monkeypatch.setattr(admin_auth_routes, "get_redis", _fake_get_redis)
    monkeypatch.setattr(admin_enrollment_routes, "get_redis", _fake_get_redis)

    # Disable rate limiting globally for tests.
    class _L:
        async def aacquire(self, *a: object, **kw: object) -> bool:
            return True

    class _M:
        async def get_admin_auth_login_limiter(self) -> _L:
            return _L()

        async def get_admin_auth_mfa_limiter(self) -> _L:
            return _L()

        async def get_admin_users_mutate_limiter(self) -> _L:
            return _L()

        async def get_admin_enrollment_issue_limiter(self) -> _L:
            return _L()

        async def get_admin_enrollment_public_limiter(self) -> _L:
            return _L()

    async def _noop_enforce(*a: object, **kw: object) -> None:
        return None

    for module in (admin_auth_routes, admin_users_routes, admin_enrollment_routes):
        monkeypatch.setattr(module, "get_rate_limiter_manager", lambda: _M())
        monkeypatch.setattr(module, "enforce_rate_limit", _noop_enforce)

    app = FastAPI()
    app.include_router(admin_auth_routes.router, tags=["admin-auth"])
    app.include_router(admin_enrollment_routes.router, tags=["admin-enrollment"])
    app.state.pool = object()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post(
            "/admin/auth/login",
            json={"email": _SUPER_EMAIL, "password": _SUPER_PASSWORD},
        )
        assert login.status_code == 200
        csrf = client.cookies.get("mft_admin_csrf") or ""
        code = pyotp.TOTP(super_totp_secret).now()
        mfa = await client.post(
            "/admin/auth/mfa/verify",
            json={"code": code},
            headers={"X-CSRF-Token": csrf},
        )
        assert mfa.status_code == 200

        try:
            yield client, enrollment, users, csrf
        finally:
            await fake_redis.flushall()
            await fake_redis.aclose()


# ─────────── POST /tokens (issue) ───────────


@pytest.mark.asyncio
async def test_issue_token_happy_path(
    env: tuple[AsyncClient, _FakeEnrollmentRepo, _FakeAdminUsersRepo, str],
) -> None:
    client, enrollment, _, csrf = env
    response = await client.post(
        "/agent/admin/enrollment/tokens",
        json={"email": "New@Example.com", "role": "admin", "ttl_hours": 6},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "new@example.com"
    assert body["role"] == "admin"
    assert body["token"]
    assert "/admin/enroll?token=" in body["redeem_url"]
    # Token was stored server-side.
    assert len(enrollment.tokens) == 1


@pytest.mark.asyncio
async def test_issue_token_rejects_non_super_admin(
    env: tuple[AsyncClient, _FakeEnrollmentRepo, _FakeAdminUsersRepo, str],
) -> None:
    client, _, _, csrf = env
    # Mint a plain-admin fresh-MFA token.
    access, _ = admin_jwt.issue_access_token(
        sub=str(uuid4()),
        roles=["admin"],
        mfa_verified_at=int(time.time()),
    )
    client.cookies.set("mft_admin_at", access)
    response = await client.post(
        "/agent/admin/enrollment/tokens",
        json={"email": "x@example.com", "role": "admin"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 403
    # require_mfa_fresh chains through require_super_admin, which returns
    # "not_super_admin" before the handler runs.
    assert response.json()["detail"]["code"] == "not_super_admin"


@pytest.mark.asyncio
async def test_issue_token_rejects_stale_mfa(
    env: tuple[AsyncClient, _FakeEnrollmentRepo, _FakeAdminUsersRepo, str],
) -> None:
    client, _, _, csrf = env
    access, _ = admin_jwt.issue_access_token(
        sub=str(_SUPER_ID),
        roles=["admin", "super_admin"],
        mfa_verified_at=int(time.time()) - 3600,
    )
    client.cookies.set("mft_admin_at", access)
    response = await client.post(
        "/agent/admin/enrollment/tokens",
        json={"email": "x@example.com", "role": "admin"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "mfa_required"


@pytest.mark.asyncio
async def test_issue_token_rejects_invalid_email(
    env: tuple[AsyncClient, _FakeEnrollmentRepo, _FakeAdminUsersRepo, str],
) -> None:
    client, _, _, csrf = env
    response = await client.post(
        "/agent/admin/enrollment/tokens",
        json={"email": "not-an-email", "role": "admin"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_email"


# ─────────── GET /tokens/{plaintext} (lookup) ───────────


@pytest.mark.asyncio
async def test_lookup_returns_metadata_for_pending_token(
    env: tuple[AsyncClient, _FakeEnrollmentRepo, _FakeAdminUsersRepo, str],
) -> None:
    client, _, _, csrf = env
    issue = await client.post(
        "/agent/admin/enrollment/tokens",
        json={"email": "newuser@example.com", "role": "admin"},
        headers={"X-CSRF-Token": csrf},
    )
    plaintext = issue.json()["token"]

    lookup = await client.get(f"/agent/admin/enrollment/tokens/{plaintext}")
    assert lookup.status_code == 200
    body = lookup.json()
    assert body["email"] == "newuser@example.com"
    assert body["role"] == "admin"
    assert body["status"] == "pending"


@pytest.mark.asyncio
async def test_lookup_returns_404_for_unknown_token(
    env: tuple[AsyncClient, _FakeEnrollmentRepo, _FakeAdminUsersRepo, str],
) -> None:
    client, _, _, _ = env
    response = await client.get("/agent/admin/enrollment/tokens/nonexistent-token")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "not_found"


# ─────────── POST /tokens/{plaintext}/redeem ───────────


@pytest.mark.asyncio
async def test_redeem_happy_path_creates_admin_and_sets_cookies(
    env: tuple[AsyncClient, _FakeEnrollmentRepo, _FakeAdminUsersRepo, str],
) -> None:
    client, enrollment, users, csrf = env

    issue = await client.post(
        "/agent/admin/enrollment/tokens",
        json={"email": "redeemer@example.com", "role": "admin"},
        headers={"X-CSRF-Token": csrf},
    )
    plaintext = issue.json()["token"]

    # Drop the super-admin's session cookies — redeem is PUBLIC.
    client.cookies.clear()

    client_secret = pyotp.random_base32()
    code = pyotp.TOTP(client_secret).now()

    response = await client.post(
        f"/agent/admin/enrollment/tokens/{plaintext}/redeem",
        json={
            "password": "new-admin-strong-pw-12345",
            "totp_secret_base32": client_secret,
            "totp_code": code,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    # New admin row was created.
    assert len(users.rows) == 2  # super-admin + new
    # Token is now consumed.
    token_row = next(iter(enrollment.tokens.values()))
    assert token_row.consumed_at is not None
    # Cookies were set so the new user lands authenticated.
    assert "mft_admin_at" in response.cookies
    assert "mft_admin_csrf" in response.cookies


@pytest.mark.asyncio
async def test_redeem_rejects_invalid_totp_code(
    env: tuple[AsyncClient, _FakeEnrollmentRepo, _FakeAdminUsersRepo, str],
) -> None:
    client, _, _, csrf = env
    issue = await client.post(
        "/agent/admin/enrollment/tokens",
        json={"email": "bad-totp@example.com", "role": "admin"},
        headers={"X-CSRF-Token": csrf},
    )
    plaintext = issue.json()["token"]
    client.cookies.clear()

    response = await client.post(
        f"/agent/admin/enrollment/tokens/{plaintext}/redeem",
        json={
            "password": "long-enough-password-12",
            "totp_secret_base32": pyotp.random_base32(),
            "totp_code": "000000",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_totp"


@pytest.mark.asyncio
async def test_redeem_rejects_expired_token(
    env: tuple[AsyncClient, _FakeEnrollmentRepo, _FakeAdminUsersRepo, str],
) -> None:
    client, enrollment, _, csrf = env
    issue = await client.post(
        "/agent/admin/enrollment/tokens",
        json={"email": "expired@example.com", "role": "admin"},
        headers={"X-CSRF-Token": csrf},
    )
    plaintext = issue.json()["token"]
    enrollment.force_expire(plaintext)
    client.cookies.clear()

    client_secret = pyotp.random_base32()
    code = pyotp.TOTP(client_secret).now()

    response = await client.post(
        f"/agent/admin/enrollment/tokens/{plaintext}/redeem",
        json={
            "password": "long-enough-password-12",
            "totp_secret_base32": client_secret,
            "totp_code": code,
        },
    )
    assert response.status_code == 410
    assert response.json()["detail"]["code"] == "expired"


@pytest.mark.asyncio
async def test_redeem_rejects_already_consumed_token(
    env: tuple[AsyncClient, _FakeEnrollmentRepo, _FakeAdminUsersRepo, str],
) -> None:
    client, enrollment, _, csrf = env
    issue = await client.post(
        "/agent/admin/enrollment/tokens",
        json={"email": "twice@example.com", "role": "admin"},
        headers={"X-CSRF-Token": csrf},
    )
    plaintext = issue.json()["token"]
    enrollment.force_consume(plaintext)
    client.cookies.clear()

    client_secret = pyotp.random_base32()
    code = pyotp.TOTP(client_secret).now()

    response = await client.post(
        f"/agent/admin/enrollment/tokens/{plaintext}/redeem",
        json={
            "password": "long-enough-password-12",
            "totp_secret_base32": client_secret,
            "totp_code": code,
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "consumed"
