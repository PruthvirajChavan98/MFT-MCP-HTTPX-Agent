from __future__ import annotations

from typing import Any, Dict

import src.agent_service.llm.client as llm_client


def test_get_llm_prefers_chatopenrouter_when_available(monkeypatch):
    captured: Dict[str, Any] = {}

    class FakeChatOpenRouter:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    def fail_init_chat_model(*args, **kwargs):
        raise AssertionError("init_chat_model should not be called when ChatOpenRouter is present")

    monkeypatch.setattr(llm_client, "ChatOpenRouter", FakeChatOpenRouter)
    monkeypatch.setattr(llm_client, "init_chat_model", fail_init_chat_model)

    llm = llm_client.get_llm(
        model_name="z-ai/glm-5",
        provider="openrouter",
        openrouter_api_key="sk-or-test",
        reasoning_effort="high",
        temperature=0.15,
        max_tokens=128,
    )

    assert isinstance(llm, FakeChatOpenRouter)
    assert captured["model"] == "z-ai/glm-5"
    assert captured["api_key"] == "sk-or-test"
    assert captured["temperature"] == 0.15
    assert captured["max_tokens"] == 128
    assert captured["reasoning"] == {"effort": "high"}


def test_get_llm_openrouter_falls_back_to_openai_adapter(monkeypatch):
    captured: Dict[str, Any] = {}

    def fake_init_chat_model(*, model, model_provider, api_key, **kwargs):
        captured["model"] = model
        captured["model_provider"] = model_provider
        captured["api_key"] = api_key
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(llm_client, "ChatOpenRouter", None)
    monkeypatch.setattr(llm_client, "init_chat_model", fake_init_chat_model)

    llm = llm_client.get_llm(
        model_name="z-ai/glm-5",
        provider="openrouter",
        openrouter_api_key="sk-or-test",
        reasoning_effort="high",
    )

    assert llm is not None
    assert captured["model"] == "z-ai/glm-5"
    assert captured["model_provider"] == "openai"
    assert captured["api_key"] == "sk-or-test"
    assert captured["kwargs"]["base_url"] == "https://openrouter.ai/api/v1"
    assert captured["kwargs"]["model_kwargs"]["reasoning"]["effort"] == "high"


def test_get_llm_retains_reasoning_effort_for_non_openai_providers(monkeypatch):
    captured: Dict[str, Any] = {}

    def fake_init_chat_model(*, model, model_provider, api_key, **kwargs):
        captured["model"] = model
        captured["model_provider"] = model_provider
        captured["api_key"] = api_key
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(llm_client, "init_chat_model", fake_init_chat_model)

    llm = llm_client.get_llm(
        model_name="openai/gpt-oss-120b",
        provider="groq",
        groq_api_key="gsk_test",
        reasoning_effort="high",
    )

    assert llm is not None
    assert captured["model_provider"] == "groq"
    assert captured["kwargs"]["reasoning_effort"] == "high"
