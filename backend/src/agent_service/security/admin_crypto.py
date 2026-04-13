"""Admin authentication crypto helpers: Fernet envelope for TOTP secrets + JWT secret validation.

Dormant module — fully lazy, no side effects at import time. Activated at first use when
ADMIN_AUTH_ENABLED flips to True in Phase 6.
"""

from __future__ import annotations

import logging
from typing import Final

from cryptography.fernet import Fernet, InvalidToken

from src.agent_service.core.config import FERNET_MASTER_KEY

log = logging.getLogger(__name__)

_MIN_JWT_SECRET_BYTES: Final[int] = 32  # RFC 7518 §3.2 for HS256 (see lessons.md L1)

_fernet_singleton: Fernet | None = None


class AdminCryptoConfigError(RuntimeError):
    """Raised when admin crypto is used but FERNET_MASTER_KEY is missing or malformed."""


def _get_fernet() -> Fernet:
    """Lazy-load and cache a Fernet instance from FERNET_MASTER_KEY.

    Raises AdminCryptoConfigError if the key is missing or malformed.
    """
    global _fernet_singleton
    if _fernet_singleton is not None:
        return _fernet_singleton
    if not FERNET_MASTER_KEY:
        raise AdminCryptoConfigError(
            "FERNET_MASTER_KEY is not set. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    try:
        _fernet_singleton = Fernet(FERNET_MASTER_KEY.encode("utf-8"))
    except ValueError as e:
        raise AdminCryptoConfigError(
            f"FERNET_MASTER_KEY is malformed (must be URL-safe base64 of exactly 32 bytes): {e}"
        ) from e
    return _fernet_singleton


def encrypt_secret(plaintext: str) -> str:
    """Fernet-encrypt a secret. Returns a URL-safe base64 string.

    Raises ValueError on empty input; AdminCryptoConfigError on missing/malformed master key.
    """
    if not plaintext:
        raise ValueError("encrypt_secret: plaintext must be non-empty")
    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    """Fernet-decrypt a secret previously produced by encrypt_secret().

    Raises ValueError on empty input; AdminCryptoConfigError on missing/malformed master key;
    cryptography.fernet.InvalidToken if the ciphertext is tampered or was encrypted with a
    different master key.
    """
    if not ciphertext:
        raise ValueError("decrypt_secret: ciphertext must be non-empty")
    fernet = _get_fernet()
    try:
        return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        log.warning("decrypt_secret: InvalidToken (wrong key or tampered ciphertext)")
        raise


def validate_jwt_secret(secret: str | None) -> None:
    """Raise ValueError if the JWT secret is missing or shorter than 32 bytes.

    Called by config.py at import time when ADMIN_AUTH_ENABLED=True, and by
    admin_jwt.py (Phase 2) before every issue/verify operation.
    """
    if not secret:
        raise ValueError("JWT_SECRET is required when ADMIN_AUTH_ENABLED=True")
    if len(secret.encode("utf-8")) < _MIN_JWT_SECRET_BYTES:
        raise ValueError(
            f"JWT_SECRET must be >={_MIN_JWT_SECRET_BYTES} bytes "
            f"(RFC 7518 §3.2 for HS256); got {len(secret.encode('utf-8'))} bytes"
        )


def generate_fernet_key() -> str:
    """Helper for operators enrolling a new FERNET_MASTER_KEY. Returns URL-safe base64 string."""
    return Fernet.generate_key().decode("utf-8")


def _reset_for_testing() -> None:
    """Test-only helper — clears the Fernet singleton so tests can rebuild with a fresh key."""
    global _fernet_singleton
    _fernet_singleton = None
