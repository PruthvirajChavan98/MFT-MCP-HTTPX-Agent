from __future__ import annotations

from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

from src.agent_service.core.recursive_rag_graph import (
    build_recursive_rag_graph,
    initial_recursive_rag_state,
)


class _FakeModel:
    def __init__(self, responses: list[AIMessage]):
        self._responses = list(responses)

    def bind_tools(self, _tools: list[Any]):
        return self

    async def ainvoke(self, _messages: list[Any]) -> AIMessage:
        if not self._responses:
            raise AssertionError("No fake responses left for model invocation.")
        return self._responses.pop(0)


def _tool_call(tool_name: str, args: dict[str, Any], tool_call_id: str) -> dict[str, Any]:
    return {"name": tool_name, "args": args, "id": tool_call_id}


@pytest.mark.asyncio
async def test_same_turn_duplicate_generate_otp_executes_only_once():
    calls: list[str] = []

    async def _generate_otp(user_input: str) -> str:
        calls.append(user_input)
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
    graph = build_recursive_rag_graph(
        model=model,
        tools=[tool],
        system_prompt="system",
        checkpointer=None,
    )

    result = await graph.ainvoke(
        initial_recursive_rag_state("9657052655 login"),
        {"configurable": {"thread_id": "session-1"}},
    )

    assert calls == ["9657052655"]
    tool_messages = [
        message for message in result["messages"] if getattr(message, "type", "") == "tool"
    ]
    assert len(tool_messages) == 2
    assert tool_messages[0].content == tool_messages[1].content == "OTP sent to 9657052655"


@pytest.mark.asyncio
async def test_same_turn_dedupe_does_not_apply_to_different_generate_otp_inputs():
    calls: list[str] = []

    async def _generate_otp(user_input: str) -> str:
        calls.append(user_input)
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
                tool_calls=[_tool_call("generate_otp", {"user_input": "9876543210"}, "call-2")],
            ),
            AIMessage(content="OTP has been sent."),
        ]
    )
    graph = build_recursive_rag_graph(
        model=model,
        tools=[tool],
        system_prompt="system",
        checkpointer=None,
    )

    await graph.ainvoke(
        initial_recursive_rag_state("login"),
        {"configurable": {"thread_id": "session-1"}},
    )

    assert calls == ["9657052655", "9876543210"]


@pytest.mark.asyncio
async def test_generate_otp_can_run_again_on_a_later_turn():
    calls: list[str] = []

    async def _generate_otp(user_input: str) -> str:
        calls.append(user_input)
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
            AIMessage(content="OTP has been sent."),
            AIMessage(
                content="",
                tool_calls=[_tool_call("generate_otp", {"user_input": "9657052655"}, "call-2")],
            ),
            AIMessage(content="OTP resent."),
        ]
    )
    graph = build_recursive_rag_graph(
        model=model,
        tools=[tool],
        system_prompt="system",
        checkpointer=None,
    )

    await graph.ainvoke(
        initial_recursive_rag_state("login"),
        {"configurable": {"thread_id": "session-1"}},
    )
    await graph.ainvoke(
        initial_recursive_rag_state("resend otp"),
        {"configurable": {"thread_id": "session-1"}},
    )

    assert calls == ["9657052655", "9657052655"]
