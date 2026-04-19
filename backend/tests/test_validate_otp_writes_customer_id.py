from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import fakeredis
import httpx
import pytest
import pytest_asyncio

from src.mcp_service import auth_api as auth_api_mod
from src.mcp_service import session_store as session_store_mod
from src.mcp_service.auth_api import MockFinTechAuthAPIs
from src.mcp_service.session_store import RedisSessionStore


@pytest_asyncio.fixture
async def fake_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[RedisSessionStore]:
    server = fakeredis.FakeServer()
    fake_client = fakeredis.FakeAsyncRedis(server=server, decode_responses=True)
    monkeypatch.setattr(session_store_mod, "_client", fake_client)
    yield RedisSessionStore()
    monkeypatch.setattr(session_store_mod, "_client", None)
    monkeypatch.setattr(session_store_mod, "_pool", None)


def _build_mock_client(responses: dict[str, httpx.Response]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        resp = responses.get(request.url.path)
        if resp is None:
            return httpx.Response(404, text=f"no stub for {request.url.path}")
        return resp

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_validate_otp_writes_customer_id_and_auth_state(
    fake_redis: RedisSessionStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After successful validate_otp, the session MUST carry an explicit
    ``customer_id`` anchor and ``auth_state="authenticated"`` flag.

    These two fields are the load-bearing contract downstream tools rely
    on — the decorator checks auth_state, the ownership helpers assert
    against customer_id. Without them the entire per-tool auth layer
    degrades silently to the old implicit-identity behaviour.
    """
    monkeypatch.setenv("BASIC_AUTH_USERNAME", "test")
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", "test")

    async def _mock_get_client() -> httpx.AsyncClient:
        return _build_mock_client(
            {
                "/mockfin-service/otp/validate_new/": httpx.Response(
                    200,
                    json={
                        "access_token": "tok_abc",
                        "user": {"id": "CUST-42", "name": "Test"},
                        "loans": [
                            {
                                "loan_number": "LN-001",
                                "status": "ACTIVE",
                                "product_code": "PL",
                            }
                        ],
                    },
                )
            }
        )

    monkeypatch.setattr(auth_api_mod, "_get_http_client", _mock_get_client)

    # Seed phone_number as generate_otp would have
    await fake_redis.set("sess_1", {"phone_number": "9999988888"})

    auth = MockFinTechAuthAPIs("sess_1", session_store=fake_redis)
    raw_result = await auth.validate_otp("123456")

    # Result text is VSC — just verify it looks like success.
    assert "success" in raw_result.lower()

    stored: dict[str, Any] = await fake_redis.get("sess_1") or {}
    assert stored.get("customer_id") == "CUST-42"
    assert stored.get("auth_state") == "authenticated"
    assert stored.get("access_token") == "tok_abc"
    assert stored.get("phone_number") == "9999988888"
    # Auto-select when exactly one loan
    assert stored.get("app_id") == "LN-001"
    assert len(stored.get("loans", [])) == 1


@pytest.mark.asyncio
async def test_validate_otp_customer_id_falls_back_to_customer_id_key(
    fake_redis: RedisSessionStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CRM historically used ``user.id`` but other deployments expose
    ``user.customer_id`` — the auth layer handles both."""
    monkeypatch.setenv("BASIC_AUTH_USERNAME", "test")
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", "test")

    async def _mock_get_client() -> httpx.AsyncClient:
        return _build_mock_client(
            {
                "/mockfin-service/otp/validate_new/": httpx.Response(
                    200,
                    json={
                        "access_token": "tok_xyz",
                        "user": {"customer_id": "ALT-99", "name": "Alt"},
                        "loans": [],
                    },
                )
            }
        )

    monkeypatch.setattr(auth_api_mod, "_get_http_client", _mock_get_client)

    await fake_redis.set("sess_alt", {"phone_number": "8888877777"})
    auth = MockFinTechAuthAPIs("sess_alt", session_store=fake_redis)
    _ = await auth.validate_otp("654321")

    stored = await fake_redis.get("sess_alt") or {}
    assert stored.get("customer_id") == "ALT-99"
    assert stored.get("auth_state") == "authenticated"


@pytest.mark.asyncio
async def test_validate_otp_failure_does_not_mark_authenticated(
    fake_redis: RedisSessionStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 401 from the CRM must leave ``auth_state`` unset so the decorator
    continues to reject downstream tool calls."""
    monkeypatch.setenv("BASIC_AUTH_USERNAME", "test")
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", "test")

    async def _mock_get_client() -> httpx.AsyncClient:
        return _build_mock_client(
            {
                "/mockfin-service/otp/validate_new/": httpx.Response(
                    401, text=json.dumps({"error": "bad otp"})
                )
            }
        )

    monkeypatch.setattr(auth_api_mod, "_get_http_client", _mock_get_client)

    await fake_redis.set("sess_fail", {"phone_number": "7777766666"})
    auth = MockFinTechAuthAPIs("sess_fail", session_store=fake_redis)
    _ = await auth.validate_otp("000000")

    stored = await fake_redis.get("sess_fail") or {}
    assert stored.get("auth_state") is None
    assert stored.get("customer_id") is None
    assert stored.get("access_token") is None
