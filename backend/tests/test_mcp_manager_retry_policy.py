from __future__ import annotations

import pytest

import src.agent_service.tools.mcp_manager as mcp_manager_module
from src.agent_service.tools.mcp_manager import MCPManager


class _FakeRawTool:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls: list[dict] = []

    async def ainvoke(self, args):
        self.calls.append(dict(args))
        if not self._outcomes:
            raise AssertionError("No fake tool outcomes left.")
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


async def _noop_async(*_args, **_kwargs):
    return None


def _blueprint(manager: MCPManager, name: str, raw_tool: _FakeRawTool):
    args_schema = {
        "type": "object",
        "properties": {"user_input": {"type": "string"}},
        "required": [],
    }
    return {
        "name": name,
        "description": f"Tool: {name}",
        "safe_schema": manager._safe_schema_from_args_schema(name, args_schema),
        "raw_tool": raw_tool,
    }


@pytest.mark.asyncio
async def test_side_effect_tool_does_not_retry_transport_failure(monkeypatch):
    manager = MCPManager()
    raw_tool = _FakeRawTool([RuntimeError("network boom")])
    manager.tool_blueprints = [_blueprint(manager, "generate_otp", raw_tool)]

    monkeypatch.setattr(mcp_manager_module, "is_user_authenticated", lambda _sid: True)
    monkeypatch.setattr(manager, "shutdown", _noop_async)
    monkeypatch.setattr(manager, "initialize", _noop_async)

    tool = manager.rebuild_tools_for_user("session-1")[0]

    with pytest.raises(RuntimeError, match="network boom"):
        await tool.ainvoke({"user_input": "9657052655"})

    assert len(raw_tool.calls) == 1
    assert raw_tool.calls[0]["session_id"] == "session-1"


@pytest.mark.asyncio
async def test_read_only_tool_retries_once_after_reconnect(monkeypatch):
    manager = MCPManager()
    raw_tool = _FakeRawTool([RuntimeError("network boom"), "ok"])
    manager.tool_blueprints = [_blueprint(manager, "dashboard_home", raw_tool)]

    monkeypatch.setattr(mcp_manager_module, "is_user_authenticated", lambda _sid: True)
    monkeypatch.setattr(manager, "shutdown", _noop_async)
    monkeypatch.setattr(manager, "initialize", _noop_async)

    tool = manager.rebuild_tools_for_user("session-1")[0]
    result = await tool.ainvoke({"user_input": "ignored"})

    assert result == {"text": "ok"}
    assert len(raw_tool.calls) == 2
    assert all(call["session_id"] == "session-1" for call in raw_tool.calls)
