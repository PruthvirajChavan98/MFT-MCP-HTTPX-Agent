"""LLM-based metric computation for shadow evaluation.

The eval system is **pure LLM-graded**:
- RAGAS (`compute_llm_metrics` here) writes ``answer_relevancy`` for every trace
  with non-empty ``final_output``; ``faithfulness`` and ``context_relevance``
  additionally fire when the trace has retrieved contexts.
- Shadow-judge (separate worker) writes ``Helpfulness`` / ``Faithfulness`` /
  ``PolicyAdherence`` and mirrors them into ``eval_results`` so the
  Evaluation panel surfaces all judges in a single place.

There are NO regex rules, NO category-specific assertions, NO threshold
checks. Hardcoded category rules were removed because they yielded silent
zero-coverage for any question the operator hadn't pre-anticipated. If a
domain-specific deterministic check is ever needed, add it as a separate
named metric — do **not** reintroduce the rule-loop.
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
# Non-LLM metrics — intentionally empty
# ---------------------------------------------------------------------------
def compute_non_llm_metrics(
    trace: Dict[str, Any],
    events: Sequence[Dict[str, Any]],
    tool_names: Set[str],
) -> List[Dict[str, Any]]:
    """Returns ``[]``. Kept as a stable callable for upstream `_commit_bundle`.

    Earlier revisions emitted ``AnswerNonEmpty`` / ``StreamOk`` plus
    regex-rule-driven ``ToolMatch`` and ``NormalizedRegexMatch`` rows. Those
    were transport invariants and category-coupled checks respectively —
    neither is a real evaluation. All evaluation now flows through
    ``compute_llm_metrics`` (RAGAS) and the shadow-judge worker.
    """
    _ = trace, events, tool_names
    return []


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
