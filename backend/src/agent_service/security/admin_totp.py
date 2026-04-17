"""TOTP code verification with Redis-backed lockout tracking.

Lockout schema (two Redis keys per admin sub):
- admin_auth:lockout:<sub>  — hash {failures: int}, 5-min sliding TTL (resets on success)
- admin_auth:locked:<sub>   — marker "1", 15-min fixed TTL (absolute lockout)

Flow on each verify call:
1. Check locked marker first — if present, raise TOTPLockedOut WITHOUT checking the code
2. Decrypt the Fernet-encrypted TOTP secret (raises on missing/malformed master key
   or tampered ciphertext — callers must handle)
3. Verify the 6-digit TOTP code with valid_window=1 (accepts ±30 sec clock skew)
4. On success: clear both Redis keys
5. On failure: INCR failures; if >=5, set locked marker + raise TOTPLockedOut

Dormant module — no side effects at import time.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

import pyotp
from redis.exceptions import WatchError

from src.agent_service.security.admin_crypto import decrypt_secret

if TYPE_CHECKING:
    from redis.asyncio import Redis

log = logging.getLogger(__name__)

_LOCKOUT_PREFIX: Final[str] = "admin_auth:lockout:"
_LOCKED_PREFIX: Final[str] = "admin_auth:locked:"
_MAX_FAILURES: Final[int] = 5
_COUNTER_TTL_SECONDS: Final[int] = 300  # 5-min sliding window for consecutive failures
_LOCKOUT_TTL_SECONDS: Final[int] = 900  # 15-min absolute lockout


class TOTPLockedOut(Exception):
    """Raised when the admin is currently locked out due to prior failures."""


class TOTPInvalidCode(Exception):
    """Raised when the TOTP code does not match the expected value."""


async def verify_totp_code(
    redis: Redis,
    sub: str,
    encrypted_secret: str,
    code: str,
) -> None:
    """Verify a TOTP code. Raises TOTPLockedOut or TOTPInvalidCode on failure.

    Success: no exception; returns None. Both Redis counter keys are cleared.
    """
    if not sub:
        raise ValueError("verify_totp_code: sub must be non-empty")
    if not code:
        raise TOTPInvalidCode("TOTP code is empty")

    locked_key = f"{_LOCKED_PREFIX}{sub}"
    if await redis.exists(locked_key):
        raise TOTPLockedOut("account locked due to failed MFA attempts")

    # Decrypt the Fernet-encrypted secret (propagates InvalidToken / AdminCryptoConfigError)
    secret = decrypt_secret(encrypted_secret)
    totp = pyotp.TOTP(secret)

    if totp.verify(code, valid_window=1):
        await redis.delete(f"{_LOCKOUT_PREFIX}{sub}")
        await redis.delete(locked_key)
        return

    counter_key = f"{_LOCKOUT_PREFIX}{sub}"

    # Atomic check-and-increment (review finding #6 — TOTP lockout race).
    #
    # The increment must be guarded against a burst of concurrent failed attempts
    # landing between the EXISTS check above and the SET below. Without a guard, an
    # attacker sending N parallel requests before any one completes can pile up N
    # failures before the locked_key is written, defeating the 5-strike policy.
    #
    # WATCH locked_key: if ANY coroutine writes locked_key between WATCH and EXEC,
    # our pipeline aborts with WatchError and we fall into the "already locked"
    # branch. HINCRBY itself is atomic; this WATCH adds the additional guarantee
    # that we never INCR past the lock-transition boundary.
    try:
        async with redis.pipeline(transaction=True) as pipe:
            await pipe.watch(locked_key)
            # Re-check under WATCH — EXISTS above was before WATCH, so a concurrent
            # SET could have landed in-between.
            if await pipe.exists(locked_key):  # type: ignore[misc]
                await pipe.unwatch()
                raise TOTPLockedOut("account locked due to failed MFA attempts")

            pipe.multi()
            pipe.hincrby(counter_key, "failures", 1)
            pipe.expire(counter_key, _COUNTER_TTL_SECONDS)
            results = await pipe.execute()  # raises WatchError if locked_key changed
            failures = int(results[0])
    except WatchError as e:
        # A concurrent failed attempt triggered lockout between our WATCH and EXEC.
        raise TOTPLockedOut("account locked due to failed MFA attempts") from e

    if failures >= _MAX_FAILURES:
        await redis.set(locked_key, "1", ex=_LOCKOUT_TTL_SECONDS)
        log.warning("TOTP lockout triggered for sub=%s after %d failures", sub, failures)
        raise TOTPLockedOut("account locked due to failed MFA attempts")

    raise TOTPInvalidCode("invalid TOTP code")


async def reset_lockout(redis: Redis, sub: str) -> None:
    """Manually clear lockout state. Used by enrollment / admin-recovery flows."""
    await redis.delete(f"{_LOCKOUT_PREFIX}{sub}")
    await redis.delete(f"{_LOCKED_PREFIX}{sub}")
