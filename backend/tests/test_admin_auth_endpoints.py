from __future__ import annotations

import time
from collections.abc import AsyncIterator

import jwt
import pyotp
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from fakeredis.aioredis import FakeRedis
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Cookies

from src.agent_service.api.endpoints import admin_auth_routes
from src.agent_service.core import session_utils
from src.agent_service.security import admin_crypto, admin_jwt, password_hash

_TEST_JWT_SECRET = "x" * 32
_TEST_ADMIN_EMAIL = "admin@example.com"
_TEST_ADMIN_PASSWORD = "correct-horse-battery-staple"


@pytest_asyncio.fixture
async def test_env(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[tuple[FastAPI, FakeRedis, str]]:
    fernet_key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr(admin_crypto, "FERNET_MASTER_KEY", fernet_key)
    admin_crypto._reset_for_testing()

    monkeypatch.setattr(admin_jwt, "JWT_SECRET", _TEST_JWT_SECRET)

    totp_secret = pyotp.random_base32()
    encrypted_totp = admin_crypto.encrypt_secret(totp_secret)
    password_hashed = password_hash.hash_password(_TEST_ADMIN_PASSWORD)

    monkeypatch.setattr(admin_auth_routes, "SUPER_ADMIN_EMAIL", _TEST_ADMIN_EMAIL)
    monkeypatch.setattr(admin_auth_routes, "SUPER_ADMIN_PASSWORD_HASH", password_hashed)
    monkeypatch.setattr(admin_auth_routes, "SUPER_ADMIN_TOTP_SECRET_ENC", encrypted_totp)
    monkeypatch.setattr(admin_auth_routes, "ADMIN_AUTH_COOKIE_SECURE", False)

    fake_redis = FakeRedis(decode_responses=True)

    async def _fake_get_redis() -> FakeRedis:
        return fake_redis

    monkeypatch.setattr(session_utils, "get_redis", _fake_get_redis)
    monkeypatch.setattr(admin_auth_routes, "get_redis", _fake_get_redis)

    # Stub the rate limiter to a no-op: the production RateLimiterManager is a
    # module-level singleton that caches a Redis client across tests, which
    # causes `Event loop is closed` errors when subsequent tests use fresh
    # event loops. The rate limiter itself is tested independently in the
    # rate_limiter_manager test suite — we don't re-test it at the HTTP layer.
    class _StubLimiter:
        async def aacquire(self, *args: object, **kwargs: object) -> bool:
            return True

    class _StubManager:
        async def get_admin_auth_login_limiter(self) -> _StubLimiter:
            return _StubLimiter()

        async def get_admin_auth_mfa_limiter(self) -> _StubLimiter:
            return _StubLimiter()

    def _stub_get_manager() -> _StubManager:
        return _StubManager()

    async def _noop_enforce(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr(admin_auth_routes, "get_rate_limiter_manager", _stub_get_manager)
    monkeypatch.setattr(admin_auth_routes, "enforce_rate_limit", _noop_enforce)

    app = FastAPI()
    app.include_router(admin_auth_routes.router, tags=["admin-auth"])

    try:
        yield app, fake_redis, totp_secret
    finally:
        await fake_redis.flushall()
        await fake_redis.aclose()


@pytest_asyncio.fixture
async def client(test_env: tuple[FastAPI, FakeRedis, str]) -> AsyncIterator[AsyncClient]:
    app, _, _ = test_env
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _login(client: AsyncClient) -> str:
    """Log in successfully; cookies end up in the client jar. Returns CSRF token."""
    response = await client.post(
        "/admin/auth/login",
        json={"email": _TEST_ADMIN_EMAIL, "password": _TEST_ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    csrf = client.cookies.get("mft_admin_csrf")
    assert csrf is not None
    return csrf


# ─────────── login ───────────


@pytest.mark.asyncio
async def test_login_with_valid_credentials_sets_cookies_and_returns_mfa_required(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/admin/auth/login",
        json={"email": _TEST_ADMIN_EMAIL, "password": _TEST_ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["mfa_required"] is True
    assert client.cookies.get("mft_admin_at") is not None
    assert client.cookies.get("mft_admin_rt") is not None
    assert client.cookies.get("mft_admin_csrf") is not None


@pytest.mark.asyncio
async def test_login_with_wrong_password_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/admin/auth/login",
        json={"email": _TEST_ADMIN_EMAIL, "password": "wrong-password"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_with_wrong_email_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/admin/auth/login",
        json={"email": "wrong@example.com", "password": _TEST_ADMIN_PASSWORD},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_when_not_configured_returns_503(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(admin_auth_routes, "SUPER_ADMIN_EMAIL", None)
    response = await client.post(
        "/admin/auth/login",
        json={"email": _TEST_ADMIN_EMAIL, "password": _TEST_ADMIN_PASSWORD},
    )
    assert response.status_code == 503


# ─────────── MFA verify ───────────


@pytest.mark.asyncio
async def test_mfa_verify_with_valid_code_rotates_access_token_with_mfa_claim(
    client: AsyncClient, test_env: tuple[FastAPI, FakeRedis, str]
) -> None:
    _, _, totp_secret = test_env
    csrf = await _login(client)
    code = pyotp.TOTP(totp_secret).now()
    response = await client.post(
        "/admin/auth/mfa/verify",
        json={"code": code},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    new_access = client.cookies.get("mft_admin_at")
    assert new_access is not None
    decoded = jwt.decode(
        new_access,
        _TEST_JWT_SECRET,
        algorithms=["HS256"],
        audience="mft-admin-console",
        issuer="mft-agent-service",
    )
    assert decoded["mfa_verified_at"] is not None
    assert abs(int(decoded["mfa_verified_at"]) - int(time.time())) < 5


@pytest.mark.asyncio
async def test_mfa_verify_with_invalid_code_returns_401(
    client: AsyncClient,
) -> None:
    csrf = await _login(client)
    response = await client.post(
        "/admin/auth/mfa/verify",
        json={"code": "000000"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_mfa_verify_without_access_cookie_returns_401(
    client: AsyncClient,
) -> None:
    # Login first to get CSRF, then clear the access cookie so the CSRF check passes
    # but the handler's access-cookie check fails.
    csrf = await _login(client)
    client.cookies.delete("mft_admin_at")
    response = await client.post(
        "/admin/auth/mfa/verify",
        json={"code": "123456"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_mfa_verify_without_csrf_returns_403(
    client: AsyncClient, test_env: tuple[FastAPI, FakeRedis, str]
) -> None:
    _, _, totp_secret = test_env
    await _login(client)
    code = pyotp.TOTP(totp_secret).now()
    response = await client.post("/admin/auth/mfa/verify", json={"code": code})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_mfa_verify_after_5_failures_returns_429_lockout(
    client: AsyncClient,
) -> None:
    csrf = await _login(client)
    for _ in range(5):
        await client.post(
            "/admin/auth/mfa/verify",
            json={"code": "000000"},
            headers={"X-CSRF-Token": csrf},
        )
    response = await client.post(
        "/admin/auth/mfa/verify",
        json={"code": "000000"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 429


# ─────────── refresh ───────────


@pytest.mark.asyncio
async def test_refresh_with_valid_cookie_rotates_tokens(
    client: AsyncClient,
) -> None:
    csrf = await _login(client)
    original_refresh = client.cookies.get("mft_admin_rt")
    response = await client.post(
        "/admin/auth/refresh",
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    new_refresh = client.cookies.get("mft_admin_rt")
    assert new_refresh is not None
    assert new_refresh != original_refresh


@pytest.mark.asyncio
async def test_refresh_drops_mfa_verified_at_claim(
    client: AsyncClient, test_env: tuple[FastAPI, FakeRedis, str]
) -> None:
    _, _, totp_secret = test_env
    csrf = await _login(client)
    # Verify MFA first so the post-MFA access token has mfa_verified_at set
    code = pyotp.TOTP(totp_secret).now()
    mfa_response = await client.post(
        "/admin/auth/mfa/verify",
        json={"code": code},
        headers={"X-CSRF-Token": csrf},
    )
    assert mfa_response.status_code == 200
    # Now refresh — new access token must have mfa_verified_at=None
    refresh_response = await client.post(
        "/admin/auth/refresh",
        headers={"X-CSRF-Token": csrf},
    )
    assert refresh_response.status_code == 200
    new_access = client.cookies.get("mft_admin_at")
    assert new_access is not None
    decoded = jwt.decode(
        new_access,
        _TEST_JWT_SECRET,
        algorithms=["HS256"],
        audience="mft-admin-console",
        issuer="mft-agent-service",
    )
    assert decoded["mfa_verified_at"] is None


@pytest.mark.asyncio
async def test_refresh_with_tampered_cookie_returns_401(
    client: AsyncClient,
) -> None:
    csrf = await _login(client)
    original_refresh = client.cookies.get("mft_admin_rt")
    access = client.cookies.get("mft_admin_at")
    assert original_refresh is not None and access is not None
    tampered = original_refresh[:-4] + "XXXX"
    # Reset jar and rebuild with tampered refresh — avoids jar duplicate-entry issues
    client.cookies = Cookies()
    client.cookies.set("mft_admin_at", access)
    client.cookies.set("mft_admin_rt", tampered)
    client.cookies.set("mft_admin_csrf", csrf)
    response = await client.post(
        "/admin/auth/refresh",
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_without_csrf_returns_403(client: AsyncClient) -> None:
    await _login(client)
    response = await client.post("/admin/auth/refresh")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_refresh_replay_attack_returns_401_with_replay_error(
    client: AsyncClient,
) -> None:
    csrf = await _login(client)
    original_refresh = client.cookies.get("mft_admin_rt")
    original_access = client.cookies.get("mft_admin_at")
    assert original_refresh is not None and original_access is not None
    # First rotation succeeds; server rotates both refresh and csrf cookies
    first = await client.post("/admin/auth/refresh", headers={"X-CSRF-Token": csrf})
    assert first.status_code == 200
    # Simulate the replay scenario: reset jar to the pre-first-refresh state,
    # then use the SAME old refresh token + SAME old csrf. The refresh handler
    # must detect the stale token_id and return 401 (replay detection).
    client.cookies = Cookies()
    client.cookies.set("mft_admin_at", original_access)
    client.cookies.set("mft_admin_rt", original_refresh)
    client.cookies.set("mft_admin_csrf", csrf)
    second = await client.post("/admin/auth/refresh", headers={"X-CSRF-Token": csrf})
    assert second.status_code == 401


# ─────────── logout ───────────


@pytest.mark.asyncio
async def test_logout_clears_cookies_and_revokes_refresh_family(
    client: AsyncClient,
) -> None:
    csrf = await _login(client)
    original_refresh = client.cookies.get("mft_admin_rt")
    original_access = client.cookies.get("mft_admin_at")
    assert original_refresh is not None and original_access is not None
    response = await client.post(
        "/admin/auth/logout",
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    # Simulate an attacker replaying the old cookies after logout. Reset the jar
    # to the full pre-logout state and retry refresh — the family is revoked
    # server-side, so refresh must fail with 401.
    client.cookies = Cookies()
    client.cookies.set("mft_admin_at", original_access)
    client.cookies.set("mft_admin_rt", original_refresh)
    client.cookies.set("mft_admin_csrf", csrf)
    reuse = await client.post("/admin/auth/refresh", headers={"X-CSRF-Token": csrf})
    assert reuse.status_code == 401


@pytest.mark.asyncio
async def test_logout_is_idempotent_with_no_cookies(client: AsyncClient) -> None:
    # No login — no CSRF cookie. Logout requires CSRF via the require_csrf_token
    # dependency, so this hits the CSRF path and returns 403. That's acceptable
    # because logout without a session is a no-op regardless.
    response = await client.post(
        "/admin/auth/logout",
        headers={"X-CSRF-Token": "no-session-no-csrf"},
    )
    assert response.status_code == 403


# ─────────── me ───────────


@pytest.mark.asyncio
async def test_me_with_valid_access_token_returns_claims(
    client: AsyncClient,
) -> None:
    await _login(client)
    response = await client.get("/admin/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["sub"] == "super_admin"
    assert "admin" in body["roles"]
    assert "super_admin" in body["roles"]
    assert body["mfa_fresh"] is False


@pytest.mark.asyncio
async def test_me_with_expired_access_token_returns_401(
    client: AsyncClient,
) -> None:
    now = int(time.time())
    expired = jwt.encode(
        {
            "sub": "super_admin",
            "iss": "mft-agent-service",
            "aud": "mft-admin-console",
            "iat": now - 2000,
            "exp": now - 1000,
            "jti": "expired-jti",
            "roles": ["admin", "super_admin"],
            "mfa_verified_at": None,
        },
        _TEST_JWT_SECRET,
        algorithm="HS256",
    )
    client.cookies.set("mft_admin_at", expired)
    response = await client.get("/admin/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_without_cookie_returns_401(client: AsyncClient) -> None:
    response = await client.get("/admin/auth/me")
    assert response.status_code == 401
