from __future__ import annotations

import pytest

from src.agent_service.security.password_hash import (
    hash_password,
    needs_rehash,
    verify_password,
)


def test_hash_password_produces_argon2id_prefix() -> None:
    hashed = hash_password("correct-horse-battery-staple")
    assert hashed.startswith("$argon2id$")


def test_hash_password_rejects_empty_plaintext() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        hash_password("")


def test_hash_password_produces_different_hashes_for_same_input() -> None:
    # Random salt → same plaintext must produce different hashes
    h1 = hash_password("same-password")
    h2 = hash_password("same-password")
    assert h1 != h2
    # Both must still verify against the plaintext
    assert verify_password("same-password", h1) is True
    assert verify_password("same-password", h2) is True


def test_verify_password_accepts_correct_password() -> None:
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", hashed) is True


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("correct-horse-battery-staple")
    assert verify_password("wrong-password", hashed) is False


def test_verify_password_returns_false_on_empty_plaintext() -> None:
    hashed = hash_password("real-password")
    assert verify_password("", hashed) is False  # must not raise


def test_verify_password_returns_false_on_malformed_hash() -> None:
    assert verify_password("any-password", "not-a-valid-argon2-hash") is False


def test_verify_password_returns_false_on_empty_hash() -> None:
    assert verify_password("any-password", "") is False


def test_needs_rehash_returns_false_for_fresh_hash() -> None:
    hashed = hash_password("fresh-password")
    assert needs_rehash(hashed) is False


def test_needs_rehash_returns_false_on_malformed_hash() -> None:
    assert needs_rehash("not-a-valid-argon2-hash") is False


def test_needs_rehash_returns_false_on_empty_hash() -> None:
    assert needs_rehash("") is False
