from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Set

from starlette.concurrency import run_in_threadpool
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage

from src.agent_service.eval_store.neo4j_store import EvalNeo4jStore
from src.agent_service.eval_store.judge import judge_service
from src.agent_service.eval_store.embedder import EvalEmbedder
from src.agent_service.core.config import ENABLE_LLM_JUDGE, JUDGE_MODEL_NAME
from src.agent_service.llm.client import get_llm

log = logging.getLogger("shadow_eval")
STORE = EvalNeo4jStore()
EMBEDDER = EvalEmbedder()

ROUTER_JOBS_STREAM_KEY = (os.getenv('ROUTER_JOBS_STREAM_KEY') or 'router:jobs').strip()
ROUTER_JOBS_STREAM_MAXLEN = int(os.getenv('ROUTER_JOBS_STREAM_MAXLEN') or '50000')

__all__ = [
    "ShadowEvalCollector",
    "maybe_shadow_eval_commit",
    "should_shadow_eval",
]

# -----------------------------
# Config (env)
# -----------------------------
SHADOW_EVAL_ENABLED = (os.getenv("SHADOW_EVAL_ENABLED") or "0").strip() == "1"
SHADOW_EVAL_SAMPLE_RATE = float((os.getenv("SHADOW_EVAL_SAMPLE_RATE") or "0.05").strip())
SHADOW_EVAL_MAX_PER_MIN = int((os.getenv("SHADOW_EVAL_MAX_PER_MIN") or "20").strip())
SHADOW_EVAL_CAPTURE = (os.getenv("SHADOW_EVAL_CAPTURE") or "light").strip().lower()

# Judge Settings
JUDGE_REASONING_EFFORT = os.getenv("JUDGE_REASONING_EFFORT", "low")

# Safety caps
MAX_EVENTS = int((os.getenv("SHADOW_EVAL_MAX_EVENTS") or "500").strip())
MAX_TEXT = int((os.getenv("SHADOW_EVAL_MAX_TEXT") or "2000").strip())
MAX_FINAL = int((os.getenv("SHADOW_EVAL_MAX_FINAL") or "200000").strip())

# Optional rules override
RULES_JSON = (os.getenv("SHADOW_EVAL_RULES_JSON") or "").strip()

DEFAULT_RULES = [
    {
        "name": "StolenVehicleEmiFaq",
        "when": r"(vehicle\s+is\s+stolen|stolen\s+vehicle|stop\s+my\s+emi|emi\s+presentation)",
        "require_tool": "mock_fintech_knowledge_base",
        "answer_pattern": r"(cannot\s*be\s*stopped|emi.*continue|continue\s*paying|credit\s*record|knowledge\s*base\s*error)",
    }
]

# -----------------------------
# Prompts
# -----------------------------
JUDGE_SYSTEM_PROMPT = """
You are an impartial AI Judge for a FinTech assistant. 
Evaluate the "Assistant Answer" based on the provided Context.

### Metrics to Score (1-5 Scale):
1. **Faithfulness**: Is the answer derived *only* from the Tool Outputs? (Score 1 if hallucinated, 5 if fully grounded).
2. **Relevance**: Does the answer directly address the User Question? (Score 1 if evasive, 5 if direct).
3. **Correctness**: 
    - Did the assistant follow the **System Instructions** (e.g. refusal rules)? 
    - Is the answer factually consistent with the **Tool Outputs**?
4. **Coherence**: Is the answer clear and professional?

### Input Data
- **System Instructions**: The rules the assistant MUST follow.
- **Chat History**: Previous messages for context.
- **User Question**: The current query.
- **Tool Outputs**: Information retrieved to answer the query.
- **Assistant Answer**: The final response to evaluate.

Output JSON only.
"""

def _utc_iso(dt: Optional[datetime] = None) -> str:
    d = dt or datetime.now(timezone.utc)
    return d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def _clip(s: Optional[str], n: int) -> str:
    if not s: return ""
    s = str(s)
    return s if len(s) <= n else s[:n] + f"…(truncated {len(s)-n} chars)"

def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s or "")

def _normalize_text(s: str) -> str:
    s = _strip_html(s or "")
    s = s.lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _load_rules() -> List[dict]:
    if not RULES_JSON: return DEFAULT_RULES
    try:
        obj = json.loads(RULES_JSON)
        if isinstance(obj, list) and obj:
            return [x for x in obj if isinstance(x, dict)]
    except Exception:
        pass
    return DEFAULT_RULES

# -----------------------------
# Per-process throttle
# -----------------------------
_window_minute: int = 0
_window_count: int = 0
_throttle_lock = asyncio.Lock()

async def _throttle_ok() -> bool:
    global _window_minute, _window_count
    now_min = int(time.time() // 60)
    async with _throttle_lock:
        if now_min != _window_minute:
            _window_minute = now_min
            _window_count = 0
        if _window_count >= SHADOW_EVAL_MAX_PER_MIN:
            return False
        _window_count += 1
        return True

async def should_shadow_eval() -> bool:
    if not SHADOW_EVAL_ENABLED: return False
    if SHADOW_EVAL_SAMPLE_RATE <= 0: return False
    if random.random() > SHADOW_EVAL_SAMPLE_RATE: return False
    return await _throttle_ok()

# -----------------------------
# Collector
# -----------------------------
@dataclass
class ShadowEvalCollector:
    trace_id: str
    session_id: str
    question: str
    provider: Optional[str]
    model: Optional[str]
    endpoint: str
    started_at: datetime
    tool_names: Set[str]
    
    # Context Data for Judge
    retrieved_context: List[str]
    system_prompt: str
    chat_history: List[str]
    tool_definitions: str

    # Internal state
    _seq: int = 0
    events: List[Dict[str, Any]] = field(default_factory=list)
    final_parts: List[str] = field(default_factory=list)
    error: Optional[str] = None
    status: str = "success"
    
    # Optional fields
    case_id: Optional[str] = None
    _router_outcome: Optional[Dict[str, Any]] = None

    def __init__(
        self,
        session_id: str,
        question: str,
        provider: Optional[str],
        model: Optional[str],
        endpoint: str,
        system_prompt: str = "",
        chat_history: List[BaseMessage] = None, # type: ignore
        tool_definitions: str = ""
    ):
        self.trace_id = uuid.uuid4().hex
        self.session_id = session_id
        self.case_id = None 
        self.question = question
        self.provider = provider
        self.model = model
        self.endpoint = endpoint
        self.started_at = datetime.now(timezone.utc)
        self.tool_names = set()
        self.retrieved_context = []
        
        self.system_prompt = system_prompt
        self.tool_definitions = tool_definitions
        
        self.chat_history = []
        if chat_history:
            recent = chat_history[-5:]
            for msg in recent:
                role = "User" if isinstance(msg, HumanMessage) else "Assistant"
                self.chat_history.append(f"{role}: {msg.content}")

        self._seq = 0
        self.events = []
        self.final_parts = []
        self.error = None
        self.status = "success"
        self._router_outcome = None

    def set_router_outcome(self, outcome: Dict[str, Any]) -> None:
        """Store the router result to be saved with the trace."""
        self._router_outcome = outcome

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _add_event(
        self,
        event_type: str,
        name: str,
        text: Optional[str] = None,
        payload: Optional[dict] = None,
        meta: Optional[dict] = None,
    ) -> None:
        if len(self.events) >= MAX_EVENTS: return
        seq = self._next_seq()
        self.events.append({
            "trace_id": self.trace_id,
            "seq": seq,
            "event_key": f"{self.trace_id}:{seq}",
            "ts": _utc_iso(),
            "event_type": event_type,
            "name": name,
            "text": _clip(text, MAX_TEXT),
            "payload": payload or {},
            "meta": meta or {},
        })

    def _append_final(self, text: str) -> None:
        if not text: return
        cur_len = sum(len(x) for x in self.final_parts)
        if cur_len >= MAX_FINAL: return
        self.final_parts.append(text[: max(0, MAX_FINAL - cur_len)])

    # ---------- event helpers ----------
    def on_reasoning(self, token: str) -> None:
        if SHADOW_EVAL_CAPTURE == "full":
            self._add_event("reasoning_token", "reasoning_token", text=token)

    def on_token(self, token: str) -> None:
        self._append_final(token)
        if SHADOW_EVAL_CAPTURE == "full":
            self._add_event("token", "token", text=token)

    def on_tool_start(self, tool: str, tool_input: Any) -> None:
        self.tool_names.add(str(tool))
        payload = tool_input if isinstance(tool_input, dict) else {"value": tool_input}
        self._add_event("tool_start", "tool_start", text=str(tool), payload={"tool": tool, "input": payload})

    def on_tool_end(self, tool: str, output: Any, tool_call_id: Any = None) -> None:
        self.tool_names.add(str(tool))
        out_str = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        self.retrieved_context.append(f"Tool <{tool}> Output: {out_str}")
        payload = {"tool": tool, "tool_call_id": tool_call_id, "output": output}
        self._add_event("tool_end", "tool_end", text=str(tool), payload=payload)

    def on_done(self, final_output: str, error: Optional[str]) -> None:
        if error:
            self.status = "error"
            self.error = _clip(error, 4000)
            self._add_event("error", "error", text=self.error)
        else:
            self.status = "success"
        self._add_event("done", "done", text=_clip(final_output, 2000))

    def build_trace_dict(self) -> Dict[str, Any]:
        ended_at = datetime.now(timezone.utc)
        latency_ms = int((ended_at - self.started_at).total_seconds() * 1000)
        final_output = "".join(self.final_parts) if self.final_parts else None

        trace_data = {
            "trace_id": self.trace_id,
            "case_id": self.case_id,
            "session_id": self.session_id,
            "provider": self.provider,
            "model": self.model,
            "endpoint": self.endpoint,
            "started_at": _utc_iso(self.started_at),
            "ended_at": _utc_iso(ended_at),
            "latency_ms": latency_ms,
            "status": self.status,
            "error": self.error,
            "inputs": {"question": self.question},
            "final_output": final_output,
            "tags": {"shadow_eval": True, "capture": SHADOW_EVAL_CAPTURE},
            "meta": {
                "system_prompt": self.system_prompt[:500],
                "history_len": len(self.chat_history)
            },
        }

        # Bake Router Result directly into Trace
        if self._router_outcome:
            r = self._router_outcome
            trace_data["router_backend"] = r.get("backend")
            
            # Sentiment
            s = r.get("sentiment") or {}
            trace_data["router_sentiment"] = s.get("label")
            trace_data["router_sentiment_score"] = s.get("score")
            trace_data["router_override"] = s.get("overridden")
            
            # Reason
            rs = r.get("reason") or {}
            trace_data["router_reason"] = rs.get("label")
            trace_data["router_reason_score"] = rs.get("score")

        return trace_data

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
    out.append(_metric(trace_id, "AnswerNonEmpty", ok_out, 1.0 if ok_out else 0.0, "final_output is non-empty" if ok_out else "final_output empty"))

    ok_status = (trace.get("status") == "success") and not trace.get("error")
    out.append(_metric(trace_id, "StreamOk", ok_status, 1.0 if ok_status else 0.0, "status=success" if ok_status else f"error={trace.get('error')}"))

    rules = _load_rules()
    for r in rules:
        name = str(r.get("name") or "rule")
        when = r.get("when")
        if when:
            try:
                if not re.search(when, question, flags=re.I): continue
            except: continue

        req_tool = str(r.get("require_tool") or "").strip()
        if req_tool:
            has = req_tool in tool_names
            out.append(_metric(trace_id, f"ToolMatch({req_tool})", has, 1.0 if has else 0.0, f"Tool {req_tool} called" if has else "Missing tool call", meta={"rule": name}))

        pat = r.get("answer_pattern")
        if pat:
            try:
                m = re.search(pat, norm_out, flags=re.I)
                ok = m is not None
                out.append(_metric(trace_id, "NormalizedRegexMatch", ok, 1.0 if ok else 0.0, f"Matched pattern '{pat}'" if ok else f"Failed pattern", meta={"rule": name}))
            except Exception as e:
                out.append(_metric(trace_id, "RegexError", False, 0.0, str(e)))
    return out

async def compute_llm_metrics(
    trace: Dict[str, Any],
    collector: ShadowEvalCollector
) -> List[Dict[str, Any]]:
    
    if not ENABLE_LLM_JUDGE:
        return []

    trace_id = trace["trace_id"]
    question = trace.get("inputs", {}).get("question", "")
    answer = trace.get("final_output", "")
    
    tool_outputs = "\n\n".join(collector.retrieved_context) if collector.retrieved_context else "No tool outputs."
    history_str = "\n".join(collector.chat_history) if collector.chat_history else "No history."
    
    context_str = f"""
[SYSTEM INSTRUCTIONS]
{collector.system_prompt}

[AVAILABLE TOOLS]
{collector.tool_definitions}

[CHAT HISTORY (Last 5)]
{history_str}

[TOOL OUTPUTS / RETRIEVED CONTEXT]
{tool_outputs}
"""

    if not answer:
        return []

    results = []
    
    metrics_to_run = [
        ("relevance", question, answer, context_str),
        ("helpfulness", question, answer, context_str),
        ("faithfulness", question, answer, context_str),
        ("correctness", question, answer, context_str),
        ("coherence", question, answer, context_str),
    ]

    tasks = [
        judge_service.evaluate_pointwise(m, q, a, c) 
        for m, q, a, c in metrics_to_run
    ]
    
    eval_results = await asyncio.gather(*tasks)

    full_name = judge_service.model_name
    short_name = full_name.split("/", 1)[-1] if "/" in full_name else full_name
    judge_id = f"llm_judge:{short_name}"

    for res in eval_results:
        results.append({
            "eval_id": uuid.uuid4().hex,
            "trace_id": trace_id,
            "metric_name": res["metric_name"],
            "score": float(res["score"]),
            "passed": res["passed"],
            "reasoning": res["reasoning"],
            "evaluator_id": judge_id,
            "evidence": [],
            "meta": {"mode": "pointwise_g_eval"}
        })

    return results

async def _commit_bundle(trace: Dict[str, Any], events: List[Dict[str, Any]], evals: List[Dict[str, Any]]) -> None:
    await run_in_threadpool(STORE.upsert_trace, trace)
    if events:
        await run_in_threadpool(STORE.upsert_events, trace["trace_id"], events)
    if evals:
        await run_in_threadpool(STORE.upsert_evals, trace["trace_id"], evals)

async def maybe_shadow_eval_commit(collector: ShadowEvalCollector) -> None:
    try:
        if not await should_shadow_eval():
            return

        trace = collector.build_trace_dict()

        if SHADOW_EVAL_CAPTURE != "full":
            events = [e for e in collector.events if e.get("event_type") in ("tool_start", "tool_end", "error", "done")]
        else:
            events = collector.events

        evals = compute_non_llm_metrics(trace, events, collector.tool_names)
        llm_evals = await compute_llm_metrics(trace, collector)
        evals.extend(llm_evals)

        await _commit_bundle(trace, events, evals)

        # Trigger Embeddings for Vector Search
        try:
            # Fire-and-forget; don't block the main response if embedding is slow
            # embed_trace_if_needed is async, so we await it here
            await EMBEDDER.embed_trace_if_needed(trace, events)
            
            # Optionally embed results too
            for ev in evals:
                await EMBEDDER.embed_eval_if_needed(trace["trace_id"], ev)
        except Exception as e:
            log.warning(f"[shadow_eval] Embedding generation failed: {e}")

        log.info(f"[shadow_eval] committed trace_id={collector.trace_id} events={len(events)} evals={len(evals)}")
    except Exception as e:
        log.exception(f"[shadow_eval] commit failed: {e}")