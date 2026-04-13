from __future__ import annotations

from collections.abc import AsyncIterator

import pyotp
import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from fakeredis.aioredis import FakeRedis

from src.agent_service.security import admin_crypto
from src.agent_service.security.admin_totp import (
    _LOCKED_PREFIX,
    _LOCKOUT_PREFIX,
    TOTPInvalidCode,
    TOTPLockedOut,
    reset_lockout,
    verify_totp_code,
)

_TEST_SUB = "super_admin"


@pytest.fixture(autouse=True)
def _set_test_fernet(monkeypatch: pytest.MonkeyPatch) -> None:
    test_key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr(admin_crypto, "FERNET_MASTER_KEY", test_key)
    admin_crypto._reset_for_testing()


@pytest_asyncio.fixture
async def redis() -> AsyncIterator[FakeRedis]:
    client = FakeRedis(decode_responses=True)
    try:
        yield client
    finally:
        await client.flushall()
        await client.aclose()


@pytest.fixture
def totp_secret() -> str:
    return pyotp.random_base32()


@pytest.fixture
def encrypted_totp_secret(totp_secret: str) -> str:
    return admin_crypto.encrypt_secret(totp_secret)


@pytest.mark.asyncio
async def test_verify_totp_code_accepts_valid_code(
    redis: FakeRedis, totp_secret: str, encrypted_totp_secret: str
) -> None:
    code = pyotp.TOTP(totp_secret).now()
    await verify_totp_code(redis, _TEST_SUB, encrypted_totp_secret, code)
    # No exception = success


@pytest.mark.asyncio
async def test_verify_totp_code_rejects_invalid_code(
    redis: FakeRedis, encrypted_totp_secret: str
) -> None:
    with pytest.raises(TOTPInvalidCode):
        await verify_totp_code(redis, _TEST_SUB, encrypted_totp_secret, "000000")
    failures = await redis.hget(f"{_LOCKOUT_PREFIX}{_TEST_SUB}", "failures")
    assert failures == "1"


@pytest.mark.asyncio
async def test_verify_totp_code_clears_counter_on_success(
    redis: FakeRedis, totp_secret: str, encrypted_totp_secret: str
) -> None:
    # One failure
    with pytest.raises(TOTPInvalidCode):
        await verify_totp_code(redis, _TEST_SUB, encrypted_totp_secret, "000000")
    # Then success
    code = pyotp.TOTP(totp_secret).now()
    await verify_totp_code(redis, _TEST_SUB, encrypted_totp_secret, code)
    # Counter must be cleared
    assert await redis.exists(f"{_LOCKOUT_PREFIX}{_TEST_SUB}") == 0


@pytest.mark.asyncio
async def test_verify_totp_code_locks_after_5_failures(
    redis: FakeRedis, totp_secret: str, encrypted_totp_secret: str
) -> None:
    for _ in range(4):
        with pytest.raises(TOTPInvalidCode):
            await verify_totp_code(redis, _TEST_SUB, encrypted_totp_secret, "000000")
    # 5th failure triggers lockout
    with pytest.raises(TOTPLockedOut):
        await verify_totp_code(redis, _TEST_SUB, encrypted_totp_secret, "000000")
    # 6th attempt, even with a valid code, must be locked out
    valid_code = pyotp.TOTP(totp_secret).now()
    with pytest.raises(TOTPLockedOut):
        await verify_totp_code(redis, _TEST_SUB, encrypted_totp_secret, valid_code)


@pytest.mark.asyncio
async def test_verify_totp_code_locked_state_has_15_min_ttl(
    redis: FakeRedis, encrypted_totp_secret: str
) -> None:
    for _ in range(5):
        with pytest.raises((TOTPInvalidCode, TOTPLockedOut)):
            await verify_totp_code(redis, _TEST_SUB, encrypted_totp_secret, "000000")
    ttl = await redis.ttl(f"{_LOCKED_PREFIX}{_TEST_SUB}")
    assert 890 <= ttl <= 900  # 900 seconds = 15 min, allowing for test execution time


@pytest.mark.asyncio
async def test_verify_totp_code_short_circuits_on_existing_lock(
    redis: FakeRedis, totp_secret: str, encrypted_totp_secret: str
) -> None:
    # Manually set the lock marker
    await redis.set(f"{_LOCKED_PREFIX}{_TEST_SUB}", "1", ex=900)
    # Even a valid code must raise TOTPLockedOut
    valid_code = pyotp.TOTP(totp_secret).now()
    with pytest.raises(TOTPLockedOut):
        await verify_totp_code(redis, _TEST_SUB, encrypted_totp_secret, valid_code)


@pytest.mark.asyncio
async def test_verify_totp_code_empty_code_raises_invalid(
    redis: FakeRedis, encrypted_totp_secret: str
) -> None:
    with pytest.raises(TOTPInvalidCode):
        await verify_totp_code(redis, _TEST_SUB, encrypted_totp_secret, "")


@pytest.mark.asyncio
async def test_verify_totp_code_empty_sub_rejected(
    redis: FakeRedis, encrypted_totp_secret: str
) -> None:
    with pytest.raises(ValueError, match="sub must be non-empty"):
        await verify_totp_code(redis, "", encrypted_totp_secret, "123456")


@pytest.mark.asyncio
async def test_verify_totp_code_decrypt_failure_propagates(
    redis: FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Encrypt with one key, then rotate — decryption must fail
    encrypted = admin_crypto.encrypt_secret(pyotp.random_base32())
    new_key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr(admin_crypto, "FERNET_MASTER_KEY", new_key)
    admin_crypto._reset_for_testing()
    # Should raise InvalidToken (bubbles up from decrypt_secret)
    from cryptography.fernet import InvalidToken

    with pytest.raises(InvalidToken):
        await verify_totp_code(redis, _TEST_SUB, encrypted, "123456")


@pytest.mark.asyncio
async def test_reset_lockout_clears_both_keys(redis: FakeRedis) -> None:
    # Plant both keys manually
    await redis.hset(f"{_LOCKOUT_PREFIX}{_TEST_SUB}", "failures", "3")
    await redis.set(f"{_LOCKED_PREFIX}{_TEST_SUB}", "1", ex=900)
    await reset_lockout(redis, _TEST_SUB)
    assert await redis.exists(f"{_LOCKOUT_PREFIX}{_TEST_SUB}") == 0
    assert await redis.exists(f"{_LOCKED_PREFIX}{_TEST_SUB}") == 0
