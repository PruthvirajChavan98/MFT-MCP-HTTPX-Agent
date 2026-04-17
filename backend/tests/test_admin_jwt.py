from __future__ import annotations

import time
from collections.abc import AsyncIterator

import jwt
import pytest
import pytest_asyncio
from fakeredis.aioredis import FakeRedis

from src.agent_service.security import admin_jwt
from src.agent_service.security.admin_jwt import (
    _REFRESH_REDIS_PREFIX,
    AccessClaims,
    ExpiredAccessToken,
    InvalidAccessToken,
    InvalidRefreshToken,
    RefreshTokenReplayDetected,
    issue_access_token,
    issue_refresh_token,
    mfa_fresh,
    revoke_refresh_family,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_access_token,
    verify_refresh_token,
)

_TEST_JWT_SECRET = "x" * 32  # exactly 32 bytes — satisfies pyjwt 2.12.x length check
_TEST_ISSUER = "mft-agent-service"
_TEST_AUDIENCE = "mft-admin-console"


@pytest.fixture(autouse=True)
def _set_test_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test gets a valid 32-byte JWT_SECRET unless it overrides."""
    monkeypatch.setattr(admin_jwt, "JWT_SECRET", _TEST_JWT_SECRET)


@pytest_asyncio.fixture
async def redis() -> AsyncIterator[FakeRedis]:
    client = FakeRedis(decode_responses=True)
    try:
        yield client
    finally:
        await client.flushall()
        await client.aclose()


# ───────────────── access token — issue/verify round-trip ─────────────────


def test_issue_access_token_returns_token_and_claims() -> None:
    token, claims = issue_access_token("super_admin", ["admin", "super_admin"])
    assert isinstance(token, str) and token.count(".") == 2  # header.payload.sig
    assert claims.sub == "super_admin"
    assert claims.roles == ("admin", "super_admin")
    assert claims.iss == _TEST_ISSUER
    assert claims.aud == _TEST_AUDIENCE
    assert claims.mfa_verified_at is None


def test_issue_access_token_contains_all_required_claims() -> None:
    token, _ = issue_access_token("anonymous_admin", ["admin"], mfa_verified_at=1712345700)
    decoded = jwt.decode(
        token,
        _TEST_JWT_SECRET,
        algorithms=["HS256"],
        audience=_TEST_AUDIENCE,
        issuer=_TEST_ISSUER,
    )
    assert set(decoded.keys()) >= {
        "sub",
        "iss",
        "aud",
        "iat",
        "exp",
        "jti",
        "roles",
        "mfa_verified_at",
    }
    assert decoded["sub"] == "anonymous_admin"
    assert decoded["roles"] == ["admin"]
    assert decoded["mfa_verified_at"] == 1712345700


def test_verify_access_token_round_trip() -> None:
    token, issued = issue_access_token(
        "super_admin", ["admin", "super_admin"], mfa_verified_at=1712345700
    )
    verified = verify_access_token(token)
    assert verified.sub == issued.sub
    assert verified.roles == issued.roles
    assert verified.jti == issued.jti
    assert verified.mfa_verified_at == 1712345700


def test_issue_access_token_rejects_empty_sub() -> None:
    with pytest.raises(ValueError, match="sub must be non-empty"):
        issue_access_token("", ["admin"])


def test_issue_access_token_rejects_empty_roles() -> None:
    with pytest.raises(ValueError, match="roles must be non-empty"):
        issue_access_token("super_admin", [])


# ───────────────── access token — rejection paths ─────────────────


def test_verify_access_token_rejects_expired() -> None:
    now = int(time.time())
    expired = jwt.encode(
        {
            "sub": "super_admin",
            "iss": _TEST_ISSUER,
            "aud": _TEST_AUDIENCE,
            "iat": now - 2000,
            "exp": now - 1000,
            "jti": "test-jti",
            "roles": ["admin"],
            "mfa_verified_at": None,
        },
        _TEST_JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(ExpiredAccessToken):
        verify_access_token(expired)


def test_verify_access_token_rejects_tampered_signature() -> None:
    token, _ = issue_access_token("super_admin", ["admin"])
    # Mutate the last character of the signature segment
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(InvalidAccessToken):
        verify_access_token(tampered)


def test_verify_access_token_rejects_wrong_audience() -> None:
    now = int(time.time())
    wrong_aud = jwt.encode(
        {
            "sub": "super_admin",
            "iss": _TEST_ISSUER,
            "aud": "wrong-audience",
            "iat": now,
            "exp": now + 900,
            "jti": "test-jti",
            "roles": ["admin"],
            "mfa_verified_at": None,
        },
        _TEST_JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(InvalidAccessToken):
        verify_access_token(wrong_aud)


def test_verify_access_token_rejects_wrong_issuer() -> None:
    now = int(time.time())
    wrong_iss = jwt.encode(
        {
            "sub": "super_admin",
            "iss": "wrong-issuer",
            "aud": _TEST_AUDIENCE,
            "iat": now,
            "exp": now + 900,
            "jti": "test-jti",
            "roles": ["admin"],
            "mfa_verified_at": None,
        },
        _TEST_JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(InvalidAccessToken):
        verify_access_token(wrong_iss)


def test_verify_access_token_rejects_missing_jti() -> None:
    now = int(time.time())
    no_jti = jwt.encode(
        {
            "sub": "super_admin",
            "iss": _TEST_ISSUER,
            "aud": _TEST_AUDIENCE,
            "iat": now,
            "exp": now + 900,
            "roles": ["admin"],
            "mfa_verified_at": None,
        },
        _TEST_JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(InvalidAccessToken):
        verify_access_token(no_jti)


def test_verify_access_token_rejects_missing_roles() -> None:
    now = int(time.time())
    no_roles = jwt.encode(
        {
            "sub": "super_admin",
            "iss": _TEST_ISSUER,
            "aud": _TEST_AUDIENCE,
            "iat": now,
            "exp": now + 900,
            "jti": "test-jti",
            "mfa_verified_at": None,
        },
        _TEST_JWT_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(InvalidAccessToken):
        verify_access_token(no_roles)


def test_verify_access_token_rejects_empty_token() -> None:
    with pytest.raises(InvalidAccessToken):
        verify_access_token("")


# ───────────────── mfa_fresh ─────────────────


def test_mfa_fresh_true_within_window() -> None:
    now = int(time.time())
    claims = AccessClaims(
        sub="super_admin",
        iss=_TEST_ISSUER,
        aud=_TEST_AUDIENCE,
        iat=now - 200,
        exp=now + 700,
        jti="test-jti",
        roles=("admin", "super_admin"),
        mfa_verified_at=now - 100,
    )
    assert mfa_fresh(claims, now=now) is True


def test_mfa_fresh_false_outside_window() -> None:
    now = int(time.time())
    claims = AccessClaims(
        sub="super_admin",
        iss=_TEST_ISSUER,
        aud=_TEST_AUDIENCE,
        iat=now - 500,
        exp=now + 400,
        jti="test-jti",
        roles=("admin", "super_admin"),
        mfa_verified_at=now - 400,  # > 300 sec default
    )
    assert mfa_fresh(claims, now=now) is False


def test_mfa_fresh_false_when_none() -> None:
    now = int(time.time())
    claims = AccessClaims(
        sub="anonymous_admin",
        iss=_TEST_ISSUER,
        aud=_TEST_AUDIENCE,
        iat=now,
        exp=now + 900,
        jti="test-jti",
        roles=("admin",),
        mfa_verified_at=None,
    )
    assert mfa_fresh(claims, now=now) is False


# ───────────────── refresh token ─────────────────


@pytest.mark.asyncio
async def test_issue_refresh_token_writes_family_to_redis(redis: FakeRedis) -> None:
    token, handle = await issue_refresh_token(redis, "super_admin")
    assert token.count(".") == 2
    key = f"{_REFRESH_REDIS_PREFIX}{handle.family_id}"
    data = await redis.hgetall(key)
    assert data["current_token_id"] == handle.token_id
    assert data["sub"] == "super_admin"
    assert data["revoked"] == "0"
    ttl = await redis.ttl(key)
    assert 0 < ttl <= 28800  # JWT_REFRESH_TTL_SECONDS default


@pytest.mark.asyncio
async def test_verify_refresh_token_accepts_current_token(redis: FakeRedis) -> None:
    token, issued = await issue_refresh_token(redis, "super_admin")
    verified = await verify_refresh_token(redis, token)
    assert verified.family_id == issued.family_id
    assert verified.token_id == issued.token_id
    assert verified.sub == "super_admin"


@pytest.mark.asyncio
async def test_rotate_refresh_token_mints_new_token_id(redis: FakeRedis) -> None:
    old_token, old_handle = await issue_refresh_token(redis, "super_admin")
    new_token, new_handle = await rotate_refresh_token(redis, old_token)
    assert new_handle.family_id == old_handle.family_id
    assert new_handle.token_id != old_handle.token_id
    assert new_token != old_token
    # New token verifies
    verified = await verify_refresh_token(redis, new_token)
    assert verified.token_id == new_handle.token_id


@pytest.mark.asyncio
async def test_rotate_refresh_token_preserves_family_ttl(redis: FakeRedis) -> None:
    _, old_handle = await issue_refresh_token(redis, "super_admin")
    key = f"{_REFRESH_REDIS_PREFIX}{old_handle.family_id}"
    # Force TTL to a known value to detect any reset on rotation
    await redis.expire(key, 100)
    old_ttl = await redis.ttl(key)
    _, _ = await rotate_refresh_token(
        redis, _sign_test_token(old_handle.family_id, old_handle.token_id)
    )
    new_ttl = await redis.ttl(key)
    # TTL should not INCREASE (fixed-window semantics). It may decrease slightly due to elapsed time.
    assert new_ttl <= old_ttl


@pytest.mark.asyncio
async def test_rotate_refresh_token_replay_detection_revokes_family(redis: FakeRedis) -> None:
    old_token, old_handle = await issue_refresh_token(redis, "super_admin")
    await rotate_refresh_token(redis, old_token)  # legitimate rotation
    # Attempt to reuse the old token — replay attack
    with pytest.raises(RefreshTokenReplayDetected):
        await verify_refresh_token(redis, old_token)
    # Family must now be marked revoked
    key = f"{_REFRESH_REDIS_PREFIX}{old_handle.family_id}"
    data = await redis.hgetall(key)
    assert data["revoked"] == "1"


@pytest.mark.asyncio
async def test_verify_refresh_token_rejects_tampered_hmac(redis: FakeRedis) -> None:
    token, _ = await issue_refresh_token(redis, "super_admin")
    tampered = token[:-4] + "XXXX"
    with pytest.raises(InvalidRefreshToken):
        await verify_refresh_token(redis, tampered)


@pytest.mark.asyncio
async def test_verify_refresh_token_rejects_nonexistent_family(redis: FakeRedis) -> None:
    # Issue then wipe Redis to simulate expired / missing family
    token, _ = await issue_refresh_token(redis, "super_admin")
    await redis.flushall()
    with pytest.raises(InvalidRefreshToken, match="not found"):
        await verify_refresh_token(redis, token)


@pytest.mark.asyncio
async def test_verify_refresh_token_rejects_revoked_family(redis: FakeRedis) -> None:
    token, handle = await issue_refresh_token(redis, "super_admin")
    await revoke_refresh_family(redis, handle.family_id)
    with pytest.raises(InvalidRefreshToken, match="revoked"):
        await verify_refresh_token(redis, token)


@pytest.mark.asyncio
async def test_revoke_refresh_family_is_idempotent(redis: FakeRedis) -> None:
    _, handle = await issue_refresh_token(redis, "super_admin")
    await revoke_refresh_family(redis, handle.family_id)
    await revoke_refresh_family(redis, handle.family_id)  # second call must not raise
    key = f"{_REFRESH_REDIS_PREFIX}{handle.family_id}"
    data = await redis.hgetall(key)
    assert data["revoked"] == "1"


@pytest.mark.asyncio
async def test_verify_refresh_token_rejects_malformed_token(redis: FakeRedis) -> None:
    with pytest.raises(InvalidRefreshToken, match="malformed"):
        await verify_refresh_token(redis, "not-a-valid-refresh-token")


# ─────────── revoke_refresh_token(token) public wrapper (Phase 3b) ───────────


@pytest.mark.asyncio
async def test_revoke_refresh_token_by_string_revokes_family(redis: FakeRedis) -> None:
    token, handle = await issue_refresh_token(redis, "super_admin")
    await revoke_refresh_token(redis, token)
    key = f"{_REFRESH_REDIS_PREFIX}{handle.family_id}"
    data = await redis.hgetall(key)
    assert data["revoked"] == "1"


@pytest.mark.asyncio
async def test_revoke_refresh_token_idempotent_on_malformed(redis: FakeRedis) -> None:
    # Must not raise — logout path calls this unconditionally
    await revoke_refresh_token(redis, "not-a-valid-refresh-token")
    await revoke_refresh_token(redis, "")


@pytest.mark.asyncio
async def test_revoke_refresh_token_then_verify_raises(redis: FakeRedis) -> None:
    token, _ = await issue_refresh_token(redis, "super_admin")
    await revoke_refresh_token(redis, token)
    with pytest.raises(InvalidRefreshToken, match="revoked"):
        await verify_refresh_token(redis, token)


def _sign_test_token(family_id: str, token_id: str) -> str:
    """Test helper — produces the refresh token string that matches a given family/token."""
    import hashlib
    import hmac as _hmac

    msg = f"{family_id}.{token_id}".encode("utf-8")
    mac = _hmac.new(_TEST_JWT_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return f"{family_id}.{token_id}.{mac}"


# ───────────────── review remediation — P2 regression guards ─────────────────


@pytest.mark.asyncio
async def test_rotate_refresh_token_concurrent_rotates_exactly_one_succeeds(
    redis: FakeRedis,
) -> None:
    """HIGH #2 — TOCTOU fix.

    Two concurrent rotates with the SAME old_token should resolve to:
      - exactly one mints a new token
      - the other sees RefreshTokenReplayDetected (WATCH/EXEC conflict)
      - the family ends up revoked (replay-detection contract)

    Prior code was not atomic — it did verify→hset in two trips, letting both
    callers pass verify and both mint tokens. Now WATCH/MULTI/EXEC serializes
    them at the Redis layer.
    """
    import asyncio

    old_token, _ = await issue_refresh_token(redis, sub="super_admin")

    results = await asyncio.gather(
        rotate_refresh_token(redis, old_token),
        rotate_refresh_token(redis, old_token),
        return_exceptions=True,
    )

    successes = [r for r in results if not isinstance(r, BaseException)]
    replays = [r for r in results if isinstance(r, RefreshTokenReplayDetected)]

    assert len(successes) == 1, f"exactly 1 should succeed, got {len(successes)}: {results}"
    assert len(replays) == 1, f"exactly 1 should be replay, got {len(replays)}: {results}"

    # Family must be revoked after the replay detection
    family_id = _parse_old_family(old_token)
    revoked_flag = await redis.hget(  # type: ignore[misc]
        f"{_REFRESH_REDIS_PREFIX}{family_id}", "revoked"
    )
    assert revoked_flag == "1"


@pytest.mark.asyncio
async def test_rotate_refresh_token_preserves_family_ttl_after_cas(
    redis: FakeRedis,
) -> None:
    """Regression: switching to WATCH/MULTI/EXEC must still preserve the fixed-window TTL."""
    old_token, _ = await issue_refresh_token(redis, sub="super_admin")

    family_id = _parse_old_family(old_token)
    key = f"{_REFRESH_REDIS_PREFIX}{family_id}"
    ttl_before = await redis.ttl(key)

    _, _ = await rotate_refresh_token(redis, old_token)
    ttl_after = await redis.ttl(key)

    # TTL should NOT have been reset (fixed-window policy preserved).
    assert ttl_after <= ttl_before  # allowed to decrement by the test's elapsed ms
    assert ttl_after > 0


def test_parse_refresh_rejects_token_with_no_dots() -> None:
    """HIGH #3 — maxsplit=2 defensive parse. 'no-dots' has 1 part → rejected."""
    with pytest.raises(InvalidRefreshToken, match="malformed"):
        admin_jwt._parse_refresh("just-one-chunk")


def test_parse_refresh_rejects_token_with_one_dot() -> None:
    """Two parts → rejected."""
    with pytest.raises(InvalidRefreshToken, match="malformed"):
        admin_jwt._parse_refresh("family.token")


def test_parse_refresh_rejects_token_with_empty_segment() -> None:
    """Empty middle segment → rejected by `not all(parts)`."""
    with pytest.raises(InvalidRefreshToken, match="malformed"):
        admin_jwt._parse_refresh("family..hmac")


def test_parse_refresh_accepts_extra_dots_in_hmac_segment() -> None:
    """HIGH #3 — with maxsplit=2, even if the HMAC ever becomes a value containing
    dots (e.g. base64url), parsing stays deterministic — family/token_id are the
    first two parts, everything else is the hmac.
    """
    family, token_id, hmac_part = admin_jwt._parse_refresh("fam.tok.mac.with.dots")
    assert family == "fam"
    assert token_id == "tok"
    assert hmac_part == "mac.with.dots"


def test_sign_refresh_rejects_family_id_with_dot() -> None:
    """HIGH #3 — no-dot assertion in _sign_refresh, so a generation-source change
    that introduces '.' (e.g. switching to base64 IDs) fails loudly.
    """
    with pytest.raises(ValueError, match="must not contain"):
        admin_jwt._sign_refresh("family.with.dot", "token_id")


def test_sign_refresh_rejects_token_id_with_dot() -> None:
    with pytest.raises(ValueError, match="must not contain"):
        admin_jwt._sign_refresh("family", "token.with.dot")


def test_verify_access_token_rejects_non_numeric_mfa_verified_at() -> None:
    """HIGH #4 — a forged token with mfa_verified_at='never' must raise
    InvalidAccessToken cleanly, not leak a 500 with a ValueError stack trace.
    """
    # Mint a token with a string mfa_verified_at by building it manually (bypasses
    # the dataclass path which enforces int | None)
    now_ts = int(time.time())
    claims = {
        "sub": "super_admin",
        "iss": _TEST_ISSUER,
        "aud": _TEST_AUDIENCE,
        "iat": now_ts,
        "exp": now_ts + 900,
        "jti": "forged-jti",
        "roles": ["admin"],
        "mfa_verified_at": "never",  # wrong type
    }
    token = jwt.encode(claims, _TEST_JWT_SECRET, algorithm="HS256")

    with pytest.raises(InvalidAccessToken, match="mfa_verified_at claim must be a number"):
        verify_access_token(token)


def test_verify_access_token_rejects_bool_mfa_verified_at() -> None:
    """bool is a subclass of int in Python — explicitly reject True/False."""
    now_ts = int(time.time())
    claims = {
        "sub": "super_admin",
        "iss": _TEST_ISSUER,
        "aud": _TEST_AUDIENCE,
        "iat": now_ts,
        "exp": now_ts + 900,
        "jti": "forged-jti",
        "roles": ["admin"],
        "mfa_verified_at": True,
    }
    token = jwt.encode(claims, _TEST_JWT_SECRET, algorithm="HS256")

    with pytest.raises(InvalidAccessToken, match="mfa_verified_at claim must be a number"):
        verify_access_token(token)


def test_verify_access_token_accepts_float_mfa_verified_at() -> None:
    """A float timestamp (e.g. PyJWT sometimes round-trips as float) must coerce cleanly."""
    now_ts = int(time.time())
    claims = {
        "sub": "super_admin",
        "iss": _TEST_ISSUER,
        "aud": _TEST_AUDIENCE,
        "iat": now_ts,
        "exp": now_ts + 900,
        "jti": "j",
        "roles": ["admin"],
        "mfa_verified_at": float(now_ts - 60),
    }
    token = jwt.encode(claims, _TEST_JWT_SECRET, algorithm="HS256")

    result = verify_access_token(token)
    assert result.mfa_verified_at == now_ts - 60


def _parse_old_family(old_token: str) -> str:
    """Test helper — extract the family_id from a refresh token string."""
    return old_token.split(".", 2)[0]
