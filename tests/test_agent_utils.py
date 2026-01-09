import pytest
import json
from src.agent_service.utils import valid_session_id, normalize_result, keep_only_last_n_messages
from langchain_core.messages import HumanMessage, RemoveMessage

def test_valid_session_id():
    assert valid_session_id(" sess_123 ") == "sess_123"
    assert valid_session_id(12345) == "12345"

    with pytest.raises(ValueError):
        valid_session_id(None)
    
    with pytest.raises(ValueError):
        valid_session_id("   ")

    with pytest.raises(ValueError):
        valid_session_id("null")

def test_normalize_result_dict():
    # Small dict should be formatted nicely
    data = {"key": "value"}
    result = normalize_result(data)
    assert isinstance(result, str)
    assert "value" in result

    # Massive dict should be truncated
    massive = {"data": "x" * 10000}
    result = normalize_result(massive)
    assert "TRUNCATED" in result
    assert len(result) < 9000

def test_normalize_result_list_of_tools():
    # Simulating a tool output object that has a .text attribute
    class MockToolMessage:
        def __init__(self, text):
            self.text = text
    
    msg = MockToolMessage(text=json.dumps({"foo": "bar"}))
    result = normalize_result([msg])
    assert '"foo": "bar"' in result

def test_keep_only_last_n_messages():
    # Config is mocked as passing KEEP_LAST implicitly via the function's closure in real app,
    # but here we test the logic directly. Note: The actual function imports global config.
    # We assume config.KEEP_LAST is set (default 20).
    
    # Create 25 messages
    messages = [HumanMessage(content=f"msg {i}", id=str(i)) for i in range(25)]
    state = {"messages": messages}
    
    # Run reducer
    result = keep_only_last_n_messages(state, {})
    
    # Should return RemoveMessage for the first 5 (25 - 20)
    assert "messages" in result
    assert len(result["messages"]) == 5
    assert isinstance(result["messages"][0], RemoveMessage)
    assert result["messages"][0].id == "0"
    assert result["messages"][4].id == "4"
