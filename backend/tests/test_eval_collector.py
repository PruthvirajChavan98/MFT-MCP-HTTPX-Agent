"""Regression tests for ShadowEvalCollector.build_trace_dict router projection.

The projection used to emit `router_reason=None` whenever the embeddings router
returned `{"reason": None, ...}` for a non-ops-intent query. That NULL landed in
`eval_traces.router_reason`, which the Topic Distribution SQL CASE then
misclassified as "other", producing the 98% Uncategorized dashboard.

Both layers now emit `"unknown"`:
- nbfc_router.py always returns a reason dict (never None)
- collector.py falls back to "unknown" if a future router forgets the convention
"""

from __future__ import annotations

from src.agent_service.features.eval.collector import ShadowEvalCollector


def _make_collector() -> ShadowEvalCollector:
    return ShadowEvalCollector(
        session_id="sess-1",
        question="hello",
        provider="groq",
        model="openai/gpt-oss-120b",
        endpoint="/agent/stream",
    )


def test_build_trace_dict_uses_unknown_when_reason_is_none() -> None:
    """Outcome with explicit `reason: None` must project as 'unknown', not NULL."""
    c = _make_collector()
    c.set_router_outcome(
        {
            "backend": "embeddings",
            "sentiment": {"label": "positive", "score": 0.8},
            "reason": None,  # the historical bug trigger
        }
    )
    trace = c.build_trace_dict()
    assert trace["router_backend"] == "embeddings"
    assert trace["router_sentiment"] == "positive"
    assert trace["router_reason"] == "unknown"
    assert trace["router_reason_score"] == 0.0


def test_build_trace_dict_uses_unknown_when_reason_label_missing() -> None:
    """Outcome with reason dict but no label key also falls back to 'unknown'."""
    c = _make_collector()
    c.set_router_outcome(
        {
            "backend": "llm",
            "sentiment": {"label": "negative", "score": 0.9},
            "reason": {"score": 0.42},  # missing "label"
        }
    )
    trace = c.build_trace_dict()
    assert trace["router_reason"] == "unknown"
    assert trace["router_reason_score"] == 0.42


def test_build_trace_dict_preserves_real_reason() -> None:
    """Happy path: a populated reason dict round-trips unchanged."""
    c = _make_collector()
    c.set_router_outcome(
        {
            "backend": "embeddings",
            "sentiment": {"label": "negative", "score": 0.91},
            "reason": {"label": "fraud_security", "score": 0.87, "topk": []},
        }
    )
    trace = c.build_trace_dict()
    assert trace["router_reason"] == "fraud_security"
    assert trace["router_reason_score"] == 0.87


def test_build_trace_dict_no_router_outcome_leaves_fields_unset() -> None:
    """When set_router_outcome is never called, router_* fields stay absent."""
    c = _make_collector()
    trace = c.build_trace_dict()
    assert "router_reason" not in trace
    assert "router_backend" not in trace
