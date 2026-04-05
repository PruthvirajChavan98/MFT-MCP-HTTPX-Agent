from __future__ import annotations

import pytest
from fastapi import FastAPI

from src.agent_service.core import app_factory as app_factory_module
from src.agent_service.core.prompts import prompt_manager
from src.agent_service.eval_store.pg_store import EvalSchemaUnavailableError
from src.common.milvus_mgr import milvus_mgr


class _FakeAsyncContextManager:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeAsyncRedisSaver:
    @staticmethod
    def from_conn_string(*args, **kwargs):
        return _FakeAsyncContextManager()


class _FakePostgresPoolManager:
    def __init__(self, dsn: str, min_size: int, max_size: int):
        self.dsn = dsn
        self.min_size = min_size
        self.max_size = max_size
        self.pool = object()

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None


@pytest.mark.asyncio
async def test_lifespan_fails_when_eval_schema_is_unavailable(monkeypatch):
    async def _noop_async(*args, **kwargs):
        return None

    async def _raise_schema_error(self, pool):
        raise EvalSchemaUnavailableError("eval_traces table not found")

    monkeypatch.setattr(app_factory_module, "AsyncRedisSaver", _FakeAsyncRedisSaver)
    monkeypatch.setattr(app_factory_module, "POSTGRES_DSN", "postgresql://test")
    monkeypatch.setattr(app_factory_module, "SECURITY_ENABLED", False)
    monkeypatch.setattr(app_factory_module, "initialize_http_client", _noop_async)
    monkeypatch.setattr(app_factory_module, "close_http_client", _noop_async)
    monkeypatch.setattr(app_factory_module, "close_redis", _noop_async)
    monkeypatch.setattr(app_factory_module, "PostgresPoolManager", _FakePostgresPoolManager)
    monkeypatch.setattr(app_factory_module.mcp_manager, "initialize", _noop_async)
    monkeypatch.setattr(app_factory_module.mcp_manager, "shutdown", _noop_async)
    monkeypatch.setattr(app_factory_module.model_service, "start_background_loop", _noop_async)
    monkeypatch.setattr(app_factory_module.event_bus, "close", _noop_async)
    monkeypatch.setattr(prompt_manager, "load", lambda: None)
    monkeypatch.setattr(milvus_mgr, "aconnect", _noop_async)
    monkeypatch.setattr(milvus_mgr, "close", _noop_async)
    monkeypatch.setattr(
        "src.agent_service.eval_store.pg_store.EvalPgStore.ensure_schema",
        _raise_schema_error,
    )

    factory = app_factory_module.AppFactory()
    app = FastAPI()

    with pytest.raises(EvalSchemaUnavailableError, match="eval_traces table not found"):
        async with factory.lifespan(app):
            pytest.fail("lifespan should not yield when eval schema verification fails")
