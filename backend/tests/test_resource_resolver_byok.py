from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.agent_service.core.resource_resolver as resolver_module
from src.agent_service.core.resource_resolver import ResourceResolver


async def _fake_rebuild_tools(*_args, **_kwargs):
    return []


@pytest.fixture(autouse=True)
def _stub_default_system_prompt(monkeypatch):
    monkeypatch.setattr(
        resolver_module.prompt_manager, "get_default_system_prompt", lambda: "You are helpful."
    )


@pytest.mark.asyncio
async def test_openrouter_provider_requires_session_key_even_when_env_key_exists(monkeypatch):
    async def fake_get_config(_session_id: str):
        return {"provider": "openrouter", "model_name": "openai/o3-mini"}

    monkeypatch.setattr(resolver_module.config_manager, "get_config", fake_get_config)
    monkeypatch.setattr(resolver_module, "OPENROUTER_API_KEY", "sk-or-env")

    with pytest.raises(
        ValueError, match="OpenRouter provider requires a session OpenRouter API key"
    ):
        await ResourceResolver.resolve_agent_resources("sid-openrouter", SimpleNamespace())


@pytest.mark.asyncio
async def test_nvidia_provider_requires_session_key_even_when_env_key_exists(monkeypatch):
    async def fake_get_config(_session_id: str):
        return {"provider": "nvidia", "model_name": "nvidia/meta/llama-3.1-70b-instruct"}

    monkeypatch.setattr(resolver_module.config_manager, "get_config", fake_get_config)

    with pytest.raises(ValueError, match="NVIDIA provider requires a session NVIDIA API key"):
        await ResourceResolver.resolve_agent_resources("sid-nvidia", SimpleNamespace())


@pytest.mark.asyncio
async def test_openrouter_provider_uses_saved_session_key_instead_of_env_fallback(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_get_config(_session_id: str):
        return {
            "provider": "openrouter",
            "model_name": "openai/o3-mini",
            "openrouter_api_key": "sk-or-session",
        }

    def fake_get_llm(**kwargs):
        captured.update(kwargs)
        return object(), "openrouter"

    monkeypatch.setattr(resolver_module.config_manager, "get_config", fake_get_config)
    monkeypatch.setattr(resolver_module, "OPENROUTER_API_KEY", "sk-or-env")
    monkeypatch.setattr(resolver_module, "get_llm", fake_get_llm)
    monkeypatch.setattr(resolver_module.mcp_manager, "rebuild_tools_for_user", _fake_rebuild_tools)

    resources = await ResourceResolver.resolve_agent_resources("sid-openrouter", SimpleNamespace())

    assert captured["openrouter_api_key"] == "sk-or-session"
    assert resources.openrouter_api_key == "sk-or-session"
    assert resources.provider == "openrouter"


@pytest.mark.asyncio
async def test_groq_provider_keeps_server_fallback_when_session_key_missing(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_get_config(_session_id: str):
        return {"provider": "groq", "model_name": "openai/gpt-oss-120b"}

    def fake_get_llm(**kwargs):
        captured.update(kwargs)
        return object(), "groq"

    monkeypatch.setattr(resolver_module.config_manager, "get_config", fake_get_config)
    monkeypatch.setattr(resolver_module, "OPENROUTER_API_KEY", "sk-or-owner")
    monkeypatch.setattr(resolver_module, "GROQ_API_KEYS", ["gsk-owner"])
    monkeypatch.setattr(resolver_module, "get_llm", fake_get_llm)
    monkeypatch.setattr(resolver_module.mcp_manager, "rebuild_tools_for_user", _fake_rebuild_tools)

    resources = await ResourceResolver.resolve_agent_resources("sid-groq", SimpleNamespace())

    assert captured["groq_api_key"] == "gsk-owner"
    assert resources.groq_api_key == "gsk-owner"
    assert resources.openrouter_api_key == "sk-or-owner"
    assert resources.provider == "groq"


@pytest.mark.asyncio
async def test_groq_fallback_rotates_across_multiple_keys(monkeypatch):
    """Multi-key fallback must distribute across keys, not pin to index 0."""
    from src.agent_service.llm import groq_rotator

    class _FakeRedis:
        def __init__(self) -> None:
            self._n = 0

        async def incr(self, _key: str) -> int:
            self._n += 1
            return self._n

        async def exists(self, _key: str) -> int:
            return 0

    redis = _FakeRedis()

    async def _fake_get_redis() -> _FakeRedis:
        return redis

    monkeypatch.setattr(groq_rotator, "get_redis", _fake_get_redis)

    async def fake_get_config(_session_id: str):
        return {"provider": "groq", "model_name": "openai/gpt-oss-120b"}

    keys_seen: list[str] = []

    def fake_get_llm(**kwargs):
        keys_seen.append(str(kwargs["groq_api_key"]))
        return object(), "groq"

    monkeypatch.setattr(resolver_module.config_manager, "get_config", fake_get_config)
    monkeypatch.setattr(resolver_module, "OPENROUTER_API_KEY", "sk-or-owner")
    monkeypatch.setattr(resolver_module, "GROQ_API_KEYS", ["gsk-a", "gsk-b", "gsk-c"])
    monkeypatch.setattr(groq_rotator, "GROQ_API_KEYS", ["gsk-a", "gsk-b", "gsk-c"])
    monkeypatch.setattr(resolver_module, "get_llm", fake_get_llm)
    monkeypatch.setattr(resolver_module.mcp_manager, "rebuild_tools_for_user", _fake_rebuild_tools)

    for _ in range(6):
        await ResourceResolver.resolve_agent_resources("sid-groq", SimpleNamespace())

    # 6 resolutions across 3 keys — each key should appear twice.
    from collections import Counter

    counts = Counter(keys_seen)
    assert dict(counts) == {"gsk-a": 2, "gsk-b": 2, "gsk-c": 2}


@pytest.mark.asyncio
async def test_missing_saved_config_uses_explicit_default_groq_pair(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_get_config(_session_id: str):
        return {}

    def fake_get_llm(**kwargs):
        captured.update(kwargs)
        return object(), "groq"

    monkeypatch.setattr(resolver_module.config_manager, "get_config", fake_get_config)
    monkeypatch.setattr(resolver_module, "DEFAULT_CHAT_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setattr(resolver_module, "DEFAULT_CHAT_PROVIDER", "groq")
    monkeypatch.setattr(resolver_module, "OPENROUTER_API_KEY", "sk-or-owner")
    monkeypatch.setattr(resolver_module, "GROQ_API_KEYS", ["gsk-owner"])
    monkeypatch.setattr(resolver_module, "get_llm", fake_get_llm)
    monkeypatch.setattr(resolver_module.mcp_manager, "rebuild_tools_for_user", _fake_rebuild_tools)

    resources = await ResourceResolver.resolve_agent_resources("sid-default", SimpleNamespace())

    assert captured["provider"] == "groq"
    assert captured["model_name"] == "openai/gpt-oss-120b"
    assert resources.provider == "groq"
    assert resources.model_name == "openai/gpt-oss-120b"
