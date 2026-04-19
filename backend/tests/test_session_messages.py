"""Tests for GET /agent/sessions/{session_id}/messages endpoint."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Optional

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import src.agent_service.api.endpoints.sessions as sessions_mod


class _FakeCheckpointTuple:
    def __init__(self, checkpoint: dict[str, Any]) -> None:
        self.checkpoint = checkpoint
        self.config = {"configurable": {"thread_id": "sess-1"}}


class _FakeCheckpointer:
    def __init__(self, checkpoint: Optional[dict[str, Any]] = None) -> None:
        self._checkpoint = checkpoint

    async def aget_tuple(self, config: dict) -> Optional[_FakeCheckpointTuple]:
        if self._checkpoint is None:
            return None
        return _FakeCheckpointTuple(self._checkpoint)


@pytest.mark.asyncio
async def test_session_messages_returns_human_and_ai_messages():
    """Endpoint transforms LangChain messages into frontend ChatMessage shape."""
    ai_msg = AIMessage(
        content="Your EMI is ₹12,500.",
        additional_kwargs={
            "trace_id": "trace-abc",
            "provider": "groq",
            "model": "openai/gpt-oss-120b",
            "total_tokens": 350,
        },
        response_metadata={
            "created": 1712345678.0,
            "model_name": "openai/gpt-oss-120b",
            "model_provider": "groq",
        },
    )
    checkpoint = {
        "channel_values": {
            "messages": [
                HumanMessage(content="What is my EMI?"),
                ai_msg,
            ],
        },
    }
    checkpointer = _FakeCheckpointer(checkpoint)
    fake_app = SimpleNamespace(state=SimpleNamespace(checkpointer=checkpointer))
    request = SimpleNamespace(app=fake_app)

    response = await sessions_mod.get_session_messages(
        session_id="sess-1",
        request=request,
        limit=120,
    )

    assert response["session_id"] == "sess-1"
    assert len(response["messages"]) == 2

    user_msg = response["messages"][0]
    assert user_msg["role"] == "user"
    assert user_msg["content"] == "What is my EMI?"
    assert user_msg["status"] == "done"

    assistant_msg = response["messages"][1]
    assert assistant_msg["role"] == "assistant"
    assert assistant_msg["content"] == "Your EMI is ₹12,500."
    assert assistant_msg["traceId"] == "trace-abc"
    assert assistant_msg["provider"] == "groq"
    assert assistant_msg["model"] == "openai/gpt-oss-120b"
    assert assistant_msg["totalTokens"] == 350
    assert assistant_msg["timestamp"] == 1712345678000


@pytest.mark.asyncio
async def test_session_messages_returns_empty_for_missing_checkpoint():
    """Endpoint returns empty messages when checkpoint does not exist."""
    checkpointer = _FakeCheckpointer(checkpoint=None)
    fake_app = SimpleNamespace(state=SimpleNamespace(checkpointer=checkpointer))
    request = SimpleNamespace(app=fake_app)

    response = await sessions_mod.get_session_messages(
        session_id="sess-unknown",
        request=request,
        limit=120,
    )

    assert response["session_id"] == "sess-unknown"
    assert response["messages"] == []


@pytest.mark.asyncio
async def test_session_messages_skips_empty_ai_messages():
    """Tool-call-only AIMessages (empty content) are filtered to avoid blank bubbles."""
    tool_call_only = AIMessage(
        content="",
        tool_calls=[{"id": "call_1", "name": "select_loan", "args": {"loan_id": "X"}}],
    )
    final_answer = AIMessage(content="Your loan is selected.")

    checkpoint = {
        "channel_values": {
            "messages": [
                HumanMessage(content="Select my loan."),
                tool_call_only,
                final_answer,
            ],
        },
    }
    checkpointer = _FakeCheckpointer(checkpoint)
    fake_app = SimpleNamespace(state=SimpleNamespace(checkpointer=checkpointer))
    request = SimpleNamespace(app=fake_app)

    response = await sessions_mod.get_session_messages(
        session_id="sess-empty",
        request=request,
        limit=120,
    )

    assert len(response["messages"]) == 2
    assert response["messages"][0]["role"] == "user"
    assert response["messages"][1]["role"] == "assistant"
    assert response["messages"][1]["content"] == "Your loan is selected."


@pytest.mark.asyncio
async def test_session_messages_skips_ai_messages_with_list_empty_content():
    """Anthropic-style AIMessages with list content of only empty blocks are filtered."""
    ai_empty_blocks = AIMessage(content=[{"type": "text", "text": ""}])  # type: ignore[arg-type]
    ai_real_blocks = AIMessage(content=[{"type": "text", "text": "Here is the answer."}])  # type: ignore[arg-type]

    checkpoint = {
        "channel_values": {
            "messages": [
                HumanMessage(content="question"),
                ai_empty_blocks,
                ai_real_blocks,
            ],
        },
    }
    checkpointer = _FakeCheckpointer(checkpoint)
    fake_app = SimpleNamespace(state=SimpleNamespace(checkpointer=checkpointer))
    request = SimpleNamespace(app=fake_app)

    response = await sessions_mod.get_session_messages(
        session_id="sess-blocks",
        request=request,
        limit=120,
    )

    assert len(response["messages"]) == 2
    assert response["messages"][1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_session_messages_skips_tool_messages():
    """Tool messages are filtered out — frontend displays them inline via SSE."""
    from langchain_core.messages import ToolMessage

    checkpoint = {
        "channel_values": {
            "messages": [
                HumanMessage(content="Show my loan details"),
                ToolMessage(content="tool output", tool_call_id="tc-1"),
                AIMessage(content="Here are your loan details."),
            ],
        },
    }
    checkpointer = _FakeCheckpointer(checkpoint)
    fake_app = SimpleNamespace(state=SimpleNamespace(checkpointer=checkpointer))
    request = SimpleNamespace(app=fake_app)

    response = await sessions_mod.get_session_messages(
        session_id="sess-2",
        request=request,
        limit=120,
    )

    assert len(response["messages"]) == 2
    assert response["messages"][0]["role"] == "user"
    assert response["messages"][1]["role"] == "assistant"
