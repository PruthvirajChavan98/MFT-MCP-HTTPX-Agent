"""LLM-graded evaluation + minimal transport sanity metrics.

The evaluation surface is overwhelmingly LLM-graded:
- RAGAS (`compute_llm_metrics` here) writes ``answer_relevancy`` for every trace
  with non-empty ``final_output``; ``faithfulness`` and ``context_relevance``
  additionally fire when the trace has retrieved contexts.
- Shadow-judge (separate worker) writes ``Helpfulness`` / ``Faithfulness`` /
  ``PolicyAdherence`` and mirrors them into ``eval_results``.

Two **transport sanity** metrics — ``StreamOk`` and ``AnswerNonEmpty`` — also
emit for every trace via ``compute_non_llm_metrics``. They are deliberately
NOT evaluations of agent quality; they answer "did the request complete and
return text?" If they fail, the LLM judges' scores are unreliable, so
operators see them surfaced alongside the judges as a context floor.

What we still don't do:
- NO regex category rules.
- NO ``require_tool`` / ``answer_pattern`` assertions.
- NO threshold checks (latency budgets, token caps, etc.).

Domain-specific deterministic checks should be added as **named** universal
metrics in ``compute_non_llm_metrics`` — do NOT reintroduce a rule-loop or
``DEFAULT_RULES`` config.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Sequence, Set

from src.agent_service.core.config import ENABLE_LLM_JUDGE, JUDGE_MODEL_NAME
from src.agent_service.eval_store.ragas_judge import RagasJudge

from .collector import ShadowEvalCollector

log = logging.getLogger("shadow_eval")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _metric(
    trace_id: str,
    metric_name: str,
    passed: bool,
    score: float,
    reasoning: str,
    evaluator_id: str = "shadow_eval",
    meta: Optional[dict] = None,
) -> Dict[str, Any]:
    return {
        "eval_id": uuid.uuid4().hex,
        "trace_id": trace_id,
        "metric_name": metric_name,
        "score": float(score),
        "passed": bool(passed),
        "reasoning": reasoning,
        "evaluator_id": evaluator_id,
        "evidence": [],
        "meta": meta or {},
    }


# ---------------------------------------------------------------------------
# Transport sanity metrics — universal, deterministic, always-emit
# ---------------------------------------------------------------------------
def compute_non_llm_metrics(
    trace: Dict[str, Any],
    events: Sequence[Dict[str, Any]],
    tool_names: Set[str],
) -> List[Dict[str, Any]]:
    """Emit two universal sanity metrics: ``StreamOk`` and ``AnswerNonEmpty``.

    These are **not** quality evaluations — they're transport floors that tell
    operators whether the LLM judges' scores can be trusted. A trace where
    ``StreamOk`` fails almost certainly has noise downstream; a trace where
    ``AnswerNonEmpty`` fails has nothing for the judges to grade.

    The previous regex-rule-driven ``ToolMatch`` / ``NormalizedRegexMatch``
    metrics were removed in PR #18 — they yielded silent zero-coverage for
    95% of questions and have not been reintroduced.
    """
    _ = events, tool_names
    trace_id = str(trace.get("trace_id"))
    final_output = trace.get("final_output") or ""
    out: List[Dict[str, Any]] = []

    ok_out = bool(str(final_output).strip())
    out.append(
        _metric(
            trace_id,
            "AnswerNonEmpty",
            ok_out,
            1.0 if ok_out else 0.0,
            "final_output is non-empty" if ok_out else "final_output empty",
        )
    )

    ok_status = (trace.get("status") == "success") and not trace.get("error")
    out.append(
        _metric(
            trace_id,
            "StreamOk",
            ok_status,
            1.0 if ok_status else 0.0,
            "status=success" if ok_status else f"error={trace.get('error')}",
        )
    )

    return out


# ---------------------------------------------------------------------------
# LLM metrics (RAGAS judge)
# ---------------------------------------------------------------------------
async def compute_llm_metrics(
    trace: Dict[str, Any],
    collector: ShadowEvalCollector,
    openrouter_api_key: Optional[str] = None,
    nvidia_api_key: Optional[str] = None,
    groq_api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    provider: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if not ENABLE_LLM_JUDGE:
        return []

    trace_id = trace["trace_id"]
    question = trace.get("inputs", {}).get("question", "")
    answer = trace.get("final_output", "") or ""

    if not answer:
        return []

    # Tool outputs captured by the collector map directly to RAGAS retrieved_contexts
    contexts: List[str] = collector.retrieved_context or []

    judge_model = model_name or trace.get("model") or JUDGE_MODEL_NAME

    try:
        if groq_api_key:
            # Session BYOK — honor the user's key, single-LLM path.
            judge = RagasJudge(
                model_name=judge_model,
                openrouter_api_key=openrouter_api_key,
                nvidia_api_key=nvidia_api_key,
                groq_api_key=groq_api_key,
            )
        else:
            # No session key — eval path spreads 3 metrics across 3 Groq keys
            # via the shared rotator.
            judge = await RagasJudge.for_eval(
                model_name=judge_model,
                openrouter_api_key=openrouter_api_key,
                nvidia_api_key=nvidia_api_key,
            )
    except Exception as exc:
        log.warning(
            "[shadow_eval] RAGAS judge initialization failed trace=%s: %s",
            trace_id,
            exc,
            exc_info=True,
        )
        return []

    try:
        return await judge.evaluate(question, answer, contexts, trace_id)
    except Exception as exc:
        log.warning(
            "[shadow_eval] RAGAS evaluation failed trace=%s: %s",
            trace_id,
            exc,
            exc_info=True,
        )
        return []
