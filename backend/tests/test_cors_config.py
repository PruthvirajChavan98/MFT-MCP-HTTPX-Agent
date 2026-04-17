from __future__ import annotations

import pytest
from fastapi import FastAPI

from src.agent_service.core.app_factory import AppFactory


class TestCorsConfiguration:
    """S-H2: Fail-closed CORS config — reject empty origins + wildcard with credentials."""

    def test_raises_on_empty_origins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "")
        with pytest.raises(RuntimeError, match="CORS_ALLOWED_ORIGINS resolved to an empty list"):
            AppFactory._configure_cors(FastAPI())

    def test_raises_on_whitespace_only_origins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "   ,  ,   ")
        with pytest.raises(RuntimeError, match="empty list"):
            AppFactory._configure_cors(FastAPI())

    def test_raises_on_wildcard_with_credentials(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")
        with pytest.raises(
            RuntimeError, match="'\\*' which is incompatible with allow_credentials"
        ):
            AppFactory._configure_cors(FastAPI())

    def test_accepts_explicit_origins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(
            "CORS_ALLOWED_ORIGINS",
            "https://mft-agent.pruthvirajchavan.codes,https://mft-api.pruthvirajchavan.codes",
        )
        app = FastAPI()
        # Should not raise
        AppFactory._configure_cors(app)
        # Two middlewares in user_middleware — sanity check one was added
        assert any("CORSMiddleware" in str(mw.cls) for mw in app.user_middleware)
