"""Regression tests for admin `session_traces` handler's empty-content filter.

Mirrors the filter the public widget's `get_session_messages` already applies.
Without this, LangGraph's intermediate tool-calling AIMessages (empty content,
only tool_calls populated) rendered as standalone bubbles with empty Reasoning
+ Raw tool calls disclosures on the admin Conversations transcript.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

import src.agent_service.api.admin_analytics.traces as traces_mod


class _FakeCheckpointTuple:
    def __init__(self, messages: list[Any]) -> None:
        self.checkpoint = {"channel_values": {"messages": messages}}
        self.config = {"configurable": {"thread_id": "sess-test"}}


class _FakeCheckpointer:
    def __init__(self, messages: list[Any]) -> None:
        self._messages = messages

    async def aget_tuple(self, _config: dict) -> _FakeCheckpointTuple:
        return _FakeCheckpointTuple(self._messages)


def _fake_request(messages: list[Any]) -> SimpleNamespace:
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                checkpointer=_FakeCheckpointer(messages),
                pool=object(),
            )
        )
    )


def _ai_tool_call(name: str, tc_id: str, args: dict[str, Any] | None = None) -> AIMessage:
    """AIMessage with only a tool_calls request (empty content)."""
    return AIMessage(
        content="",
        tool_calls=[{"id": tc_id, "name": name, "args": args or {}}],
    )


@pytest.mark.asyncio
async def test_session_traces_collapses_multiple_tool_call_turns() -> None:
    """Two consecutive tool-calling AIMessages + final answer → ONE assistant bubble
    with BOTH tools merged into toolCalls.
    """
    messages = [
        HumanMessage(content="i have completed it"),
        _ai_tool_call("is_logged_in", tc_id="call-a"),
        ToolMessage(content="true", tool_call_id="call-a"),
        _ai_tool_call("select_loan", tc_id="call-b"),
        ToolMessage(content='{"loan_id": "MOCK-TWL"}', tool_call_id="call-b"),
        AIMessage(content="Your active loan (MOCK-TWL) is now selected."),
    ]

    result = await traces_mod.session_traces(
        request=_fake_request(messages),
        session_id="sess-test",
        limit=500,
    )
    items = result["items"]

    # Expect exactly 2 items: user + merged final assistant
    assert len(items) == 2, f"expected 2 items, got {len(items)}: {items}"
    assert items[0]["role"] == "user"
    assert items[1]["role"] == "assistant"
    assert items[1]["content"] == "Your active loan (MOCK-TWL) is now selected."

    tool_calls = items[1].get("toolCalls") or []
    tool_names = {tc.get("name") for tc in tool_calls}
    assert tool_names == {
        "is_logged_in",
        "select_loan",
    }, f"both tool calls must fold onto the final bubble; got {tool_names}"


@pytest.mark.asyncio
async def test_session_traces_legacy_single_tool_call_still_merges() -> None:
    """Pre-existing binary case: one tool-call turn + final answer → 1 merged bubble."""
    messages = [
        HumanMessage(content="what loans do you offer?"),
        _ai_tool_call("search_knowledge_base", tc_id="call-k"),
        ToolMessage(content="loan info", tool_call_id="call-k"),
        AIMessage(content="We offer two-wheeler and MSME loans."),
    ]

    result = await traces_mod.session_traces(
        request=_fake_request(messages),
        session_id="sess-test",
        limit=500,
    )
    items = result["items"]

    assert len(items) == 2
    assert items[1]["role"] == "assistant"
    assert items[1]["content"] == "We offer two-wheeler and MSME loans."
    tool_names = {tc.get("name") for tc in (items[1].get("toolCalls") or [])}
    assert tool_names == {"search_knowledge_base"}


@pytest.mark.asyncio
async def test_session_traces_filters_anthropic_list_content_when_empty() -> None:
    """AIMessage with Anthropic-style list content of only empty blocks is treated
    as empty (same semantics as the public widget's filter)."""
    empty_blocks_tool_call = AIMessage(
        content=[{"type": "text", "text": ""}],  # type: ignore[arg-type]
        tool_calls=[{"id": "call-x", "name": "get_profile", "args": {}}],
    )
    messages = [
        HumanMessage(content="profile?"),
        empty_blocks_tool_call,
        ToolMessage(content='{"name": "ant"}', tool_call_id="call-x"),
        AIMessage(content=[{"type": "text", "text": "Your name is ant."}]),  # type: ignore[arg-type]
    ]

    result = await traces_mod.session_traces(
        request=_fake_request(messages),
        session_id="sess-test",
        limit=500,
    )
    items = result["items"]

    # Empty-blocks intermediate must be folded; 2 items (user + final).
    assert len(items) == 2
    assert items[1]["role"] == "assistant"
    tool_names = {tc.get("name") for tc in (items[1].get("toolCalls") or [])}
    assert tool_names == {"get_profile"}


@pytest.mark.asyncio
async def test_session_traces_preserves_trailing_tool_calls_without_final_answer() -> None:
    """Truncated stream: tool-call intermediates with no final answer should still
    surface a synthetic bubble so the audit trail is preserved."""
    messages = [
        HumanMessage(content="hi"),
        _ai_tool_call("is_logged_in", tc_id="call-only"),
        ToolMessage(content="true", tool_call_id="call-only"),
        # No final AIMessage with content — simulating a truncated / cancelled run.
    ]

    result = await traces_mod.session_traces(
        request=_fake_request(messages),
        session_id="sess-test",
        limit=500,
    )
    items = result["items"]

    # user + synthetic trailing assistant
    assert len(items) == 2
    assert items[0]["role"] == "user"
    assert items[1]["role"] == "assistant"
    tool_names = {tc.get("name") for tc in (items[1].get("toolCalls") or [])}
    assert "is_logged_in" in tool_names
