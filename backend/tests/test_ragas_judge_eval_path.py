"""RagasJudge eval-path tests: per-metric Groq keys + per-metric timeouts.

These tests never call the real RAGAS metrics or real Groq. The 3 metric
instances on a RagasJudge are replaced with fakes whose ``ascore`` is a
controllable coroutine; the classmethod ``for_eval`` is exercised by
monkeypatching ``next_groq_keys`` and the wrappers used by construction.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from src.agent_service.eval_store import ragas_judge
from src.agent_service.eval_store.ragas_judge import RagasJudge


class _FakeMetric:
    def __init__(self, result: Any = 0.7, *, delay: float = 0.0, raises: bool = False) -> None:
        self._result = result
        self._delay = delay
        self._raises = raises
        self.calls = 0

    async def ascore(self, **_: Any) -> float:
        self.calls += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._raises:
            raise RuntimeError("metric-boom")
        return self._result


def _bare_judge() -> RagasJudge:
    """Construct a RagasJudge without touching real LLMs/embeddings."""
    judge = RagasJudge.__new__(RagasJudge)
    judge.model_name = "openai/gpt-oss-120b"
    return judge


@pytest.mark.asyncio
async def test_evaluate_returns_three_results_when_all_metrics_pass() -> None:
    judge = _bare_judge()
    judge._faithfulness = _FakeMetric(0.8)
    judge._answer_rel = _FakeMetric(0.9)
    judge._context_rel = _FakeMetric(0.6)

    results = await judge.evaluate("q", "a", ["ctx"], "trace-1")

    assert len(results) == 3
    names = {r["metric_name"] for r in results}
    assert names == {"faithfulness", "answer_relevancy", "context_relevance"}
    assert all(r["trace_id"] == "trace-1" for r in results)
    assert all(r["passed"] for r in results)


@pytest.mark.asyncio
async def test_evaluate_empty_contexts_emits_only_answer_relevancy() -> None:
    """Tool-less traces must still produce ≥1 RAGAS row (answer_relevancy).

    Faithfulness and ContextRelevance are skipped — they require non-empty
    retrieved_contexts and would either raise or score zero on empty input,
    which previously dropped the entire RAGAS row set for tool-less traces.
    """
    judge = _bare_judge()
    judge._answer_rel = _FakeMetric(0.85)
    # Construct context-dependent metrics so we can assert they were never called.
    judge._faithfulness = _FakeMetric(0.8)
    judge._context_rel = _FakeMetric(0.6)

    results = await judge.evaluate("q", "a", [], "trace-no-tools")

    assert len(results) == 1
    assert results[0]["metric_name"] == "answer_relevancy"
    assert results[0]["passed"] is True
    # Critically: faithfulness/context_relevance must NOT have been invoked.
    assert judge._faithfulness.calls == 0
    assert judge._context_rel.calls == 0


@pytest.mark.asyncio
async def test_evaluate_per_metric_timeout_does_not_stall_others(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Short timeout so the slow metric trips quickly.
    monkeypatch.setattr(ragas_judge, "RAGAS_PER_METRIC_TIMEOUT_S", 0.05)

    judge = _bare_judge()
    judge._faithfulness = _FakeMetric(0.7, delay=1.0)  # will time out
    judge._answer_rel = _FakeMetric(0.8)
    judge._context_rel = _FakeMetric(0.6)

    results = await judge.evaluate("q", "a", ["ctx"], "trace-2")

    # 2 good metrics returned; timed-out one is skipped.
    names = {r["metric_name"] for r in results}
    assert names == {"answer_relevancy", "context_relevance"}


@pytest.mark.asyncio
async def test_evaluate_metric_exception_is_isolated() -> None:
    judge = _bare_judge()
    judge._faithfulness = _FakeMetric(raises=True)
    judge._answer_rel = _FakeMetric(0.8)
    judge._context_rel = _FakeMetric(0.6)

    results = await judge.evaluate("q", "a", ["ctx"], "trace-3")

    names = {r["metric_name"] for r in results}
    assert names == {"answer_relevancy", "context_relevance"}


@pytest.mark.asyncio
async def test_evaluate_empty_inputs_short_circuits() -> None:
    judge = _bare_judge()
    # Should never even touch the metrics.
    judge._faithfulness = _FakeMetric(raises=True)
    judge._answer_rel = _FakeMetric(raises=True)
    judge._context_rel = _FakeMetric(raises=True)

    assert await judge.evaluate("", "a", [], "t") == []
    assert await judge.evaluate("q", "", [], "t") == []


# --- for_eval classmethod wiring -------------------------------------------


class _Recorder:
    """Captures calls to monkeypatched construction functions."""

    def __init__(self) -> None:
        self.get_llm_calls: list[dict[str, Any]] = []
        self.wrapped_llms: list[object] = []


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    rec = _Recorder()

    def _fake_get_llm(**kwargs: Any) -> str:
        rec.get_llm_calls.append(kwargs)
        return f"lc_llm::{kwargs.get('groq_api_key')}"

    class _FakeWrapper:
        def __init__(self, lc: Any) -> None:
            self.lc = lc
            rec.wrapped_llms.append(self)

    class _FakeEmbWrapper:
        def __init__(self, emb: Any) -> None:
            self.emb = emb

    def _fake_owner_embeddings(model: str) -> str:
        return f"emb::{model}"

    class _FakeMetricClass:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    monkeypatch.setattr(ragas_judge, "get_llm", _fake_get_llm)
    monkeypatch.setattr(ragas_judge, "get_owner_embeddings", _fake_owner_embeddings)
    monkeypatch.setattr(ragas_judge, "LangchainLLMWrapper", _FakeWrapper)
    monkeypatch.setattr(ragas_judge, "LangchainEmbeddingsWrapper", _FakeEmbWrapper)
    monkeypatch.setattr(ragas_judge, "Faithfulness", _FakeMetricClass)
    monkeypatch.setattr(ragas_judge, "AnswerRelevancy", _FakeMetricClass)
    monkeypatch.setattr(ragas_judge, "ContextRelevance", _FakeMetricClass)
    return rec


@pytest.mark.asyncio
async def test_for_eval_groq_path_uses_three_distinct_keys(
    monkeypatch: pytest.MonkeyPatch,
    recorder: _Recorder,
) -> None:
    async def _fake_next(n: int) -> list[str]:
        assert n == 3
        return ["grk-A", "grk-B", "grk-C"]

    monkeypatch.setattr(ragas_judge, "next_groq_keys", _fake_next)

    judge = await RagasJudge.for_eval(model_name="openai/gpt-oss-120b")

    keys_used = [c["groq_api_key"] for c in recorder.get_llm_calls]
    assert keys_used == ["grk-A", "grk-B", "grk-C"]
    # All 3 calls declared provider="groq" at temperature 0.
    assert all(c["provider"] == "groq" for c in recorder.get_llm_calls)
    assert all(c["temperature"] == 0.0 for c in recorder.get_llm_calls)
    assert judge._metric_keys == ["grk-A", "grk-B", "grk-C"]


@pytest.mark.asyncio
async def test_for_eval_openrouter_path_falls_back_to_single_llm(
    monkeypatch: pytest.MonkeyPatch,
    recorder: _Recorder,
) -> None:
    called = False

    async def _should_not_be_called(_n: int) -> list[str]:
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(ragas_judge, "next_groq_keys", _should_not_be_called)

    judge = await RagasJudge.for_eval(
        model_name="openai/gpt-oss-120b",
        openrouter_api_key="sk-or-xxxx",
    )

    assert called is False
    # Exactly one get_llm call, provider=openrouter.
    assert len(recorder.get_llm_calls) == 1
    assert recorder.get_llm_calls[0]["provider"] == "openrouter"
    assert judge.model_name == "openai/gpt-oss-120b"


@pytest.mark.asyncio
async def test_for_eval_nvidia_path_falls_back_to_single_llm(
    monkeypatch: pytest.MonkeyPatch,
    recorder: _Recorder,
) -> None:
    async def _never(_n: int) -> list[str]:
        raise AssertionError("next_groq_keys must not be called on nvidia path")

    monkeypatch.setattr(ragas_judge, "next_groq_keys", _never)

    await RagasJudge.for_eval(
        model_name="nvidia/llama-3-70b",
        nvidia_api_key="nvapi-xxx",
    )

    assert len(recorder.get_llm_calls) == 1
    assert recorder.get_llm_calls[0]["provider"] == "nvidia"
