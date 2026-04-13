from __future__ import annotations

import secrets as stdsecrets

import pytest
from cryptography.fernet import Fernet, InvalidToken

from src.agent_service.security import admin_crypto
from src.agent_service.security.admin_crypto import (
    AdminCryptoConfigError,
    decrypt_secret,
    encrypt_secret,
    generate_fernet_key,
    validate_jwt_secret,
)


@pytest.fixture(autouse=True)
def _reset_fernet_singleton(monkeypatch: pytest.MonkeyPatch):
    """Every test starts with a fresh Fernet singleton bound to a test master key."""
    test_key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr(admin_crypto, "FERNET_MASTER_KEY", test_key)
    admin_crypto._reset_for_testing()
    yield
    admin_crypto._reset_for_testing()


# ─────────── encrypt_secret / decrypt_secret round-trips ───────────


def test_round_trip_returns_original_plaintext() -> None:
    plaintext = "JBSWY3DPEHPK3PXP"  # shape of a base32 TOTP secret
    ciphertext = encrypt_secret(plaintext)
    assert ciphertext != plaintext
    assert decrypt_secret(ciphertext) == plaintext


def test_round_trip_handles_high_entropy_input() -> None:
    # Use stdlib-generated base32 so the test has no cross-phase dep on pyotp.
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    plaintext = "".join(stdsecrets.choice(alphabet) for _ in range(32))
    assert decrypt_secret(encrypt_secret(plaintext)) == plaintext


def test_encrypt_secret_rejects_empty_plaintext() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        encrypt_secret("")


def test_decrypt_secret_rejects_empty_ciphertext() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        decrypt_secret("")


def test_decrypt_secret_rejects_tampered_ciphertext() -> None:
    ciphertext = encrypt_secret("original-totp-secret")
    tampered = ciphertext[:-4] + "XXXX"
    with pytest.raises(InvalidToken):
        decrypt_secret(tampered)


def test_decrypt_secret_rejects_wrong_master_key(monkeypatch: pytest.MonkeyPatch) -> None:
    original = encrypt_secret("secret-totp-value")
    new_key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr(admin_crypto, "FERNET_MASTER_KEY", new_key)
    admin_crypto._reset_for_testing()
    with pytest.raises(InvalidToken):
        decrypt_secret(original)


# ─────────── _get_fernet configuration errors ───────────


def test_missing_fernet_master_key_raises_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_crypto, "FERNET_MASTER_KEY", None)
    admin_crypto._reset_for_testing()
    with pytest.raises(AdminCryptoConfigError, match="FERNET_MASTER_KEY is not set"):
        encrypt_secret("anything")


def test_malformed_fernet_master_key_raises_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_crypto, "FERNET_MASTER_KEY", "not-a-valid-fernet-key")
    admin_crypto._reset_for_testing()
    with pytest.raises(AdminCryptoConfigError, match="malformed"):
        encrypt_secret("anything")


# ─────────── validate_jwt_secret ───────────


def test_validate_jwt_secret_accepts_32_byte_secret() -> None:
    validate_jwt_secret("x" * 32)


def test_validate_jwt_secret_accepts_longer_secret() -> None:
    validate_jwt_secret(stdsecrets.token_urlsafe(32))


def test_validate_jwt_secret_rejects_short_secret() -> None:
    with pytest.raises(ValueError, match="must be >=32 bytes"):
        validate_jwt_secret("x" * 31)


def test_validate_jwt_secret_rejects_empty_secret() -> None:
    with pytest.raises(ValueError, match="required"):
        validate_jwt_secret("")


def test_validate_jwt_secret_rejects_none() -> None:
    with pytest.raises(ValueError, match="required"):
        validate_jwt_secret(None)


# ─────────── generate_fernet_key ───────────


def test_generate_fernet_key_produces_usable_key(monkeypatch: pytest.MonkeyPatch) -> None:
    new_key = generate_fernet_key()
    monkeypatch.setattr(admin_crypto, "FERNET_MASTER_KEY", new_key)
    admin_crypto._reset_for_testing()
    assert decrypt_secret(encrypt_secret("value")) == "value"
