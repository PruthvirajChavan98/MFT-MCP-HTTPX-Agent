"""Regression: ShadowEvalCollector.build_trace_dict() must surface
inline_guard_decision / reason_code / risk_score at the top level so the
ON CONFLICT UPDATE in EvalPgStore.upsert_trace() doesn't overwrite the
columns with NULL on the second persist (maybe_shadow_eval_commit, run
in `finally` after the synchronous persist_runtime_trace).

Bug: trace 12227118a97b4902919a128011e3732b in production session
019dfdc3-49f4-76c0-a5f2-00652d684721 had `meta.inline_guard.decision = "allow"`
but `inline_guard_decision` column was NULL. Root cause: build_trace_dict
populated only the `meta.inline_guard` blob; the second writer didn't
denormalise; UPDATE wrote NULLs over the values the first writer set.
"""

from __future__ import annotations

import pytest

from src.agent_service.features.eval.collector import ShadowEvalCollector


def _make_collector() -> ShadowEvalCollector:
    return ShadowEvalCollector(
        session_id="session-x",
        question="what tools do you have?",
        provider="groq",
        model="openai/gpt-oss-120b",
        endpoint="/agent/stream",
        system_prompt="be helpful",
        tool_definitions="",
    )


def test_build_trace_dict_denormalises_guard_fields_on_top_level() -> None:
    collector = _make_collector()
    collector.set_inline_guard_decision(
        {
            "allow": True,
            "decision": "allow",
            "reason_code": "safe",
            "risk_score": 0.0,
            "checks": [],
        }
    )
    collector.on_done("ok", None)

    trace = collector.build_trace_dict()

    # Both the meta blob (for forward-compat consumers) AND the top-level
    # columns (for the SQL upsert) must be populated.
    assert trace["meta"]["inline_guard"]["decision"] == "allow"
    assert trace["inline_guard_decision"] == "allow"
    assert trace["inline_guard_reason_code"] == "safe"
    assert trace["inline_guard_risk_score"] == pytest.approx(0.0)


def test_build_trace_dict_block_decision_round_trips() -> None:
    collector = _make_collector()
    collector.set_inline_guard_decision(
        {
            "allow": False,
            "decision": "block",
            "reason_code": "unsafe_signal",
            "risk_score": 0.9,
            "checks": [],
        }
    )
    collector.on_done("", "Prompt violates security policy")

    trace = collector.build_trace_dict()
    assert trace["inline_guard_decision"] == "block"
    assert trace["inline_guard_reason_code"] == "unsafe_signal"
    assert trace["inline_guard_risk_score"] == pytest.approx(0.9)


def test_build_trace_dict_with_no_guard_decision_keeps_keys_none() -> None:
    collector = _make_collector()
    collector.on_done("ok", None)

    trace = collector.build_trace_dict()
    # Keys must be present (so the upsert binds them), but NULL is the right
    # value when the guard never ran (e.g. INLINE_GUARD_ENABLED=false path
    # or admin/internal endpoints bypassing the gate).
    assert trace["inline_guard_decision"] is None
    assert trace["inline_guard_reason_code"] is None
    assert trace["inline_guard_risk_score"] is None
    assert "inline_guard" not in trace["meta"]


def test_build_trace_dict_handles_partial_decision_dict() -> None:
    """Defensive: if the decision dict is missing risk_score for any reason,
    we should populate what we can and leave the missing field as None
    rather than raising or storing an empty string."""
    collector = _make_collector()
    collector.set_inline_guard_decision(
        {
            "decision": "degraded_allow",
            "reason_code": "infra_degraded",
            # risk_score intentionally omitted
        }
    )
    collector.on_done("ok", None)

    trace = collector.build_trace_dict()
    assert trace["inline_guard_decision"] == "degraded_allow"
    assert trace["inline_guard_reason_code"] == "infra_degraded"
    assert trace["inline_guard_risk_score"] is None


def test_build_trace_dict_strips_blank_decision_strings() -> None:
    """Whitespace-only strings on `decision`/`reason_code` should be coerced
    to None, not pass through as falsy-looking columns that confuse the
    admin dashboard's "no decision" state."""
    collector = _make_collector()
    collector.set_inline_guard_decision(
        {
            "decision": "   ",
            "reason_code": "",
            "risk_score": 0.42,
        }
    )
    collector.on_done("ok", None)

    trace = collector.build_trace_dict()
    assert trace["inline_guard_decision"] is None
    assert trace["inline_guard_reason_code"] is None
    assert trace["inline_guard_risk_score"] == pytest.approx(0.42)
