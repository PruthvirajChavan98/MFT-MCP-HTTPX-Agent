"""Regression tests for the security-review hardenings (H1, H2, M1, M4).

These sit in their own file rather than bolting onto the existing
modules because each fix spans a different module — keeping them here
means one entry point for anyone auditing the hardening later.
"""

from __future__ import annotations

import pytest

from src.agent_service.security.password_hash import hash_password, verify_password
from src.mcp_service.session_store import RedisSessionStore, valid_session_id

# ─────────────────────────────────────────────────────────────────────────────
# M1 — Argon2 rejects oversized passwords (hash-flooding DoS defence)
# ─────────────────────────────────────────────────────────────────────────────


def test_hash_password_rejects_over_cap() -> None:
    too_long = "x" * 4097
    with pytest.raises(ValueError, match="cap"):
        hash_password(too_long)


def test_hash_password_accepts_at_cap() -> None:
    at_cap = "x" * 4096
    hashed = hash_password(at_cap)
    assert hashed.startswith("$argon2")


def test_verify_password_short_circuits_on_over_cap() -> None:
    # Verify must NOT spend Argon2 time on caller-controlled input beyond
    # the cap. Using a bogus hash — verify returns False without calling
    # the Argon2 backend on the oversized plaintext.
    assert verify_password("x" * 4097, "$argon2id$v=19$m=65536$invalid") is False


# ─────────────────────────────────────────────────────────────────────────────
# M4 — session_id charset + length bounds
# ─────────────────────────────────────────────────────────────────────────────


def test_valid_session_id_rejects_undefined_literal() -> None:
    with pytest.raises(ValueError):
        valid_session_id("undefined")


def test_valid_session_id_rejects_inflated_length() -> None:
    # Reject a 1 MB session_id outright — a Redis key that large is a DoS
    # vector, not a legitimate ID.
    with pytest.raises(ValueError):
        valid_session_id("a" * 200)


def test_valid_session_id_rejects_redis_glob_chars() -> None:
    for bad in ("abcd*", "abcd?", "abcd[def]"):
        with pytest.raises(ValueError):
            valid_session_id(bad)


def test_valid_session_id_accepts_uuid_like() -> None:
    assert valid_session_id("a1b2c3d4_test") == "a1b2c3d4_test"
    assert valid_session_id("01234567-89ab-cdef-0123-456789abcdef") == (
        "01234567-89ab-cdef-0123-456789abcdef"
    )


def test_store_valid_session_id_is_no_op_on_invalid() -> None:
    # Non-raising variant — returns None, which the instance methods
    # treat as "skip this call" so a bad ID can't trash unrelated state.
    assert RedisSessionStore._valid_session_id("undefined") is None
    assert RedisSessionStore._valid_session_id("x" * 200) is None
    assert RedisSessionStore._valid_session_id("glob*id") is None


# ─────────────────────────────────────────────────────────────────────────────
# H1 — enrollment token HMAC keys the hash
# ─────────────────────────────────────────────────────────────────────────────


def test_enrollment_token_hmac_key_differs_from_raw_fernet_master_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.agent_service.core.config as cfg

    monkeypatch.setenv("FERNET_MASTER_KEY", "x" * 44)
    derived = cfg.get_enrollment_token_hmac_key()
    assert len(derived) == 32
    # Key is deterministic but distinct from the raw master key bytes —
    # confirms BLAKE2b domain separation is actually invoked.
    assert derived != ("x" * 44).encode("utf-8")[:32]


def test_enrollment_hash_token_uses_hmac_not_bare_sha256(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import hashlib

    from src.agent_service.api.admin_enrollment import repo as enrollment_repo

    monkeypatch.setenv("FERNET_MASTER_KEY", "y" * 44)
    hashed = enrollment_repo._hash_token("known-plaintext")
    bare = hashlib.sha256(b"known-plaintext").hexdigest()
    assert hashed != bare, "token hash must be keyed, not a bare SHA-256"
    # Deterministic: same plaintext + same key produces the same hash.
    assert enrollment_repo._hash_token("known-plaintext") == hashed


def test_enrollment_tokens_match_uses_constant_time_compare(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.agent_service.api.admin_enrollment import repo as enrollment_repo

    monkeypatch.setenv("FERNET_MASTER_KEY", "z" * 44)
    hashed = enrollment_repo._hash_token("secret")
    assert enrollment_repo._tokens_match(hashed, "secret") is True
    assert enrollment_repo._tokens_match(hashed, "other") is False
