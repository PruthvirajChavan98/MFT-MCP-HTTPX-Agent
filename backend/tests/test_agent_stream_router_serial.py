"""Regression: agent stream must run the router SERIALLY after the graph.

Prior to 2026-04-18 Phase D, the router was spawned as ``asyncio.create_task``
BEFORE ``graph.astream_events`` started. Its 4-6s of concurrent HTTP I/O
(embeddings, LLM fallback, answerability) interfered with
``langchain_mcp_adapters``' SSE consumer task on the same event loop — so MCP
tool results never returned to the graph, and the stream hung forever.

The fix moves the router call to AFTER the graph loop exits, wrapped in
``asyncio.wait_for(..., timeout=3.0)``. This test locks that invariant in
place so the concurrent-spawn pattern cannot regress.
"""

from __future__ import annotations

import asyncio
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from src.agent_service.api.endpoints import agent_stream
from src.agent_service.core.schemas import AgentRequest


class _FakeLimiterManager:
    async def get_agent_stream_limiter(self):
        return object()


class _FakePool:
    """asyncpg-like no-op for the fire-and-forget router UPDATE path."""

    async def execute(self, *args: Any, **kwargs: Any) -> str:
        return "UPDATE 1"


class _FakeRequest:
    scope: dict[str, Any] = {}

    def __init__(self) -> None:
        # Fire-and-forget router task calls
        # `http_request.app.state.pool.execute(...)` so fake the chain out.
        self.app = SimpleNamespace(state=SimpleNamespace(pool=_FakePool()))

    async def is_disconnected(self) -> bool:
        return False


class _FakeModel:
    def __init__(self, responses: list[AIMessage], call_log: list[str]):
        self._responses = list(responses)
        self._call_log = call_log

    def bind_tools(self, _tools: list[Any]):
        return self

    async def ainvoke(self, _messages: list[Any]) -> AIMessage:
        self._call_log.append("MODEL")
        if not self._responses:
            raise AssertionError("No fake model responses left.")
        return self._responses.pop(0)


class _FakeTracker:
    async def add_cost(self, **kwargs):
        return None


async def _noop(*args, **kwargs):
    return None


async def _fake_app_id(_session_id: str):
    return "tenant-1"


async def _async_decision(*, allow: bool, decision: str, reason_code: str, risk_score: float):
    return SimpleNamespace(
        allow=allow,
        decision=decision,
        reason_code=reason_code,
        risk_score=risk_score,
        as_dict=lambda: {
            "allow": allow,
            "decision": decision,
            "reason_code": reason_code,
            "risk_score": risk_score,
            "checks": [],
        },
    )


async def _persist_runtime_trace(_collector):
    return True


@pytest.mark.asyncio
async def test_router_runs_after_graph_not_concurrent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Router's classify must be awaited AFTER the graph loop finishes.

    We prove this with a shared ordered list — the fake model appends "MODEL"
    on each .ainvoke; the fake router appends "ROUTER". If the router were
    still spawned via asyncio.create_task pre-graph (the bug), ROUTER would
    appear before or interleaved with MODEL. In the correct post-graph
    serial ordering, every MODEL call happens before ROUTER.
    """
    call_log: list[str] = []

    # Model produces a simple final response (no tool calls) — keeps the
    # graph execution short + deterministic.
    model = _FakeModel([AIMessage(content="final answer")], call_log)

    async def _resolve_resources(*args, **kwargs):
        return SimpleNamespace(
            provider="groq",
            model_name="openai/gpt-oss-120b",
            system_prompt="system",
            tools=[_no_op_tool()],
            model=model,
            openrouter_api_key="fake-key",
            nvidia_api_key=None,
            groq_api_key=None,
        )

    async def _fake_router_classify(text, openrouter_api_key=None, tools=None, mode=None):
        # Record the call ordering + simulate ~50ms of work so any
        # accidental concurrent spawn would have a visible gap.
        call_log.append("ROUTER")
        await asyncio.sleep(0.01)
        return {
            "backend": "embeddings",
            "sentiment": {"label": "positive", "score": 0.9},
            "reason": {"label": "lead_intent_new_loan", "score": 0.8, "topk": []},
        }

    fake_router_service = SimpleNamespace(classify=_fake_router_classify)

    fake_main_agent = ModuleType("src.main_agent")
    fake_main_agent.app = SimpleNamespace(state=SimpleNamespace(checkpointer=None))

    monkeypatch.setattr(agent_stream, "get_rate_limiter_manager", lambda: _FakeLimiterManager())
    monkeypatch.setattr(agent_stream, "enforce_rate_limit", _noop)
    monkeypatch.setattr(agent_stream.session_utils, "validate_session_id", lambda sid: sid)
    monkeypatch.setattr(
        agent_stream.resource_resolver, "resolve_agent_resources", _resolve_resources
    )
    monkeypatch.setattr(agent_stream.session_utils, "get_app_id_for_session", _fake_app_id)
    # Router ENABLED — this is the point of the test.
    monkeypatch.setattr(agent_stream, "AGENT_INLINE_ROUTER_ENABLED", True)
    monkeypatch.setattr(agent_stream, "nbfc_router_service", fake_router_service)
    monkeypatch.setattr(
        agent_stream,
        "evaluate_prompt_safety_decision",
        lambda prompt: _async_decision(
            allow=True, decision="allow", reason_code="safe", risk_score=0.0
        ),
    )
    monkeypatch.setattr(agent_stream, "persist_runtime_trace", _persist_runtime_trace)
    monkeypatch.setattr(agent_stream, "get_session_cost_tracker", lambda: _FakeTracker())
    monkeypatch.setattr(agent_stream, "maybe_shadow_eval_commit", _noop)
    monkeypatch.setattr(agent_stream.trace_queue, "enqueue_trace", _noop)
    monkeypatch.setitem(sys.modules, "src.main_agent", fake_main_agent)

    req = AgentRequest(session_id="session-router-1", question="hello")
    response = await agent_stream.stream_agent(req, _FakeRequest())
    # Exhaust the stream. Router now runs FIRE-AND-FORGET via
    # `asyncio.create_task` in the generator's finally block — so when the
    # body_iterator is exhausted, the router task is scheduled but may not
    # have run yet. Sleep briefly to let it execute.
    async for _ in response.body_iterator:
        pass
    # Fire-and-forget router sleeps 250ms inside _classify_and_update_trace_router
    # (trace-persist race guard) before calling classify. 500ms here is plenty.
    await asyncio.sleep(0.5)

    # Core ordering invariant: every MODEL call happened before the ROUTER call.
    # This still holds — the router is spawned in `finally`, which runs AFTER
    # `async for event in event_stream:` (and therefore after all model calls).
    assert "MODEL" in call_log, f"model never called, log={call_log}"
    assert "ROUTER" in call_log, f"router never called, log={call_log}"
    last_model_idx = max(i for i, entry in enumerate(call_log) if entry == "MODEL")
    router_idx = call_log.index("ROUTER")
    assert router_idx > last_model_idx, (
        f"router fired concurrently with (or before) the model; " f"call order was {call_log}"
    )


def _no_op_tool() -> Any:
    """Minimal langchain tool stub so build_recursive_rag_graph accepts it."""
    from langchain_core.tools import StructuredTool

    async def _noop_impl() -> str:
        return "noop"

    return StructuredTool.from_function(
        func=None,
        coroutine=_noop_impl,
        name="noop_tool",
        description="A tool the model never calls in this test.",
    )
