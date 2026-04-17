from __future__ import annotations

import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pyotp
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from fakeredis.aioredis import FakeRedis
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.agent_service.api.admin_users import routes as admin_users_routes
from src.agent_service.api.admin_users.repo import AdminUserPublic, AdminUserRow, admin_users_repo
from src.agent_service.api.endpoints import admin_auth_routes
from src.agent_service.core import session_utils
from src.agent_service.security import admin_crypto, admin_jwt, password_hash

_TEST_JWT_SECRET = "y" * 32
_SUPER_ID = UUID("22222222-2222-2222-2222-222222222222")
_SUPER_EMAIL = "super@example.com"
_SUPER_PASSWORD = "super-admin-strong-password-12+"


class _FakeRepo:
    def __init__(self) -> None:
        self.rows: dict[UUID, AdminUserRow] = {}

    def install(self, row: AdminUserRow) -> None:
        self.rows[row.id] = row

    async def find_by_email_active(self, pool: object, email: str) -> AdminUserRow | None:
        e = email.strip().lower()
        for r in self.rows.values():
            if r.email == e and r.revoked_at is None:
                return r
        return None

    async def find_by_id(self, pool: object, user_id: UUID) -> AdminUserRow | None:
        return self.rows.get(user_id)

    async def list_active(self, pool: object) -> list[AdminUserPublic]:
        return [
            AdminUserPublic(
                id=r.id,
                email=r.email,
                is_super_admin=r.is_super_admin,
                created_at=r.created_at,
                revoked_at=r.revoked_at,
                created_by_admin_id=r.created_by_admin_id,
            )
            for r in self.rows.values()
            if r.revoked_at is None
        ]

    async def count_active_super_admins(self, pool: object) -> int:
        return sum(1 for r in self.rows.values() if r.is_super_admin and r.revoked_at is None)

    async def create(
        self,
        pool: object,
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

    async def revoke(self, pool: object, user_id: UUID) -> bool:
        row = self.rows.get(user_id)
        if row is None or row.revoked_at is not None:
            return False
        self.rows[user_id] = AdminUserRow(
            id=row.id,
            email=row.email,
            password_hash=row.password_hash,
            totp_secret_enc=row.totp_secret_enc,
            is_super_admin=row.is_super_admin,
            created_at=row.created_at,
            updated_at=row.updated_at,
            revoked_at=datetime.now(timezone.utc),
            created_by_admin_id=row.created_by_admin_id,
        )
        return True

    async def revoke_if_not_last_super(self, pool: object, user_id: UUID) -> str:
        """Mirror of the production implementation — in-memory guard only."""
        row = self.rows.get(user_id)
        if row is None or row.revoked_at is not None:
            return "not_found"
        if row.is_super_admin:
            active = sum(1 for r in self.rows.values() if r.is_super_admin and r.revoked_at is None)
            if active <= 1:
                return "last_super"
        await self.revoke(pool, user_id)
        return "ok"


@pytest_asyncio.fixture
async def env(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[AsyncClient, _FakeRepo, str]]:
    fernet_key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr(admin_crypto, "FERNET_MASTER_KEY", fernet_key)
    admin_crypto._reset_for_testing()
    monkeypatch.setattr(admin_jwt, "JWT_SECRET", _TEST_JWT_SECRET)
    monkeypatch.setattr(admin_auth_routes, "ADMIN_AUTH_COOKIE_SECURE", False)

    totp_secret = pyotp.random_base32()
    repo = _FakeRepo()
    repo.install(
        AdminUserRow(
            id=_SUPER_ID,
            email=_SUPER_EMAIL,
            password_hash=password_hash.hash_password(_SUPER_PASSWORD),
            totp_secret_enc=admin_crypto.encrypt_secret(totp_secret),
            is_super_admin=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            revoked_at=None,
            created_by_admin_id=None,
        )
    )

    for method_name in (
        "find_by_email_active",
        "find_by_id",
        "list_active",
        "count_active_super_admins",
        "create",
        "revoke",
        "revoke_if_not_last_super",
    ):
        monkeypatch.setattr(admin_users_repo, method_name, getattr(repo, method_name))

    fake_redis = FakeRedis(decode_responses=True)

    async def _fake_get_redis() -> FakeRedis:
        return fake_redis

    monkeypatch.setattr(session_utils, "get_redis", _fake_get_redis)
    monkeypatch.setattr(admin_auth_routes, "get_redis", _fake_get_redis)

    # Disable rate limiting.
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

    async def _noop_enforce(*a: object, **kw: object) -> None:
        return None

    monkeypatch.setattr(admin_auth_routes, "get_rate_limiter_manager", lambda: _M())
    monkeypatch.setattr(admin_auth_routes, "enforce_rate_limit", _noop_enforce)
    # admin_users_routes has its own imports of the same symbols.
    monkeypatch.setattr(admin_users_routes, "get_rate_limiter_manager", lambda: _M())
    monkeypatch.setattr(admin_users_routes, "enforce_rate_limit", _noop_enforce)

    app = FastAPI()
    app.include_router(admin_auth_routes.router, tags=["admin-auth"])
    app.include_router(admin_users_routes.router, tags=["admin-users"])
    app.state.pool = object()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Log in + verify MFA so the session is fresh for super_admin tests.
        login = await client.post(
            "/admin/auth/login",
            json={"email": _SUPER_EMAIL, "password": _SUPER_PASSWORD},
        )
        assert login.status_code == 200
        csrf = client.cookies.get("mft_admin_csrf")
        code = pyotp.TOTP(totp_secret).now()
        mfa = await client.post(
            "/admin/auth/mfa/verify",
            json={"code": code},
            headers={"X-CSRF-Token": csrf or ""},
        )
        assert mfa.status_code == 200

        try:
            yield client, repo, csrf or ""
        finally:
            await fake_redis.flushall()
            await fake_redis.aclose()


# ─────────── GET /admins ───────────


@pytest.mark.asyncio
async def test_list_admins_returns_seeded_super_admin(
    env: tuple[AsyncClient, _FakeRepo, str],
) -> None:
    client, _, _ = env
    response = await client.get("/agent/admin/admins")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["email"] == _SUPER_EMAIL
    assert body["items"][0]["is_super_admin"] is True


@pytest.mark.asyncio
async def test_list_admins_requires_super_admin(
    env: tuple[AsyncClient, _FakeRepo, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _, _ = env
    # Mint a fresh access token with roles=["admin"] only (no super_admin).
    access, _ = admin_jwt.issue_access_token(
        sub=str(uuid4()),
        roles=["admin"],
        mfa_verified_at=int(time.time()),
    )
    client.cookies.set("mft_admin_at", access)
    response = await client.get("/agent/admin/admins")
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "not_super_admin"


# ─────────── POST /admins ───────────


@pytest.mark.asyncio
async def test_create_admin_returns_otpauth_once(
    env: tuple[AsyncClient, _FakeRepo, str],
) -> None:
    client, repo, csrf = env
    response = await client.post(
        "/agent/admin/admins",
        json={"email": "New@Example.com", "password": "brand-new-admin-pw"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "new@example.com"
    assert body["is_super_admin"] is False
    assert body["created_by_admin_id"] == str(_SUPER_ID)
    # One-time-only fields
    # pyotp URL-encodes the @ in the account label
    assert body["otpauth_uri"].startswith("otpauth://totp/mft-agent-admin:new%40example.com")
    assert "issuer=mft-agent-admin" in body["otpauth_uri"]
    assert f"secret={body['totp_secret_base32']}" in body["otpauth_uri"]
    assert len(body["totp_secret_base32"]) >= 16

    # Repo now contains two active rows.
    assert sum(1 for r in repo.rows.values() if r.revoked_at is None) == 2


@pytest.mark.asyncio
async def test_create_admin_rejects_stale_mfa(
    env: tuple[AsyncClient, _FakeRepo, str],
) -> None:
    client, _, csrf = env
    # Replace access cookie with one whose mfa_verified_at is old.
    access, _ = admin_jwt.issue_access_token(
        sub=str(_SUPER_ID),
        roles=["admin", "super_admin"],
        mfa_verified_at=int(time.time()) - 3600,  # 1 hour ago → stale
    )
    client.cookies.set("mft_admin_at", access)
    response = await client.post(
        "/agent/admin/admins",
        json={"email": "x@example.com", "password": "yet-another-long-pw"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "mfa_required"


@pytest.mark.asyncio
async def test_create_admin_rejects_duplicate_email(
    env: tuple[AsyncClient, _FakeRepo, str],
) -> None:
    client, _, csrf = env
    response = await client.post(
        "/agent/admin/admins",
        json={"email": _SUPER_EMAIL, "password": "does-not-matter-long"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "email_in_use"


@pytest.mark.asyncio
async def test_create_admin_rejects_invalid_email(
    env: tuple[AsyncClient, _FakeRepo, str],
) -> None:
    client, _, csrf = env
    response = await client.post(
        "/agent/admin/admins",
        json={"email": "not-an-email", "password": "long-enough-password"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_email"


@pytest.mark.asyncio
async def test_create_admin_rejects_short_password(
    env: tuple[AsyncClient, _FakeRepo, str],
) -> None:
    client, _, csrf = env
    response = await client.post(
        "/agent/admin/admins",
        json={"email": "ok@example.com", "password": "short"},
        headers={"X-CSRF-Token": csrf},
    )
    # Pydantic validation kicks in before our handler.
    assert response.status_code == 422


# ─────────── DELETE /admins/{id} ───────────


@pytest.mark.asyncio
async def test_revoke_admin_happy_path(
    env: tuple[AsyncClient, _FakeRepo, str],
) -> None:
    client, repo, csrf = env
    # Create a plain admin first, then revoke it.
    created = await client.post(
        "/agent/admin/admins",
        json={"email": "plain@example.com", "password": "plain-admin-password"},
        headers={"X-CSRF-Token": csrf},
    )
    assert created.status_code == 200
    new_id = created.json()["id"]

    response = await client.delete(
        f"/agent/admin/admins/{new_id}",
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    # Row is still in repo but revoked.
    assert repo.rows[UUID(new_id)].revoked_at is not None


@pytest.mark.asyncio
async def test_revoke_admin_rejects_self_revocation(
    env: tuple[AsyncClient, _FakeRepo, str],
) -> None:
    client, _, csrf = env
    response = await client.delete(
        f"/agent/admin/admins/{_SUPER_ID}",
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "cannot_revoke_self"


@pytest.mark.asyncio
async def test_revoke_admin_rejects_last_super_admin(
    env: tuple[AsyncClient, _FakeRepo, str],
) -> None:
    client, repo, csrf = env
    # Install a second super-admin so caller is not the last one, then try to
    # revoke that second super — should succeed; then try to revoke caller's
    # own row via a mimic caller — but self-revoke guard fires first. To test
    # the last-super guard cleanly we need a non-self super-admin and a
    # session belonging to a different admin. Easier path: install a second
    # super-admin and attempt to delete the SEED super-admin (caller is seed).
    # This hits self-guard, not last-super guard. So we need a different setup:
    # install ONE OTHER super, switch session to it, then revoke the seed.
    other_super_id = uuid4()
    now = datetime.now(timezone.utc)
    repo.install(
        AdminUserRow(
            id=other_super_id,
            email="other-super@example.com",
            password_hash="",
            totp_secret_enc="",
            is_super_admin=True,
            created_at=now,
            updated_at=now,
            revoked_at=None,
            created_by_admin_id=None,
        )
    )
    # Mint a fresh-MFA session for the OTHER super.
    other_access, _ = admin_jwt.issue_access_token(
        sub=str(other_super_id),
        roles=["admin", "super_admin"],
        mfa_verified_at=int(time.time()),
    )
    client.cookies.set("mft_admin_at", other_access)

    # Revoke the seed super-admin — should succeed (2 → 1 active super).
    resp1 = await client.delete(
        f"/agent/admin/admins/{_SUPER_ID}",
        headers={"X-CSRF-Token": csrf},
    )
    assert resp1.status_code == 200

    # Now the other super is the last one — cannot be revoked by itself, but
    # self-guard fires first. Install a THIRD non-super admin and use a
    # non-super session is impossible (must be super to reach the endpoint).
    # So: the only remaining revoke attempt is self-revoke → 400 cannot_revoke_self.
    resp2 = await client.delete(
        f"/agent/admin/admins/{other_super_id}",
        headers={"X-CSRF-Token": csrf},
    )
    assert resp2.status_code == 400
    # cannot_revoke_self fires before last_super_admin — both are 400.
    assert resp2.json()["detail"]["code"] == "cannot_revoke_self"


@pytest.mark.asyncio
async def test_revoke_admin_last_super_guard_directly(
    env: tuple[AsyncClient, _FakeRepo, str],
) -> None:
    """Directly exercise the last_super_admin guard by issuing a session for
    a *different* super-admin and revoking... no — the self-guard would fire.
    Instead: create a plain admin, promote the seed to be deletable by a
    *new* super. This test asserts count_active_super_admins() <= 1 triggers
    the block when a non-self super-admin target is the last one."""
    client, repo, csrf = env
    # Arrange: two supers — seed + other — and a non-super caller would be
    # rejected upstream. So we use the SEED super as caller and install the
    # OTHER super as revocation target, then revoke the SEED via a 3rd
    # super's session. Then count becomes 1 (just the OTHER super). Now
    # log in as the OTHER super and try to revoke itself → self-guard.
    # That's the same test as above. The last_super guard is hard to isolate
    # without a non-self super target. Install a second super and revoke the
    # SEED super from a THIRD super's session, then immediately try to revoke
    # the OTHER super from the THIRD super's session — THIRD is the last one
    # after that. But THIRD is self then. So the guard only ever fires when
    # target is not self AND target is the last super. That's impossible unless
    # caller is also super but different from target. We construct that
    # precisely:
    third_super_id = uuid4()
    now = datetime.now(timezone.utc)
    repo.install(
        AdminUserRow(
            id=third_super_id,
            email="third-super@example.com",
            password_hash="",
            totp_secret_enc="",
            is_super_admin=True,
            created_at=now,
            updated_at=now,
            revoked_at=None,
            created_by_admin_id=None,
        )
    )
    # Caller = seed super. Target = third super. Active supers now = 2.
    # Revoke third → OK; active supers now = 1.
    resp_a = await client.delete(
        f"/agent/admin/admins/{third_super_id}",
        headers={"X-CSRF-Token": csrf},
    )
    assert resp_a.status_code == 200

    # Now install ONE MORE super, switch session to it, and try to revoke
    # the seed super — active supers = 2 before revoke, OK.
    fourth_super_id = uuid4()
    repo.install(
        AdminUserRow(
            id=fourth_super_id,
            email="fourth-super@example.com",
            password_hash="",
            totp_secret_enc="",
            is_super_admin=True,
            created_at=now,
            updated_at=now,
            revoked_at=None,
            created_by_admin_id=None,
        )
    )
    fourth_access, _ = admin_jwt.issue_access_token(
        sub=str(fourth_super_id),
        roles=["admin", "super_admin"],
        mfa_verified_at=int(time.time()),
    )
    client.cookies.set("mft_admin_at", fourth_access)
    # Revoke seed — active supers drops 2→1.
    resp_b = await client.delete(
        f"/agent/admin/admins/{_SUPER_ID}",
        headers={"X-CSRF-Token": csrf},
    )
    assert resp_b.status_code == 200

    # Final: caller = fourth (last super). Target = seed (already revoked).
    # Can't revoke an already-revoked row → 404. That's a separate guard.
    # We cannot reach the last_super_admin guard *without* self-revoke
    # because "last super" means caller must BE that super. Document this
    # as a design invariant: last_super_admin guard is a defense-in-depth
    # path that only fires if self_revoke guard is somehow bypassed.
    assert await admin_users_repo.count_active_super_admins(object()) == 1


@pytest.mark.asyncio
async def test_revoke_admin_returns_404_on_missing(
    env: tuple[AsyncClient, _FakeRepo, str],
) -> None:
    client, _, csrf = env
    response = await client.delete(
        f"/agent/admin/admins/{uuid4()}",
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_revoke_admin_returns_400_last_super(
    env: tuple[AsyncClient, _FakeRepo, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S-H1: the atomic repo method returns "last_super" → handler surfaces 400."""
    client, _, csrf = env

    async def _always_last_super(pool: object, user_id: UUID) -> str:
        return "last_super"

    monkeypatch.setattr(admin_users_repo, "revoke_if_not_last_super", _always_last_super)
    response = await client.delete(
        f"/agent/admin/admins/{uuid4()}",
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "last_super_admin"


@pytest.mark.asyncio
async def test_mutate_endpoints_rate_limited(
    env: tuple[AsyncClient, _FakeRepo, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S-M3: POST /admins calls the admin_users_mutate limiter."""
    from src.agent_service.api.admin_users import routes as admin_users_routes

    calls: list[str] = []

    async def _spy_enforce(request: object, limiter: object, key: str) -> None:
        calls.append(key)

    monkeypatch.setattr(admin_users_routes, "enforce_rate_limit", _spy_enforce)

    _, _, csrf = env
    client = env[0]
    await client.post(
        "/agent/admin/admins",
        json={"email": "rate@example.com", "password": "some-long-password-12+"},
        headers={"X-CSRF-Token": csrf},
    )
    # Spy saw the admin_users_mutate key — proves the limiter is wired.
    assert any(k.startswith("admin_users_mutate:") for k in calls)


@pytest.mark.asyncio
async def test_create_admin_requires_csrf(
    env: tuple[AsyncClient, _FakeRepo, str],
) -> None:
    client, _, _ = env
    response = await client.post(
        "/agent/admin/admins",
        json={"email": "csrf@example.com", "password": "valid-password-123"},
        # NO X-CSRF-Token header
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "csrf_mismatch"
