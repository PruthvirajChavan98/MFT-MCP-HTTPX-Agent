import pytest
import fakeredis
from src.mcp_service.session_store import RedisSessionStore

@pytest.fixture
def mock_redis(monkeypatch):
    # Mock the Redis client creation inside the class
    server = fakeredis.FakeServer()
    
    def fake_from_url(url, decode_responses=True):
        return fakeredis.FakeStrictRedis(server=server, decode_responses=decode_responses)
    
    monkeypatch.setattr("redis.from_url", fake_from_url)
    
    # Initialize store (it will use the fake redis)
    store = RedisSessionStore("redis://localhost:6379/0")
    return store

def test_set_and_get(mock_redis):
    data = {"user": "test", "token": "123"}
    mock_redis.set("sess_001", data)
    
    result = mock_redis.get("sess_001")
    assert result == data
    assert result["user"] == "test"

def test_get_missing_key(mock_redis):
    result = mock_redis.get("non_existent")
    assert result is None

def test_update_existing_session(mock_redis):
    mock_redis.set("sess_002", {"step": 1})
    mock_redis.update("sess_002", {"step": 2, "new_field": "ok"})
    
    result = mock_redis.get("sess_002")
    assert result["step"] == 2
    assert result["new_field"] == "ok"

def test_update_creates_if_missing(mock_redis):
    # Update on a missing key acts like set (starts with empty dict)
    mock_redis.update("sess_003", {"started": True})
    result = mock_redis.get("sess_003")
    assert result["started"] is True

def test_delete(mock_redis):
    mock_redis.set("sess_004", {"foo": "bar"})
    mock_redis.delete("sess_004")
    assert mock_redis.get("sess_004") is None

def test_invalid_session_ids(mock_redis):
    # Should safely do nothing or return None
    mock_redis.set(None, {})
    assert mock_redis.get(None) is None
    
    mock_redis.set("   ", {})
    assert mock_redis.get("   ") is None
