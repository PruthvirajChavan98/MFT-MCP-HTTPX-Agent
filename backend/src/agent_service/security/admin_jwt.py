"""Admin JWT issuer/verifier + opaque refresh token store (Redis-backed).

Dormant module — no side effects at import time. Activated when ADMIN_AUTH_ENABLED=True.

Access tokens are standard HS256 JWTs with claims sub, iss, aud, iat, exp, jti, roles,
mfa_verified_at. Refresh tokens are opaque strings of the form
"<family_id>.<token_id>.<hmac_sha256>" with Redis-backed family rotation and replay
detection. Family state lives at key `admin_auth:rt:<family_id>` with fields
current_token_id, sub, revoked. TTL equals JWT_REFRESH_TTL_SECONDS (fixed-window).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

import jwt
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    PyJWTError,
)
from redis.exceptions import WatchError

from src.agent_service.core.config import (
    JWT_ACCESS_TTL_SECONDS,
    JWT_ALGORITHM,
    JWT_AUDIENCE,
    JWT_ISSUER,
    JWT_MFA_FRESHNESS_SECONDS,
    JWT_REFRESH_TTL_SECONDS,
    JWT_SECRET,
)
from src.agent_service.security.admin_crypto import validate_jwt_secret

if TYPE_CHECKING:
    from redis.asyncio import Redis

log = logging.getLogger(__name__)

_REFRESH_REDIS_PREFIX: Final[str] = "admin_auth:rt:"


# ───────────────── exceptions ─────────────────


class InvalidAccessToken(Exception):
    """Raised when an access token fails signature, issuer, audience, or claim checks."""


class ExpiredAccessToken(InvalidAccessToken):
    """Raised specifically when an access token is expired (narrow catch for 'please refresh')."""


class InvalidRefreshToken(Exception):
    """Raised when a refresh token fails HMAC verification or Redis family lookup."""


class RefreshTokenReplayDetected(InvalidRefreshToken):
    """Raised when a rotated refresh token is reused — family is revoked on detection."""


# ───────────────── dataclasses ─────────────────


@dataclass(frozen=True)
class AccessClaims:
    sub: str
    iss: str
    aud: str
    iat: int
    exp: int
    jti: str
    roles: tuple[str, ...]
    mfa_verified_at: int | None


@dataclass(frozen=True)
class RefreshHandle:
    family_id: str
    token_id: str
    sub: str
    issued_at: int
    expires_at: int


# ───────────────── access token ─────────────────


def issue_access_token(
    sub: str,
    roles: Sequence[str],
    *,
    mfa_verified_at: int | None = None,
    now: int | None = None,
) -> tuple[str, AccessClaims]:
    """Issue an HS256 JWT access token. Returns (token_string, claims)."""
    if not sub:
        raise ValueError("issue_access_token: sub must be non-empty")
    if not roles:
        raise ValueError("issue_access_token: roles must be non-empty")
    validate_jwt_secret(JWT_SECRET)
    assert JWT_SECRET is not None  # narrowed by validate_jwt_secret

    now_ts = now if now is not None else int(time.time())
    exp_ts = now_ts + JWT_ACCESS_TTL_SECONDS
    jti = uuid.uuid4().hex

    claims_dict: dict[str, object] = {
        "sub": sub,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": now_ts,
        "exp": exp_ts,
        "jti": jti,
        "roles": list(roles),
        "mfa_verified_at": mfa_verified_at,
    }
    token = jwt.encode(claims_dict, JWT_SECRET, algorithm=JWT_ALGORITHM)

    return token, AccessClaims(
        sub=sub,
        iss=JWT_ISSUER,
        aud=JWT_AUDIENCE,
        iat=now_ts,
        exp=exp_ts,
        jti=jti,
        roles=tuple(roles),
        mfa_verified_at=mfa_verified_at,
    )


def verify_access_token(token: str) -> AccessClaims:
    """Verify signature, issuer, audience, expiration, and required claims.

    Raises ExpiredAccessToken if expired; InvalidAccessToken otherwise.
    """
    if not token:
        raise InvalidAccessToken("access token is empty")
    validate_jwt_secret(JWT_SECRET)
    assert JWT_SECRET is not None

    try:
        decoded = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            options={
                "require": ["sub", "iss", "aud", "iat", "exp", "jti"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": True,
                "verify_iss": True,
            },
        )
    except ExpiredSignatureError as e:
        raise ExpiredAccessToken("access token is expired") from e
    except InvalidAudienceError as e:
        raise InvalidAccessToken(f"invalid audience: {e}") from e
    except InvalidIssuerError as e:
        raise InvalidAccessToken(f"invalid issuer: {e}") from e
    except PyJWTError as e:
        raise InvalidAccessToken(f"invalid access token: {e}") from e

    if "roles" not in decoded:
        raise InvalidAccessToken("missing required claim: roles")

    # Fix #4: guard int() coercion — decoded JWT claims can be any JSON type.
    # Prior code raised uncaught ValueError on e.g. mfa_verified_at="never",
    # leaking a 500 stack trace. bool is a subclass of int in Python so reject
    # explicitly (True/False should never have been a valid claim value).
    mva_raw = decoded.get("mfa_verified_at")
    if mva_raw is None:
        mfa_verified_at = None
    elif isinstance(mva_raw, bool) or not isinstance(mva_raw, (int, float)):
        raise InvalidAccessToken(
            f"mfa_verified_at claim must be a number, got {type(mva_raw).__name__}"
        )
    else:
        mfa_verified_at = int(mva_raw)

    return AccessClaims(
        sub=str(decoded["sub"]),
        iss=str(decoded["iss"]),
        aud=str(decoded["aud"]),
        iat=int(decoded["iat"]),
        exp=int(decoded["exp"]),
        jti=str(decoded["jti"]),
        roles=tuple(str(r) for r in decoded["roles"]),
        mfa_verified_at=mfa_verified_at,
    )


def mfa_fresh(claims: AccessClaims, now: int | None = None) -> bool:
    """True iff claims.mfa_verified_at is within JWT_MFA_FRESHNESS_SECONDS of `now`."""
    if claims.mfa_verified_at is None:
        return False
    now_ts = now if now is not None else int(time.time())
    age = now_ts - claims.mfa_verified_at
    return 0 <= age < JWT_MFA_FRESHNESS_SECONDS


# ───────────────── refresh token (opaque, Redis-backed) ─────────────────


def _sign_refresh(family_id: str, token_id: str) -> str:
    """Returns '<family_id>.<token_id>.<hmac_sha256_hex>'.

    family_id and token_id MUST NOT contain '.' — the parse side uses '.' as a
    delimiter. uuid4().hex (the only current caller) is safe by construction, but
    assert defensively so a future generation-source change that introduces dots
    (e.g. base64 or UUID-with-hyphens) fails here rather than silently corrupting
    the parse on verify.
    """
    if "." in family_id or "." in token_id:
        raise ValueError("refresh token family_id / token_id must not contain '.'")
    validate_jwt_secret(JWT_SECRET)
    assert JWT_SECRET is not None
    msg = f"{family_id}.{token_id}".encode("utf-8")
    mac = hmac.new(JWT_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return f"{family_id}.{token_id}.{mac}"


def _parse_refresh(token: str) -> tuple[str, str, str]:
    """Returns (family_id, token_id, hmac). Raises InvalidRefreshToken on malformed input.

    Uses split('.', 2) — maxsplit=2 yields at most 3 parts. Together with the
    no-dot assertion in _sign_refresh, this guarantees deterministic parsing even
    if the token format is ever extended (e.g. if the HMAC field is replaced with
    a base64url value that could incidentally contain a '.').
    """
    if not token:
        raise InvalidRefreshToken("refresh token is empty")
    parts = token.split(".", 2)
    if len(parts) != 3 or not all(parts):
        raise InvalidRefreshToken("malformed refresh token")
    return parts[0], parts[1], parts[2]


def _verify_refresh_hmac(family_id: str, token_id: str, provided_mac: str) -> None:
    """Constant-time HMAC comparison. Raises InvalidRefreshToken on mismatch."""
    expected_full = _sign_refresh(family_id, token_id)
    expected_mac = expected_full.rsplit(".", 1)[1]
    if not hmac.compare_digest(expected_mac, provided_mac):
        raise InvalidRefreshToken("refresh token signature invalid")


async def issue_refresh_token(
    redis: Redis,
    sub: str,
    *,
    family_id: str | None = None,
    now: int | None = None,
) -> tuple[str, RefreshHandle]:
    """Issue a refresh token and write family state to Redis.

    Pass family_id=None (default) to start a new family. Pass an existing family_id to
    re-seat it (used by rotate_refresh_token via the shared _REFRESH_REDIS_PREFIX key).
    """
    if not sub:
        raise ValueError("issue_refresh_token: sub must be non-empty")

    family_id = family_id or uuid.uuid4().hex
    token_id = uuid.uuid4().hex
    now_ts = now if now is not None else int(time.time())
    key = f"{_REFRESH_REDIS_PREFIX}{family_id}"

    await redis.hset(  # type: ignore[misc]
        key,
        mapping={"current_token_id": token_id, "sub": sub, "revoked": "0"},
    )
    await redis.expire(key, JWT_REFRESH_TTL_SECONDS)

    token = _sign_refresh(family_id, token_id)
    return token, RefreshHandle(
        family_id=family_id,
        token_id=token_id,
        sub=sub,
        issued_at=now_ts,
        expires_at=now_ts + JWT_REFRESH_TTL_SECONDS,
    )


async def verify_refresh_token(redis: Redis, token: str) -> RefreshHandle:
    """Verify HMAC, family existence, not-revoked, and current_token_id match.

    On replay (stale token_id), revokes the entire family and raises RefreshTokenReplayDetected.
    """
    family_id, token_id, provided_mac = _parse_refresh(token)
    _verify_refresh_hmac(family_id, token_id, provided_mac)

    key = f"{_REFRESH_REDIS_PREFIX}{family_id}"
    data = await redis.hgetall(key)  # type: ignore[misc]
    if not data:
        raise InvalidRefreshToken("refresh token family not found or expired")
    if data.get("revoked") == "1":
        raise InvalidRefreshToken("refresh token family is revoked")

    current_token_id = data.get("current_token_id")
    if current_token_id != token_id:
        await redis.hset(key, "revoked", "1")  # type: ignore[misc]
        log.warning(
            "Refresh token replay detected — family=%s revoked (provided=%s, current=%s)",
            family_id,
            token_id,
            current_token_id,
        )
        raise RefreshTokenReplayDetected("refresh token replay detected; family revoked")

    ttl = await redis.ttl(key)
    now_ts = int(time.time())
    expires_at = now_ts + max(0, int(ttl))
    issued_at = expires_at - JWT_REFRESH_TTL_SECONDS
    return RefreshHandle(
        family_id=family_id,
        token_id=token_id,
        sub=str(data.get("sub", "")),
        issued_at=issued_at,
        expires_at=expires_at,
    )


async def rotate_refresh_token(redis: Redis, old_token: str) -> tuple[str, RefreshHandle]:
    """Verify the old token, mint a new token_id in the same family, preserve family TTL.

    Uses a WATCH/MULTI/EXEC transaction on the family key so the current_token_id
    check-and-swap is atomic against concurrent rotates with the same old_token.

    Race-and-replay contract: if two concurrent requests present the same valid
    old_token, exactly one succeeds and the other observes WatchError (someone
    else wrote the key between WATCH and EXEC). The loser is, by the
    refresh-rotation threat model, a replay — possibly an attacker who intercepted
    the token — so the family is revoked and RefreshTokenReplayDetected is raised.
    """
    family_id, token_id, provided_mac = _parse_refresh(old_token)
    _verify_refresh_hmac(family_id, token_id, provided_mac)

    key = f"{_REFRESH_REDIS_PREFIX}{family_id}"
    new_token_id = uuid.uuid4().hex

    async with redis.pipeline(transaction=True) as pipe:
        try:
            await pipe.watch(key)
            data = await pipe.hgetall(key)  # type: ignore[misc]
            if not data:
                await pipe.unwatch()
                raise InvalidRefreshToken("refresh token family not found or expired")
            if data.get("revoked") == "1":
                await pipe.unwatch()
                raise InvalidRefreshToken("refresh token family is revoked")

            current_token_id = data.get("current_token_id")
            if current_token_id != token_id:
                # Stale token_id while family is still live == classic replay.
                # Revoke atomically inside the transaction.
                pipe.multi()
                pipe.hset(key, "revoked", "1")
                await pipe.execute()
                log.warning(
                    "Refresh token replay detected — family=%s revoked "
                    "(provided=%s, current=%s)",
                    family_id,
                    token_id,
                    current_token_id,
                )
                raise RefreshTokenReplayDetected("refresh token replay detected; family revoked")

            ttl = await pipe.ttl(key)

            # Atomic CAS: if anyone else writes `key` between WATCH and EXEC, the
            # EXEC raises WatchError and we fall into the concurrent-rotate branch.
            pipe.multi()
            pipe.hset(key, "current_token_id", new_token_id)
            await pipe.execute()
        except WatchError:
            # Lost the race against another concurrent rotate on the same old_token
            # → by contract this is a replay; revoke the family and raise.
            # The revocation happens outside the (failed) transaction but is
            # idempotent (SET of "revoked" to "1").
            await redis.hset(key, "revoked", "1")  # type: ignore[misc]
            log.warning(
                "Refresh token replay detected via WATCH conflict — family=%s revoked",
                family_id,
            )
            raise RefreshTokenReplayDetected(
                "refresh token replay detected; family revoked"
            ) from None

    new_token = _sign_refresh(family_id, new_token_id)
    now_ts = int(time.time())
    expires_at = now_ts + max(0, int(ttl))
    return new_token, RefreshHandle(
        family_id=family_id,
        token_id=new_token_id,
        sub=str(data.get("sub", "")),
        issued_at=now_ts,
        expires_at=expires_at,
    )


async def revoke_refresh_family(redis: Redis, family_id: str) -> None:
    """Mark an entire refresh token family as revoked. Idempotent."""
    key = f"{_REFRESH_REDIS_PREFIX}{family_id}"
    await redis.hset(key, "revoked", "1")  # type: ignore[misc]


async def revoke_refresh_token(redis: Redis, token: str) -> None:
    """Revoke the family backing a given refresh token string.

    Used by the logout path. Idempotent: silently succeeds on empty or malformed
    tokens so callers can invoke this unconditionally without branching.
    """
    if not token:
        return
    try:
        family_id, _, _ = _parse_refresh(token)
    except InvalidRefreshToken:
        return
    await revoke_refresh_family(redis, family_id)
