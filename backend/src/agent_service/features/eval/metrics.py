"""Rule-based and LLM-based metric computation for shadow evaluation."""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Sequence, Set

from src.agent_service.core.config import ENABLE_LLM_JUDGE, JUDGE_MODEL_NAME
from src.agent_service.eval_store.ragas_judge import RagasJudge

from .collector import ShadowEvalCollector, _strip_html

log = logging.getLogger("shadow_eval")

# ---------------------------------------------------------------------------
# Config (env) — judge and rules
# ---------------------------------------------------------------------------
JUDGE_REASONING_EFFORT = os.getenv("JUDGE_REASONING_EFFORT", "low")

RULES_JSON = (os.getenv("SHADOW_EVAL_RULES_JSON") or "").strip()

DEFAULT_RULES = [
    {
        "name": "StolenVehicleEmiFaq",
        "when": r"(vehicle\s+is\s+stolen|stolen\s+vehicle|stop\s+my\s+emi|emi\s+presentation)",
        "require_tool": "search_knowledge_base",
        "answer_pattern": r"(cannot\s*be\s*stopped|emi.*continue|continue\s*paying|credit\s*record|knowledge\s*base\s*error)",
    }
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _normalize_text(s: str) -> str:
    s = _strip_html(s or "")
    s = s.lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _load_rules() -> List[dict]:
    if not RULES_JSON:
        return DEFAULT_RULES
    try:
        obj = json.loads(RULES_JSON)
        if isinstance(obj, list) and obj:
            return [x for x in obj if isinstance(x, dict)]
    except Exception as exc:
        log.debug("Failed to parse SHADOW_EVAL_RULES_JSON, using defaults: %s", exc)
    return DEFAULT_RULES


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
# Non-LLM (rule-based) metrics
# ---------------------------------------------------------------------------
def compute_non_llm_metrics(
    trace: Dict[str, Any],
    events: Sequence[Dict[str, Any]],
    tool_names: Set[str],
) -> List[Dict[str, Any]]:
    trace_id = str(trace.get("trace_id"))
    question = str((trace.get("inputs") or {}).get("question") or "")
    final_output = trace.get("final_output") or ""
    norm_out = _normalize_text(str(final_output))
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

    rules = _load_rules()
    for r in rules:
        name = str(r.get("name") or "rule")
        when = r.get("when")
        if when:
            try:
                if not re.search(when, question, flags=re.I):
                    continue
            except Exception as exc:
                log.debug("Rule regex match failed for rule=%s: %s", name, exc)
                continue

        req_tool_raw = r.get("require_tool")
        req_tools: List[str] = []
        if isinstance(req_tool_raw, str):
            tool = req_tool_raw.strip()
            if tool:
                req_tools = [tool]
        elif isinstance(req_tool_raw, (list, tuple, set)):
            req_tools = [str(x).strip() for x in req_tool_raw if str(x).strip()]

        if req_tools:
            matched = next((t for t in req_tools if t in tool_names), None)
            has = matched is not None
            label = matched or " | ".join(req_tools)
            reasoning = (
                f"Tool {matched} called"
                if has
                else f"No required tool called (expected one of: {', '.join(req_tools)})"
            )
            out.append(
                _metric(
                    trace_id,
                    f"ToolMatch({label})",
                    has,
                    1.0 if has else 0.0,
                    reasoning,
                    meta={"rule": name, "expected_any_of": req_tools},
                )
            )

        pat = r.get("answer_pattern")
        if pat:
            try:
                m = re.search(pat, norm_out, flags=re.I)
                ok = m is not None
                out.append(
                    _metric(
                        trace_id,
                        "NormalizedRegexMatch",
                        ok,
                        1.0 if ok else 0.0,
                        f"Matched pattern '{pat}'" if ok else "Failed pattern",
                        meta={"rule": name},
                    )
                )
            except Exception as e:
                out.append(_metric(trace_id, "RegexError", False, 0.0, str(e)))
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
