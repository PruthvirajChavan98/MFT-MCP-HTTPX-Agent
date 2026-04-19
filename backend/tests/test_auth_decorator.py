from __future__ import annotations

import inspect
from collections.abc import AsyncIterator

import fakeredis
import pytest
import pytest_asyncio

from src.mcp_service import auth_decorators as auth_decorators_mod
from src.mcp_service import session_store as session_store_mod
from src.mcp_service.auth_decorators import (
    AUTH_REJECT_MESSAGE,
    requires_authenticated_session,
)
from src.mcp_service.session_context import SessionContext
from src.mcp_service.session_store import RedisSessionStore


@pytest_asyncio.fixture
async def wired_session_store(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[RedisSessionStore]:
    server = fakeredis.FakeServer()
    fake_client = fakeredis.FakeAsyncRedis(server=server, decode_responses=True)
    monkeypatch.setattr(session_store_mod, "_client", fake_client)

    store = RedisSessionStore()
    # Redirect the decorator's default singleton to use the same fake backend
    # so the decorated tool and the fixture see the same session data.
    monkeypatch.setattr(auth_decorators_mod, "_default_session_store", store)
    yield store

    monkeypatch.setattr(session_store_mod, "_client", None)
    monkeypatch.setattr(session_store_mod, "_pool", None)


def _authenticated_dict() -> dict:
    return {
        "customer_id": "CUST-42",
        "phone_number": "9999988888",
        "access_token": "tok_abc",
        "loans": [{"loan_number": "LN-001", "status": "ACTIVE", "product_code": "PL"}],
        "app_id": "LN-001",
        "user_details": {"id": "CUST-42"},
        "auth_state": "authenticated",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Signature contract
# ─────────────────────────────────────────────────────────────────────────────


def test_decorator_requires_ctx_param() -> None:
    with pytest.raises(TypeError, match="ctx"):

        @requires_authenticated_session
        async def bad_tool(session_id: str) -> str:  # type: ignore[misc]
            return "never called"


def test_decorator_preserves_mcp_facing_signature_session_id() -> None:
    @requires_authenticated_session
    async def my_tool(ctx: SessionContext) -> str:
        return "ok"

    sig = inspect.signature(my_tool)
    assert "session_id" in sig.parameters
    assert "ctx" not in sig.parameters
    assert sig.parameters["session_id"].annotation is str


def test_decorator_preserves_extra_params() -> None:
    @requires_authenticated_session
    async def my_tool(loan_number: str, ctx: SessionContext) -> str:
        return f"loan={loan_number}"

    sig = inspect.signature(my_tool)
    assert list(sig.parameters.keys()) == ["loan_number", "session_id"]


# ─────────────────────────────────────────────────────────────────────────────
# Runtime rejection paths
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_decorator_rejects_empty_session_id(
    wired_session_store: RedisSessionStore,
) -> None:
    @requires_authenticated_session
    async def my_tool(ctx: SessionContext) -> str:
        return "ok"

    result = await my_tool(session_id="")
    assert result == AUTH_REJECT_MESSAGE


@pytest.mark.asyncio
async def test_decorator_rejects_none_session_id(
    wired_session_store: RedisSessionStore,
) -> None:
    @requires_authenticated_session
    async def my_tool(ctx: SessionContext) -> str:
        return "ok"

    result = await my_tool(session_id=None)  # type: ignore[arg-type]
    assert result == AUTH_REJECT_MESSAGE


@pytest.mark.asyncio
async def test_decorator_rejects_unknown_session(
    wired_session_store: RedisSessionStore,
) -> None:
    @requires_authenticated_session
    async def my_tool(ctx: SessionContext) -> str:
        return "ok"

    result = await my_tool(session_id="nonexistent")
    assert result == AUTH_REJECT_MESSAGE


@pytest.mark.asyncio
async def test_decorator_rejects_pending_auth_state(
    wired_session_store: RedisSessionStore,
) -> None:
    @requires_authenticated_session
    async def my_tool(ctx: SessionContext) -> str:
        return "ok"

    # generate_otp wrote the phone but hasn't validated yet — no auth_state yet.
    await wired_session_store.set("sess_pending", {"phone_number": "9999988888"})

    result = await my_tool(session_id="sess_pending")
    assert result == AUTH_REJECT_MESSAGE


@pytest.mark.asyncio
async def test_decorator_rejects_malformed_authenticated_session(
    wired_session_store: RedisSessionStore,
) -> None:
    @requires_authenticated_session
    async def my_tool(ctx: SessionContext) -> str:
        return "ok"

    # auth_state says authenticated but customer_id is missing — should still
    # reject rather than crash or pass an incomplete context through.
    bad = _authenticated_dict()
    bad["customer_id"] = ""
    await wired_session_store.set("sess_bad", bad)

    result = await my_tool(session_id="sess_bad")
    assert result == AUTH_REJECT_MESSAGE


# ─────────────────────────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_decorator_injects_session_context_on_happy_path(
    wired_session_store: RedisSessionStore,
) -> None:
    seen_ctx: SessionContext | None = None

    @requires_authenticated_session
    async def my_tool(ctx: SessionContext) -> str:
        nonlocal seen_ctx
        seen_ctx = ctx
        return f"hello {ctx.customer_id}"

    await wired_session_store.set("sess_good", _authenticated_dict())

    result = await my_tool(session_id="sess_good")
    assert result == "hello CUST-42"
    assert seen_ctx is not None
    assert seen_ctx.session_id == "sess_good"
    assert seen_ctx.app_id == "LN-001"
    assert seen_ctx.loans[0].loan_number == "LN-001"


@pytest.mark.asyncio
async def test_decorator_passes_through_extra_positional_args(
    wired_session_store: RedisSessionStore,
) -> None:
    @requires_authenticated_session
    async def my_tool(loan_number: str, ctx: SessionContext) -> str:
        return f"loan={loan_number} customer={ctx.customer_id}"

    await wired_session_store.set("sess_good", _authenticated_dict())

    # MCP invocations arrive by keyword — match that call-site.
    result = await my_tool(loan_number="LN-001", session_id="sess_good")
    assert result == "loan=LN-001 customer=CUST-42"


@pytest.mark.asyncio
async def test_decorator_updates_last_tool_audit_trail(
    wired_session_store: RedisSessionStore,
) -> None:
    @requires_authenticated_session
    async def loan_details(ctx: SessionContext) -> str:
        return "details"

    await wired_session_store.set("sess_good", _authenticated_dict())
    await loan_details(session_id="sess_good")

    refreshed = await wired_session_store.get("sess_good")
    assert refreshed is not None
    assert refreshed["_last_tool"] == "loan_details"
    assert "_last_touch_ts" in refreshed
