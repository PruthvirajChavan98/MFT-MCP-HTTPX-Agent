from __future__ import annotations

import pytest

import src.agent_service.api.endpoints.sessions as sessions_module
from src.agent_service.api.endpoints.sessions import get_session_config, initialize_session


@pytest.fixture(autouse=True)
def _stub_default_prompt(monkeypatch):
    monkeypatch.setattr(
        sessions_module.prompt_manager,
        "get_default_system_prompt",
        lambda: "You are helpful.",
    )


@pytest.mark.asyncio
async def test_initialize_session_uses_explicit_groq_default_pair(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_set_config(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(sessions_module.uuid_utils, "uuid7", lambda: "sid-default")
    monkeypatch.setattr(sessions_module, "DEFAULT_CHAT_PROVIDER", "groq")
    monkeypatch.setattr(sessions_module, "DEFAULT_CHAT_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setattr(sessions_module.config_manager, "set_config", fake_set_config)

    response = await initialize_session()

    assert response.session_id == "sid-default"
    assert response.provider == "groq"
    assert response.model_name == "openai/gpt-oss-120b"
    assert captured["provider"] == "groq"
    assert captured["model_name"] == "openai/gpt-oss-120b"


@pytest.mark.asyncio
async def test_get_session_config_falls_back_to_explicit_default_pair(monkeypatch):
    async def fake_get_config(_session_id: str):
        return {}

    monkeypatch.setattr(sessions_module.session_utils, "validate_session_id", lambda value: value)
    monkeypatch.setattr(sessions_module, "DEFAULT_CHAT_PROVIDER", "groq")
    monkeypatch.setattr(sessions_module, "DEFAULT_CHAT_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setattr(sessions_module.config_manager, "get_config", fake_get_config)

    response = await get_session_config("sid-default")

    assert response["session_id"] == "sid-default"
    assert response["provider"] == "groq"
    assert response["model_name"] == "openai/gpt-oss-120b"


@pytest.mark.asyncio
async def test_get_session_config_inferrs_provider_for_legacy_saved_model(monkeypatch):
    async def fake_get_config(_session_id: str):
        return {"model_name": "openai/o3-mini"}

    monkeypatch.setattr(sessions_module.session_utils, "validate_session_id", lambda value: value)
    monkeypatch.setattr(sessions_module, "DEFAULT_CHAT_PROVIDER", "groq")
    monkeypatch.setattr(sessions_module, "DEFAULT_CHAT_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setattr(sessions_module.config_manager, "get_config", fake_get_config)

    response = await get_session_config("sid-legacy")

    assert response["provider"] == "openrouter"
    assert response["model_name"] == "openai/o3-mini"
