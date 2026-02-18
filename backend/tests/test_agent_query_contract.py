from types import SimpleNamespace

from src.agent_service.api.endpoints.agent_query import _extract_final_response
from src.agent_service.core.streaming_utils import sse_formatter


def test_extract_final_response_from_state_messages_dict():
    state = {"messages": [{"content": "hello"}, {"content": "final answer"}]}
    assert _extract_final_response(state) == "final answer"


def test_extract_final_response_from_message_object():
    msg = SimpleNamespace(content=[{"text": "a"}, {"text": "b"}])
    assert _extract_final_response(msg) == "ab"


def test_public_streaming_event_formatters():
    thinking = sse_formatter.thinking_event("token")
    reasoning = sse_formatter.reasoning_token_event("token")
    tool_call = sse_formatter.tool_call_event("search_kb", "ok", "call-1")
    assert thinking == {"event": "reasoning", "data": "token"}
    assert reasoning == {"event": "reasoning", "data": "token"}
    assert tool_call["event"] == "tool_call"
    assert tool_call["data"]["name"] == "search_kb"
