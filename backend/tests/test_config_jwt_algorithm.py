"""Tests for the JWT_ALGORITHM allowlist guard in core.config.

The allowlist runs at module import time (NOT inside _validate_admin_auth_config,
which is bypassed in pytest contexts). It blocks the classic 'alg=none' bypass
and prevents algorithm-confusion when an operator misconfigures the env to an
asymmetric algorithm while the secret remains an HMAC string.

Tests use importlib.reload + monkeypatch.setenv to exercise the import-time check.
"""

from __future__ import annotations

import importlib
import sys

import pytest


def _reload_config(monkeypatch: pytest.MonkeyPatch, algorithm: str | None) -> object:
    """Reload core.config with JWT_ALGORITHM set (or unset) in the env."""
    if algorithm is None:
        monkeypatch.delenv("JWT_ALGORITHM", raising=False)
    else:
        monkeypatch.setenv("JWT_ALGORITHM", algorithm)
    sys.modules.pop("src.agent_service.core.config", None)
    return importlib.import_module("src.agent_service.core.config")


def test_default_unset_resolves_to_hs256(monkeypatch: pytest.MonkeyPatch) -> None:
    """No env var set → config falls back to HS256 (allowed)."""
    config = _reload_config(monkeypatch, None)
    assert config.JWT_ALGORITHM == "HS256"  # type: ignore[attr-defined]


def test_hs256_explicit_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _reload_config(monkeypatch, "HS256")
    assert config.JWT_ALGORITHM == "HS256"  # type: ignore[attr-defined]


def test_hs384_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _reload_config(monkeypatch, "HS384")
    assert config.JWT_ALGORITHM == "HS384"  # type: ignore[attr-defined]


def test_hs512_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _reload_config(monkeypatch, "HS512")
    assert config.JWT_ALGORITHM == "HS512"  # type: ignore[attr-defined]


def test_none_rejected_at_import(monkeypatch: pytest.MonkeyPatch) -> None:
    """alg=none bypass — must raise at module load before any handler can use it."""
    with pytest.raises(ValueError, match="JWT_ALGORITHM"):
        _reload_config(monkeypatch, "none")


def test_rs256_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Asymmetric algorithms require a JWKS path that this service does not implement."""
    with pytest.raises(ValueError, match="not in the allowed set"):
        _reload_config(monkeypatch, "RS256")


def test_es256_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="not in the allowed set"):
        _reload_config(monkeypatch, "ES256")


def test_empty_string_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty after .strip() → not 'HS256'/'HS384'/'HS512' → reject."""
    with pytest.raises(ValueError, match="JWT_ALGORITHM"):
        _reload_config(monkeypatch, "")


def test_lowercase_hs256_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Allowlist is case-sensitive — operator typos fail closed."""
    with pytest.raises(ValueError, match="not in the allowed set"):
        _reload_config(monkeypatch, "hs256")


def test_whitespace_padded_value_handled(monkeypatch: pytest.MonkeyPatch) -> None:
    """The .strip() in config.py is the only normalization — leading/trailing spaces ok."""
    config = _reload_config(monkeypatch, "  HS256  ")
    assert config.JWT_ALGORITHM == "HS256"  # type: ignore[attr-defined]
