"""Shadow evaluation orchestrator.

Ties together the eval sub-modules (collector, throttle, metrics, persistence)
into a single entry point for the agent streaming pipeline.

Public API (backward-compatible):
    ShadowEvalCollector   — event collector dataclass
    maybe_shadow_eval_commit — async orchestrator: decide → evaluate → persist
    should_shadow_eval    — async sampling check
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from src.agent_service.core.config import (  # noqa: F401 — accessed by test via module attribute
    ENABLE_LLM_JUDGE,
)
from src.agent_service.eval_store.embedder import EvalEmbedder
from src.agent_service.eval_store.pg_store import get_shared_pool

from .eval.collector import ShadowEvalCollector
from .eval.metrics import compute_llm_metrics, compute_non_llm_metrics
from .eval.persistence import _commit_bundle
from .eval.throttle import _shadow_eval_decision, should_shadow_eval

log = logging.getLogger("shadow_eval")

# Stream config — used by external workers (eval_ingest, shadow_judge_worker)
ROUTER_JOBS_STREAM_KEY = (os.getenv("ROUTER_JOBS_STREAM_KEY") or "router:jobs").strip()
ROUTER_JOBS_STREAM_MAXLEN = int(os.getenv("ROUTER_JOBS_STREAM_MAXLEN") or "50000")

# Capture mode for event filtering in the orchestrator
SHADOW_EVAL_CAPTURE = (os.getenv("SHADOW_EVAL_CAPTURE") or "light").strip().lower()

__all__ = [
    "ShadowEvalCollector",
    "maybe_shadow_eval_commit",
    "should_shadow_eval",
]


async def maybe_shadow_eval_commit(
    collector: ShadowEvalCollector,
    openrouter_api_key: Optional[str] = None,
    nvidia_api_key: Optional[str] = None,
    groq_api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    provider: Optional[str] = None,
) -> None:
    try:
        should_run, skip_reason = await _shadow_eval_decision()
        if not should_run:
            collector.set_eval_lifecycle("inline", skip_reason, reason=skip_reason)
            await _commit_bundle(collector.build_trace_dict(), [], [])
            return

        if SHADOW_EVAL_CAPTURE != "full":
            events: List[Dict[str, Any]] = [
                e
                for e in collector.events
                if e.get("event_type") in ("tool_start", "tool_end", "error", "done")
            ]
        else:
            events = collector.events

        trace = collector.build_trace_dict()
        evals = compute_non_llm_metrics(trace, events, collector.tool_names)

        # Pass session's model to judge
        llm_evals = await compute_llm_metrics(
            trace,
            collector,
            openrouter_api_key=openrouter_api_key,
            nvidia_api_key=nvidia_api_key,
            groq_api_key=groq_api_key,
            model_name=model_name,
            provider=provider,
        )
        evals.extend(llm_evals)

        collector.set_eval_lifecycle("inline", "complete")
        trace = collector.build_trace_dict()
        await _commit_bundle(trace, events, evals)

        try:
            embedder = EvalEmbedder()
            pool = get_shared_pool()
            if pool is not None:
                await embedder.embed_trace_if_needed(pool, trace, events)
                for ev in evals:
                    await embedder.embed_eval_if_needed(pool, trace["trace_id"], ev)
        except Exception as e:
            log.warning("[shadow_eval] Embedding generation failed: %s", e)

        log.info(
            "[shadow_eval] committed trace_id=%s events=%d evals=%d",
            collector.trace_id,
            len(events),
            len(evals),
        )
    except Exception as e:
        collector.set_eval_lifecycle("inline", "failed", reason="failed")
        try:
            await _commit_bundle(collector.build_trace_dict(), [], [])
        except Exception as persist_exc:
            log.warning(
                "[shadow_eval] failed to persist inline lifecycle failure trace=%s: %s",
                collector.trace_id,
                persist_exc,
            )
        log.exception("[shadow_eval] commit failed: %s", e)
