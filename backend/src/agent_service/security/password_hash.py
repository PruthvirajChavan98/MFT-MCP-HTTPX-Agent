"""Argon2id password hashing for admin auth.

Thin wrapper over argon2-cffi's PasswordHasher, which defaults to the RFC 9106
low-memory profile (OWASP-aligned). Exposes hash/verify/needs_rehash and never
raises on malformed hashes — returns False instead so callers can treat any
verify failure uniformly as "invalid credentials".

Dormant at import time — the module-level PasswordHasher() instance initializes
lazily on first use by argon2-cffi internals.
"""

from __future__ import annotations

import logging
from typing import Final

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerificationError, VerifyMismatchError

log = logging.getLogger(__name__)

_hasher: Final[PasswordHasher] = PasswordHasher()

# Argon2id cost is bounded by input length: every caller that hashes a
# user-supplied password MUST cap length upstream, but the wrapper enforces
# an additional hard bound so the hasher cannot be made to do unbounded
# work even if a new caller forgets the Pydantic guard. 4096 bytes is
# generous for any legitimate passphrase — 1 KB scrypt-style attacks
# don't make Argon2 expensive enough to matter at this ceiling.
# (security review M1)
_MAX_PASSWORD_BYTES: Final[int] = 4096


def hash_password(plaintext: str) -> str:
    """Argon2id-hash a plaintext password. Returns the encoded hash string."""
    if not plaintext:
        raise ValueError("hash_password: plaintext must be non-empty")
    if len(plaintext.encode("utf-8")) > _MAX_PASSWORD_BYTES:
        raise ValueError(f"hash_password: plaintext exceeds {_MAX_PASSWORD_BYTES}-byte cap")
    return _hasher.hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    """Return True on match, False on mismatch or malformed hash. Never raises.

    Consumers treat False as "invalid credentials" without branching on the
    underlying reason. Logs a warning for malformed stored hashes so operators
    can spot corrupted config.
    """
    if not plaintext or not hashed:
        return False
    # Mirror hash_password's length cap so a caller that forwards an
    # unbounded attacker-controlled string into verify doesn't spend
    # unbounded Argon2 time. (security review M1)
    if len(plaintext.encode("utf-8")) > _MAX_PASSWORD_BYTES:
        return False
    try:
        return _hasher.verify(hashed, plaintext)
    except VerifyMismatchError:
        return False
    except VerificationError:
        return False
    except InvalidHash as e:
        log.warning("verify_password: InvalidHash (malformed stored hash): %s", e)
        return False


def needs_rehash(hashed: str) -> bool:
    """True if the stored hash was produced with weaker parameters than the current profile.

    Returns False on empty or malformed input so callers can use this for auto-rehash
    gating without extra error handling.
    """
    if not hashed:
        return False
    try:
        return _hasher.check_needs_rehash(hashed)
    except InvalidHash:
        return False
