"""ShadowEvalCollector: dataclass that captures trace events during agent execution."""

from __future__ import annotations

import json
import os
import re
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from langchain_core.messages import BaseMessage, HumanMessage

# ---------------------------------------------------------------------------
# Config (env) — collector-specific caps and capture modes
# ---------------------------------------------------------------------------
SHADOW_EVAL_CAPTURE = (os.getenv("SHADOW_EVAL_CAPTURE") or "light").strip().lower()
RUNTIME_TRACE_CAPTURE = (os.getenv("RUNTIME_TRACE_CAPTURE") or "full").strip().lower()

MAX_EVENTS = int((os.getenv("SHADOW_EVAL_MAX_EVENTS") or "500").strip())
MAX_TEXT = int((os.getenv("SHADOW_EVAL_MAX_TEXT") or "2000").strip())
MAX_FINAL = int((os.getenv("SHADOW_EVAL_MAX_FINAL") or "200000").strip())


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def _utc_iso(dt: Optional[datetime] = None) -> str:
    d = dt or datetime.now(timezone.utc)
    return d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _clip(s: Optional[str], n: int) -> str:
    if not s:
        return ""
    s = str(s)
    return s if len(s) <= n else s[:n] + f"…(truncated {len(s) - n} chars)"


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s or "")


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------
@dataclass
class ShadowEvalCollector:
    """Captures trace events, tool calls, and metadata for a single agent execution."""

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
    _inline_guard_decision: Optional[Dict[str, Any]] = None
    _eval_lifecycle: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def __init__(
        self,
        session_id: str,
        question: str,
        provider: Optional[str],
        model: Optional[str],
        endpoint: str,
        system_prompt: str = "",
        chat_history: List[BaseMessage] = None,  # type: ignore[assignment]
        tool_definitions: str = "",
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
        self._inline_guard_decision = None
        self._eval_lifecycle = {}

    def set_router_outcome(self, outcome: Dict[str, Any]) -> None:
        """Store the router result to be saved with the trace."""
        self._router_outcome = outcome

    def set_inline_guard_decision(self, decision: Dict[str, Any]) -> None:
        """Store inline guard decision metadata on the trace."""
        self._inline_guard_decision = decision

    def set_eval_lifecycle(
        self,
        branch: str,
        state: str,
        *,
        reason: Optional[str] = None,
        queued_at: Optional[str] = None,
    ) -> None:
        current = dict(self._eval_lifecycle.get(branch) or {})
        payload: Dict[str, Any] = {
            "state": state,
            "updated_at": _utc_iso(),
        }
        if reason:
            payload["reason"] = reason
        elif current.get("reason") and current.get("state") == state:
            payload["reason"] = current["reason"]

        if branch == "shadow":
            existing_queued_at = current.get("queued_at")
            if queued_at:
                payload["queued_at"] = queued_at
            elif state in {"queued", "failed", "worker_backlog", "timed_out", "complete"}:
                if existing_queued_at:
                    payload["queued_at"] = existing_queued_at

        self._eval_lifecycle[branch] = payload

    def mark_shadow_judge_queued(self) -> None:
        current = dict(self._eval_lifecycle.get("shadow") or {})
        self.set_eval_lifecycle(
            "shadow",
            "queued",
            reason="queued",
            queued_at=str(current.get("queued_at") or _utc_iso()),
        )

    def eval_lifecycle(self) -> Dict[str, Dict[str, Any]]:
        return deepcopy(self._eval_lifecycle)

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
        if len(self.events) >= MAX_EVENTS:
            return
        seq = self._next_seq()
        self.events.append(
            {
                "trace_id": self.trace_id,
                "seq": seq,
                "event_key": f"{self.trace_id}:{seq}",
                "ts": _utc_iso(),
                "event_type": event_type,
                "name": name,
                "text": _clip(text, MAX_TEXT),
                "payload": payload or {},
                "meta": meta or {},
            }
        )

    def _append_final(self, text: str) -> None:
        if not text:
            return
        cur_len = sum(len(x) for x in self.final_parts)
        if cur_len >= MAX_FINAL:
            return
        self.final_parts.append(text[: max(0, MAX_FINAL - cur_len)])

    # ---------- event helpers ----------
    def on_reasoning(self, token: str) -> None:
        if RUNTIME_TRACE_CAPTURE == "full":
            self._add_event("reasoning_token", "reasoning_token", text=token)

    def on_token(self, token: str) -> None:
        self._append_final(token)
        if RUNTIME_TRACE_CAPTURE == "full":
            self._add_event("token", "token", text=token)

    def on_tool_start(self, tool: str, tool_input: Any) -> None:
        self.tool_names.add(str(tool))
        payload = tool_input if isinstance(tool_input, dict) else {"value": tool_input}
        self._add_event(
            "tool_start", "tool_start", text=str(tool), payload={"tool": tool, "input": payload}
        )

    def on_tool_end(self, tool: str, output: Any, tool_call_id: Any = None) -> None:
        self.tool_names.add(str(tool))
        out_str = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        self.retrieved_context.append(f"Tool <{tool}> Output: {out_str}")
        payload = {"tool": tool, "tool_call_id": tool_call_id, "output": output}
        self._add_event("tool_end", "tool_end", text=str(tool), payload=payload)

    def on_done(self, final_output: str, error: Optional[str]) -> None:
        # Persist the canonical final output rather than raw streamed chunks.
        self.final_parts = [final_output] if final_output else []
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

        meta: Dict[str, Any] = {
            "system_prompt": self.system_prompt[:500],
            "history_len": len(self.chat_history),
        }

        eval_lifecycle = self.eval_lifecycle()
        if eval_lifecycle:
            meta["eval_lifecycle"] = eval_lifecycle

        if self._inline_guard_decision:
            meta["inline_guard"] = self._inline_guard_decision

        trace_data: Dict[str, Any] = {
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
            "tags": {
                "runtime_trace": True,
                "runtime_capture": RUNTIME_TRACE_CAPTURE,
                "shadow_eval_capture": SHADOW_EVAL_CAPTURE,
            },
            "meta": meta,
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
            # Defensive: when a router backend forgets the convention and
            # returns `reason: None`, the raw projection stored NULL in the DB,
            # which the dashboard's SQL CASE then misclassified as "other".
            # Fall back to "unknown" so the slug round-trips through the filter.
            rs = r.get("reason") or {}
            trace_data["router_reason"] = rs.get("label") or "unknown"
            trace_data["router_reason_score"] = rs.get("score") or 0.0

        return trace_data
