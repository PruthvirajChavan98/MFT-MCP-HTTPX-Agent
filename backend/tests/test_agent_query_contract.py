import sys
from types import ModuleType, SimpleNamespace

import pytest

from src.agent_service.api.endpoints import agent_query
from src.agent_service.api.endpoints.agent_query import _extract_final_response
from src.agent_service.core.schemas import AgentRequest
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


@pytest.mark.asyncio
async def test_query_agent_former_kb_first_question_uses_graph_path(monkeypatch):
    graph_calls: list[object] = []

    async def _resolve_resources(*args, **kwargs):
        return SimpleNamespace(
            provider="openrouter",
            model_name="dummy-model",
            system_prompt="system",
            tools=["mock_fintech_knowledge_base"],
            model=object(),
            openrouter_api_key="key",
            nvidia_api_key=None,
            groq_api_key=None,
            api_key="key",
        )

    class _FakeGraph:
        async def ainvoke(self, inputs, config):
            graph_calls.append((inputs, config))
            return {"messages": [{"content": "Graph answer"}]}

    fake_main_agent = ModuleType("src.main_agent")
    fake_main_agent.app = SimpleNamespace(state=SimpleNamespace(checkpointer=object()))

    monkeypatch.setattr(agent_query.session_utils, "validate_session_id", lambda sid: sid)
    monkeypatch.setattr(
        agent_query.resource_resolver, "resolve_agent_resources", _resolve_resources
    )
    monkeypatch.setattr(agent_query, "AGENT_INLINE_ROUTER_ENABLED", False)
    monkeypatch.setattr(agent_query, "build_recursive_rag_graph", lambda **kwargs: _FakeGraph())
    monkeypatch.setitem(sys.modules, "src.main_agent", fake_main_agent)

    response = await agent_query.query_agent(
        AgentRequest(session_id="session-1", question="stop my emi")
    )

    assert len(graph_calls) == 1
    graph_input, graph_config = graph_calls[0]
    assert graph_input["messages"][0].content == "stop my emi"
    assert graph_config == {"configurable": {"thread_id": "session-1"}}
    assert response == {
        "response": "Graph answer",
        "provider": "openrouter",
        "model": "dummy-model",
        "kb_first": False,
    }
