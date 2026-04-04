from __future__ import annotations

import json
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

from src.agent_service.api.endpoints import agent_stream
from src.agent_service.core.schemas import AgentRequest


class _FakeLimiterManager:
    async def get_agent_stream_limiter(self):
        return object()


class _FakeRequest:
    scope = {}

    async def is_disconnected(self) -> bool:
        return False


class _FakeModel:
    def __init__(self, responses: list[AIMessage]):
        self._responses = list(responses)

    def bind_tools(self, _tools: list[Any]):
        return self

    async def ainvoke(self, _messages: list[Any]) -> AIMessage:
        if not self._responses:
            raise AssertionError("No fake model responses left.")
        return self._responses.pop(0)


def _tool_call(tool_name: str, args: dict[str, Any], tool_call_id: str) -> dict[str, Any]:
    return {"name": tool_name, "args": args, "id": tool_call_id}


async def _noop_enforce(*args, **kwargs):
    return None


async def _noop_shadow_eval(*args, **kwargs):
    return None


async def _noop_enqueue_trace(*args, **kwargs):
    return None


async def _persist_runtime_trace(_collector):
    return True


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


class _FakeTracker:
    async def add_cost(self, **kwargs):
        return None


@pytest.mark.asyncio
async def test_stream_agent_emits_one_public_tool_call_for_same_turn_duplicate_generate_otp(
    monkeypatch,
):
    otp_calls: list[str] = []

    async def _generate_otp(user_input: str) -> str:
        otp_calls.append(user_input)
        return f"OTP sent to {user_input}"

    tool = StructuredTool.from_function(
        func=None,
        coroutine=_generate_otp,
        name="generate_otp",
        description="Send OTP",
    )
    model = _FakeModel(
        [
            AIMessage(
                content="",
                tool_calls=[_tool_call("generate_otp", {"user_input": "9657052655"}, "call-1")],
            ),
            AIMessage(
                content="",
                tool_calls=[_tool_call("generate_otp", {"user_input": "9657052655"}, "call-2")],
            ),
            AIMessage(content="OTP has been sent."),
        ]
    )

    async def _resolve_resources(*args, **kwargs):
        return SimpleNamespace(
            provider="groq",
            model_name="openai/gpt-oss-120b",
            system_prompt="system",
            tools=[tool],
            model=model,
            openrouter_api_key=None,
            nvidia_api_key=None,
            groq_api_key="key",
        )

    fake_main_agent = ModuleType("src.main_agent")
    fake_main_agent.app = SimpleNamespace(state=SimpleNamespace(checkpointer=None))

    monkeypatch.setattr(agent_stream, "get_rate_limiter_manager", lambda: _FakeLimiterManager())
    monkeypatch.setattr(agent_stream, "enforce_rate_limit", _noop_enforce)
    monkeypatch.setattr(agent_stream.session_utils, "validate_session_id", lambda sid: sid)
    monkeypatch.setattr(
        agent_stream.resource_resolver, "resolve_agent_resources", _resolve_resources
    )
    monkeypatch.setattr(agent_stream.session_utils, "get_app_id_for_session", _fake_app_id)
    monkeypatch.setattr(agent_stream, "AGENT_INLINE_ROUTER_ENABLED", False)
    monkeypatch.setattr(
        agent_stream,
        "evaluate_prompt_safety_decision",
        lambda prompt: _async_decision(
            allow=True,
            decision="allow",
            reason_code="safe",
            risk_score=0.0,
        ),
    )
    monkeypatch.setattr(agent_stream, "persist_runtime_trace", _persist_runtime_trace)
    monkeypatch.setattr(agent_stream, "get_session_cost_tracker", lambda: _FakeTracker())
    monkeypatch.setattr(agent_stream, "maybe_shadow_eval_commit", _noop_shadow_eval)
    monkeypatch.setattr(agent_stream.trace_queue, "enqueue_trace", _noop_enqueue_trace)
    monkeypatch.setitem(sys.modules, "src.main_agent", fake_main_agent)

    req = AgentRequest(session_id="session-1", question="9657052655 login")
    response = await agent_stream.stream_agent(req, _FakeRequest())
    events = [chunk async for chunk in response.body_iterator]

    tool_call_events = [chunk for chunk in events if chunk["event"] == "tool_call"]
    assert len(tool_call_events) == 1
    payload = json.loads(tool_call_events[0]["data"])
    assert payload["name"] == "generate_otp"
    assert payload["output"] == "OTP sent to 9657052655"
    assert isinstance(payload["tool_call_id"], str)
    assert payload["tool_call_id"]
    assert otp_calls == ["9657052655"]
