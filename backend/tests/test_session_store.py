import fakeredis
import pytest
import pytest_asyncio

from src.mcp_service import session_store as session_store_mod
from src.mcp_service.session_store import RedisSessionStore


@pytest_asyncio.fixture
async def mock_redis(monkeypatch):
    """Provide a RedisSessionStore backed by fakeredis async client."""
    server = fakeredis.FakeServer()
    fake_client = fakeredis.FakeAsyncRedis(server=server, decode_responses=True)

    # Patch the module-level singleton so _redis() returns our fake
    monkeypatch.setattr(session_store_mod, "_client", fake_client)

    store = RedisSessionStore()
    yield store

    # Cleanup: reset module-level singleton
    monkeypatch.setattr(session_store_mod, "_client", None)
    monkeypatch.setattr(session_store_mod, "_pool", None)


@pytest.mark.asyncio
async def test_set_and_get(mock_redis):
    data = {"user": "test", "token": "123"}
    await mock_redis.set("sess_001", data)

    result = await mock_redis.get("sess_001")
    assert result == data
    assert result["user"] == "test"


@pytest.mark.asyncio
async def test_get_missing_key(mock_redis):
    result = await mock_redis.get("non_existent")
    assert result is None


@pytest.mark.asyncio
async def test_update_existing_session(mock_redis):
    await mock_redis.set("sess_002", {"step": 1})
    await mock_redis.update("sess_002", {"step": 2, "new_field": "ok"})

    result = await mock_redis.get("sess_002")
    assert result["step"] == 2
    assert result["new_field"] == "ok"


@pytest.mark.asyncio
async def test_update_creates_if_missing(mock_redis):
    # Update on a missing key acts like set (starts with empty dict)
    await mock_redis.update("sess_003", {"started": True})
    result = await mock_redis.get("sess_003")
    assert result["started"] is True


@pytest.mark.asyncio
async def test_delete(mock_redis):
    await mock_redis.set("sess_004", {"foo": "bar"})
    await mock_redis.delete("sess_004")
    assert await mock_redis.get("sess_004") is None


@pytest.mark.asyncio
async def test_invalid_session_ids(mock_redis):
    # Should safely do nothing or return None
    await mock_redis.set(None, {})
    assert await mock_redis.get(None) is None

    await mock_redis.set("   ", {})
    assert await mock_redis.get("   ") is None


@pytest.mark.asyncio
async def test_set_raw_with_ttl(mock_redis):
    await mock_redis.set_raw("dl_token:abc123", '{"data":"test"}', ex=600)
    r = await session_store_mod.get_redis()
    val = await r.get("dl_token:abc123")
    assert val == '{"data":"test"}'
