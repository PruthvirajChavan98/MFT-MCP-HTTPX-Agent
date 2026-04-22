"""Regression lock: the canonical KB tool is `search_knowledge_base`.

The LangChain-side `mock_fintech_knowledge_base` fallback was removed in
the Phase-M1 cleanup (see `tools/mcp_manager.py` + `prompts.yaml`). Two
places still read the canonical name and must stay aligned:

  1. Shadow-eval rule `DEFAULT_RULES[0].require_tool`
     (`features/eval/metrics.py`)
  2. Router answerability gate `_KB_TOOL_NAME`
     (`features/routing/answerability.py`)

These tests also exercise the `require_tool` handler's list-form support
so user-supplied rules via `SHADOW_EVAL_RULES_JSON` can still specify
multiple acceptable tools when the operator wants that.
"""

from __future__ import annotations

import pytest

from src.agent_service.features.eval import metrics
from src.agent_service.features.routing.answerability import _KB_TOOL_NAME

_CANONICAL_KB_TOOL = "search_knowledge_base"


def _run_stolen_vehicle_rule(tool_names: set[str]) -> dict:
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


# ---------- canonical-name invariants --------------------------------


def test_default_rule_requires_canonical_kb_tool() -> None:
    rule = next(r for r in metrics.DEFAULT_RULES if r["name"] == "StolenVehicleEmiFaq")
    assert rule["require_tool"] == _CANONICAL_KB_TOOL


def test_router_kb_tool_name_is_canonical() -> None:
    assert _KB_TOOL_NAME == _CANONICAL_KB_TOOL


# ---------- eval rule behaviour -------------------------------------


def test_rule_passes_when_search_knowledge_base_called() -> None:
    result = _run_stolen_vehicle_rule({_CANONICAL_KB_TOOL})
    assert result["passed"] is True
    assert result["score"] == 1.0
    assert result["metric_name"] == f"ToolMatch({_CANONICAL_KB_TOOL})"


def test_rule_fails_when_legacy_fallback_tool_called() -> None:
    """If the deprecated fallback ever re-appears in a trace, the rule
    correctly reports it as a miss — the fallback is no longer canonical."""
    result = _run_stolen_vehicle_rule({"mock_fintech_knowledge_base"})
    assert result["passed"] is False
    assert result["score"] == 0.0


def test_rule_fails_when_no_kb_tool_called() -> None:
    result = _run_stolen_vehicle_rule({"some_other_tool"})
    assert result["passed"] is False
    assert result["score"] == 0.0


# ---------- user-supplied rules: list-form support ------------------


def test_require_tool_list_form_still_supported_via_env_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Operators can still ship a list via SHADOW_EVAL_RULES_JSON when
    they want multiple acceptable tools — keeps the default simple but
    the handler flexible."""
    monkeypatch.setattr(
        metrics,
        "DEFAULT_RULES",
        [
            {
                "name": "MultiTool",
                "when": r"stolen",
                "require_tool": ["tool_a", "tool_b"],
            }
        ],
    )
    trace = {
        "trace_id": "t-multi",
        "status": "success",
        "error": None,
        "final_output": "x",
        "inputs": {"question": "vehicle is stolen"},
    }
    results = metrics.compute_non_llm_metrics(trace, events=[], tool_names={"tool_b"})
    tool_matches = [r for r in results if r["metric_name"].startswith("ToolMatch(")]
    assert len(tool_matches) == 1
    assert tool_matches[0]["passed"] is True
    assert tool_matches[0]["metric_name"] == "ToolMatch(tool_b)"
