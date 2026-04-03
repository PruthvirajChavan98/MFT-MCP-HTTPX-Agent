from __future__ import annotations

from src.agent_service.llm.capabilities import decorate_model_name, infer_model_capabilities
from src.agent_service.llm.catalog import ModelService


def test_infer_model_capabilities_marks_reasoning_and_tools_for_openrouter_reasoning_family():
    caps = infer_model_capabilities(
        model_id="openai/o3-mini",
        provider="openrouter",
        supported_parameters=["stream", "tools"],
    )

    assert caps["is_reasoning_model"] is True
    assert caps["supports_reasoning_effort"] is True
    assert caps["supports_tools"] is True
    assert decorate_model_name("OpenAI o3-mini", caps).startswith("🧠🛠️ ")


def test_groq_fallback_catalog_entries_include_capability_metadata():
    service = ModelService()

    models = service._hydrate_fallback("groq")
    target = next(model for model in models if model["id"] == "groq/deepseek-r1-distill-llama-70b")

    assert target["is_reasoning_model"] is True
    assert target["supports_reasoning_effort"] is True
    assert target["supports_tools"] is True
    assert target["display_name"].startswith("🧠🛠️ ")
