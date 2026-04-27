"""``compute_non_llm_metrics`` always emits two transport sanity metrics.

These are deliberately **not** quality evaluations — they're context floors
that tell operators whether downstream LLM-graded scores can be trusted.
Locked here so a future "pure LLM" refactor doesn't silently delete them
again.
"""

from __future__ import annotations

from src.agent_service.features.eval.metrics import compute_non_llm_metrics


def _metrics_for(trace: dict) -> dict[str, dict]:
    rows = compute_non_llm_metrics(trace, events=[], tool_names=set())
    return {row["metric_name"]: row for row in rows}


def test_emits_both_universal_metrics() -> None:
    rows = _metrics_for(
        {
            "trace_id": "t-ok",
            "status": "success",
            "error": None,
            "final_output": "hello",
        }
    )
    assert set(rows) == {"AnswerNonEmpty", "StreamOk"}
    assert all(r["passed"] for r in rows.values())
    assert all(r["score"] == 1.0 for r in rows.values())
    assert all(r["evaluator_id"] == "shadow_eval" for r in rows.values())


def test_answer_non_empty_fails_on_empty_output() -> None:
    rows = _metrics_for(
        {
            "trace_id": "t-empty",
            "status": "success",
            "error": None,
            "final_output": "   ",  # whitespace-only
        }
    )
    assert rows["AnswerNonEmpty"]["passed"] is False
    assert rows["AnswerNonEmpty"]["score"] == 0.0
    assert rows["StreamOk"]["passed"] is True


def test_stream_ok_fails_on_error_status() -> None:
    rows = _metrics_for(
        {
            "trace_id": "t-error",
            "status": "error",
            "error": "boom",
            "final_output": "partial",
        }
    )
    assert rows["StreamOk"]["passed"] is False
    assert "error=boom" in rows["StreamOk"]["reasoning"]
    # Output presence is independent of stream status
    assert rows["AnswerNonEmpty"]["passed"] is True


def test_no_regex_rule_metrics_emitted() -> None:
    """Lock against accidental reintroduction of the rule-loop.

    No `ToolMatch(*)` or `NormalizedRegexMatch` rows — these were removed in
    PR #18 and should never come back without an explicit RFC.
    """
    rows = compute_non_llm_metrics(
        {
            "trace_id": "t-stolen",
            "status": "success",
            "error": None,
            "final_output": "EMI cannot be stopped",
            "inputs": {"question": "my vehicle is stolen, can I stop my emi?"},
        },
        events=[],
        tool_names={"search_knowledge_base"},
    )
    metric_names = {r["metric_name"] for r in rows}
    assert metric_names == {"AnswerNonEmpty", "StreamOk"}
    for name in metric_names:
        assert not name.startswith("ToolMatch")
        assert name != "NormalizedRegexMatch"
