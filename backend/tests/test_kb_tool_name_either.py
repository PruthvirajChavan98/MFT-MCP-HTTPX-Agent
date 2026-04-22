"""Regression lock: either `search_knowledge_base` (MCP-side Milvus) or
`mock_fintech_knowledge_base` (LangChain-side fallback) satisfies the
KB-tool expectation in the shadow-eval rule AND the answerability router.

Driven by: live deployment called `search_knowledge_base` (per prompts.yaml
preference) but the default shadow-eval rule hardcoded the old LC-fallback
tool name, producing `ToolMatch(mock_fintech_knowledge_base) 0%` despite
the correct behaviour.
"""

from __future__ import annotations

import pytest

from src.agent_service.features.eval import metrics
from src.agent_service.features.routing.answerability import _KB_TOOL_NAMES

# ---------- eval rule -------------------------------------------------


def _run_stolen_vehicle_rule(tool_names: set[str]) -> dict:
    """Exercise the default StolenVehicleEmiFaq rule and return its
    ToolMatch metric payload."""
    trace = {
        "trace_id": "t-1",
        "status": "success",
        "error": None,
        "final_output": "We cannot stop the EMI — it must continue.",
        "inputs": {"question": "my vehicle is stolen can I stop my emi?"},
    }
    results = metrics.compute_non_llm_metrics(trace, events=[], tool_names=tool_names)
    tool_matches = [r for r in results if r["metric_name"].startswith("ToolMatch(")]
    assert len(tool_matches) == 1, f"expected 1 ToolMatch metric, got {tool_matches}"
    return tool_matches[0]


def test_rule_passes_when_search_knowledge_base_called() -> None:
    result = _run_stolen_vehicle_rule({"search_knowledge_base"})
    assert result["passed"] is True
    assert result["score"] == 1.0
    assert result["metric_name"] == "ToolMatch(search_knowledge_base)"


def test_rule_passes_when_lc_fallback_called() -> None:
    result = _run_stolen_vehicle_rule({"mock_fintech_knowledge_base"})
    assert result["passed"] is True
    assert result["score"] == 1.0
    assert result["metric_name"] == "ToolMatch(mock_fintech_knowledge_base)"


def test_rule_fails_when_no_kb_tool_called() -> None:
    result = _run_stolen_vehicle_rule({"some_other_tool"})
    assert result["passed"] is False
    assert result["score"] == 0.0
    # Label shows both options so the failure message is actionable.
    assert "search_knowledge_base" in result["metric_name"]
    assert "mock_fintech_knowledge_base" in result["metric_name"]
    assert result["meta"]["expected_any_of"] == [
        "search_knowledge_base",
        "mock_fintech_knowledge_base",
    ]


def test_rule_still_supports_legacy_string_require_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User-supplied rules via SHADOW_EVAL_RULES_JSON may still use a
    single string; the handler must accept that shape unchanged."""
    monkeypatch.setattr(
        metrics,
        "DEFAULT_RULES",
        [
            {
                "name": "LegacyShape",
                "when": r"stolen",
                "require_tool": "some_custom_tool",
            }
        ],
    )
    trace = {
        "trace_id": "t-legacy",
        "status": "success",
        "error": None,
        "final_output": "x",
        "inputs": {"question": "vehicle is stolen"},
    }
    results = metrics.compute_non_llm_metrics(trace, events=[], tool_names={"some_custom_tool"})
    tool_matches = [r for r in results if r["metric_name"].startswith("ToolMatch(")]
    assert len(tool_matches) == 1
    assert tool_matches[0]["passed"] is True
    assert tool_matches[0]["metric_name"] == "ToolMatch(some_custom_tool)"


# ---------- answerability router -------------------------------------


def test_kb_tool_names_set_contains_both_canonical_names() -> None:
    """Locks the accepted-KB-names frozenset against silent drift."""
    assert _KB_TOOL_NAMES == frozenset({"search_knowledge_base", "mock_fintech_knowledge_base"})
