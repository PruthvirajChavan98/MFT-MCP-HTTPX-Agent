import numpy as np
import pytest

from src.agent_service.features.routing.answerability import (
    QueryAnswerabilityClassifier,
    _answerability_decision,
)
from src.agent_service.features.routing.nbfc_router import NBFCClassifierService


class _Tool:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description


def test_answerability_decision_prefers_higher_confidence_path():
    label, path = _answerability_decision(
        kb_answerable=True,
        kb_score=0.81,
        mcp_answerable=True,
        mcp_score=0.62,
        margin=0.04,
        has_any_tools=True,
    )
    assert label == "kb_answerable"
    assert path == "kb"


@pytest.mark.asyncio
async def test_answerability_mcp_lexical_classification():
    classifier = QueryAnswerabilityClassifier(
        mcp_threshold=0.2,
        kb_threshold=0.8,
        kb_heuristic_threshold=0.8,
    )
    tools = [
        _Tool("validate_otp", "Validate OTP and login state for an active session."),
        _Tool("mock_fintech_knowledge_base", "Search FAQs database."),
    ]
    out = await classifier.classify("I need OTP validation for login", tools, api_key=None)
    assert out["mcp"]["answerable"] is True
    assert out["mcp"]["best_tool"] == "validate_otp"
    assert out["label"] in {"mcp_answerable", "kb_and_mcp_answerable"}


@pytest.mark.asyncio
async def test_answerability_kb_heuristic_without_vector():
    classifier = QueryAnswerabilityClassifier(
        kb_threshold=0.9,
        kb_heuristic_threshold=0.35,
        mcp_threshold=0.9,
    )
    tools = [_Tool("mock_fintech_knowledge_base", "Search FAQs database.")]
    out = await classifier.classify(
        "Need EMI statement and foreclosure details", tools, api_key=None
    )
    assert out["kb"]["available"] is True
    assert out["kb"]["method"] == "heuristic"
    assert out["kb"]["answerable"] is True
    assert out["label"] == "kb_answerable"


@pytest.mark.asyncio
async def test_nbfc_classifier_includes_answerability_in_responses(monkeypatch):
    service = NBFCClassifierService()

    async def fake_classify_with_query_vector(_text, _api_key):
        return (
            {
                "sentiment": {"label": "neutral", "score": 0.9},
                "reason": None,
                "backend": "embeddings",
            },
            np.asarray([0.1, 0.2, 0.3], dtype=np.float32),
        )

    async def fake_answerability(_text, *, tools, openrouter_api_key, query_vector=None):
        assert tools is not None
        assert openrouter_api_key == "sk-or-test"
        assert query_vector is not None
        return {
            "label": "mcp_answerable",
            "answerable": True,
            "confidence": 0.91,
            "recommended_path": "mcp",
        }

    monkeypatch.setattr(service.emb, "classify_with_query_vector", fake_classify_with_query_vector)
    monkeypatch.setattr(service, "_safe_answerability", fake_answerability)

    out = await service.classify(
        "customer care",
        openrouter_api_key="sk-or-test",
        mode="embeddings",
        tools=[_Tool("validate_otp", "Validate OTP and login state")],
    )
    assert out["backend"] == "embeddings"
    assert out["answerability"]["label"] == "mcp_answerable"


@pytest.mark.asyncio
async def test_nbfc_classifier_no_openrouter_key_still_returns_answerability(monkeypatch):
    service = NBFCClassifierService()

    async def fake_answerability(_text, *, tools, openrouter_api_key, query_vector=None):
        assert openrouter_api_key is None
        return {
            "label": "needs_general_llm",
            "answerable": False,
            "confidence": 0.0,
            "recommended_path": "llm",
        }

    monkeypatch.setattr(service, "_safe_answerability", fake_answerability)

    out = await service.classify(
        "what is quantum computing",
        openrouter_api_key=None,
        tools=[_Tool("validate_otp", "Validate OTP and login state")],
    )
    assert out["error"] == "OpenRouter Key required for router"
    assert out["answerability"]["label"] == "needs_general_llm"
