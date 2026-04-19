"""Per-tool authorization regression corpus.

For every MCP tool that wears ``@requires_authenticated_session``,
this file locks down the behaviour against a matrix of attack scenarios:

- ``missing_session``      — session_id doesn't exist in Redis
- ``unauthenticated``      — session exists but auth_state != "authenticated"
- ``empty_session_id``     — blank / None session_id
- ``tampered_app_id``      — authenticated session, but app_id points to a
                             loan that is NOT in session.loans
- ``cross_session_loan``   — select_loan called with a loan_number from a
                             DIFFERENT customer's session

Every authenticated tool must return the canonical AUTH_REJECT_MESSAGE on
the first three; tools that resolve an active loan via
``active_loan_or_raise`` must return the ownership-rejection text on the
``tampered_app_id`` case; ``select_loan`` must reject cross-session loan
references.

Happy-path tests confirm the decorator lets legitimate calls through
(verified by mocking ``get_api`` and observing the stub's return value).

Adding a new authenticated tool without a matching corpus entry is a
CI-caught oversight — inspect the AUTHENTICATED_TOOLS list to ensure
coverage stays complete.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Callable

import fakeredis
import pytest
import pytest_asyncio

from src.mcp_service import auth_decorators as auth_decorators_mod
from src.mcp_service import server as server_mod
from src.mcp_service import session_store as session_store_mod
from src.mcp_service.auth_decorators import AUTH_REJECT_MESSAGE
from src.mcp_service.session_store import RedisSessionStore

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

CUSTOMER_A_SESSION = "sess_customer_a"
CUSTOMER_B_SESSION = "sess_customer_b"

CUSTOMER_A_LOAN = "LN-A1"
CUSTOMER_B_LOAN = "LN-B1"


def _authenticated_dict(
    *,
    customer_id: str,
    loans: list[dict[str, Any]],
    app_id: str | None,
) -> dict[str, Any]:
    return {
        "customer_id": customer_id,
        "phone_number": f"99999{customer_id[-5:].rjust(5, '0')}",
        "access_token": f"tok_{customer_id}",
        "loans": loans,
        "app_id": app_id,
        "user_details": {"id": customer_id},
        "auth_state": "authenticated",
    }


@pytest_asyncio.fixture
async def two_sessions_store(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[RedisSessionStore]:
    """Wire fakeredis in place of the real Redis and seed two fully
    authenticated customer sessions. Each customer owns ONE loan; tests
    then deliberately try to cross the streams."""
    server = fakeredis.FakeServer()
    fake_client = fakeredis.FakeAsyncRedis(server=server, decode_responses=True)
    monkeypatch.setattr(session_store_mod, "_client", fake_client)

    store = RedisSessionStore()
    monkeypatch.setattr(auth_decorators_mod, "_default_session_store", store)
    # server.py's module-level singleton also has to point at our fake
    # backend — select_loan/logout/list_loans write via it directly.
    monkeypatch.setattr(server_mod, "session_store", store)

    await store.set(
        CUSTOMER_A_SESSION,
        _authenticated_dict(
            customer_id="CUST-A",
            loans=[
                {
                    "loan_number": CUSTOMER_A_LOAN,
                    "status": "ACTIVE",
                    "product_code": "PL",
                }
            ],
            app_id=CUSTOMER_A_LOAN,
        ),
    )
    await store.set(
        CUSTOMER_B_SESSION,
        _authenticated_dict(
            customer_id="CUST-B",
            loans=[
                {
                    "loan_number": CUSTOMER_B_LOAN,
                    "status": "ACTIVE",
                    "product_code": "PL",
                }
            ],
            app_id=CUSTOMER_B_LOAN,
        ),
    )
    yield store

    monkeypatch.setattr(session_store_mod, "_client", None)
    monkeypatch.setattr(session_store_mod, "_pool", None)


class _StubCoreAPI:
    """Stand-in for ``MockFinTechAPIs``. Every method returns a tagged
    string so tests can tell the real call-site forwarded through."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id

    async def get_dashboard_home(self) -> str:
        return f"__STUB_DASHBOARD__{self.session_id}"

    async def get_loan_details(self) -> str:
        return f"__STUB_LOAN_DETAILS__{self.session_id}"

    async def get_foreclosure_details(self) -> str:
        return f"__STUB_FORECLOSURE__{self.session_id}"

    async def get_overdue_details(self) -> str:
        return f"__STUB_OVERDUE__{self.session_id}"

    async def get_noc_details(self) -> str:
        return f"__STUB_NOC__{self.session_id}"

    async def get_repayment_schedule(self) -> str:
        return f"__STUB_REPAYMENT__{self.session_id}"

    async def download_welcome_letter(self) -> str:
        return f"__STUB_WELCOME__{self.session_id}"

    async def download_soa(self, start_date: str, end_date: str) -> str:
        return f"__STUB_SOA__{self.session_id}__{start_date}__{end_date}"


@pytest.fixture
def stubbed_core_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server_mod, "get_api", lambda sid: _StubCoreAPI(sid))


# ─────────────────────────────────────────────────────────────────────────────
# Tool catalogue
#
# Each entry:
#   name:        MCP tool name
#   call:        Async callable invoked with kwargs
#   extra_args:  Kwargs passed in addition to session_id (tool-specific)
#   uses_app_id: Tool calls active_loan_or_raise → tampered_app_id applies
# ─────────────────────────────────────────────────────────────────────────────


def _call(tool_name: str) -> Callable[..., Any]:
    tool_obj = getattr(server_mod, tool_name)
    return tool_obj.fn


AUTHENTICATED_TOOLS: list[tuple[str, Callable[..., Any], dict[str, Any], bool]] = [
    ("is_logged_in", _call("is_logged_in"), {}, False),
    ("list_loans", _call("list_loans"), {}, False),
    (
        "select_loan",
        _call("select_loan"),
        {"loan_number": CUSTOMER_A_LOAN},
        False,
    ),
    ("dashboard_home", _call("dashboard_home"), {}, False),
    ("loan_details", _call("loan_details"), {}, True),
    ("foreclosure_details", _call("foreclosure_details"), {}, True),
    ("overdue_details", _call("overdue_details"), {}, True),
    ("noc_details", _call("noc_details"), {}, True),
    ("repayment_schedule", _call("repayment_schedule"), {}, True),
    ("download_welcome_letter", _call("download_welcome_letter"), {}, True),
    (
        "download_soa",
        _call("download_soa"),
        {"start_date": "2025-01-01", "end_date": "2025-12-31"},
        True,
    ),
    ("logout", _call("logout"), {}, False),
]


APP_ID_TOOLS = [t for t in AUTHENTICATED_TOOLS if t[3]]


# ─────────────────────────────────────────────────────────────────────────────
# Rejection corpus — 4 attack scenarios × every authenticated tool
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,tool,extra_args,_uses_app_id",
    AUTHENTICATED_TOOLS,
    ids=[t[0] for t in AUTHENTICATED_TOOLS],
)
async def test_tool_rejects_missing_session(
    two_sessions_store: RedisSessionStore,
    name: str,
    tool: Callable[..., Any],
    extra_args: dict[str, Any],
    _uses_app_id: bool,
) -> None:
    result = await tool(session_id="nonexistent_session", **extra_args)
    assert (
        result == AUTH_REJECT_MESSAGE
    ), f"{name}: expected AUTH_REJECT_MESSAGE for missing session, got {result!r}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,tool,extra_args,_uses_app_id",
    AUTHENTICATED_TOOLS,
    ids=[t[0] for t in AUTHENTICATED_TOOLS],
)
async def test_tool_rejects_unauthenticated_session(
    two_sessions_store: RedisSessionStore,
    name: str,
    tool: Callable[..., Any],
    extra_args: dict[str, Any],
    _uses_app_id: bool,
) -> None:
    # Simulate a session that ran generate_otp but never validated_otp.
    await two_sessions_store.set("sess_pending", {"phone_number": "9999911111"})
    result = await tool(session_id="sess_pending", **extra_args)
    assert (
        result == AUTH_REJECT_MESSAGE
    ), f"{name}: expected AUTH_REJECT_MESSAGE for pending session, got {result!r}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,tool,extra_args,_uses_app_id",
    AUTHENTICATED_TOOLS,
    ids=[t[0] for t in AUTHENTICATED_TOOLS],
)
async def test_tool_rejects_empty_session_id(
    two_sessions_store: RedisSessionStore,
    name: str,
    tool: Callable[..., Any],
    extra_args: dict[str, Any],
    _uses_app_id: bool,
) -> None:
    result = await tool(session_id="", **extra_args)
    assert (
        result == AUTH_REJECT_MESSAGE
    ), f"{name}: expected AUTH_REJECT_MESSAGE for empty session_id, got {result!r}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,tool,extra_args,_uses_app_id",
    APP_ID_TOOLS,
    ids=[t[0] for t in APP_ID_TOOLS],
)
async def test_tool_rejects_tampered_app_id(
    two_sessions_store: RedisSessionStore,
    stubbed_core_api: None,
    name: str,
    tool: Callable[..., Any],
    extra_args: dict[str, Any],
    _uses_app_id: bool,
) -> None:
    """Defence against the 'stale / tampered app_id' bug class.

    Put customer B's loan as A's app_id — active_loan_or_raise must
    notice the mismatch against session.loans and reject rather than
    trust the raw dict entry. If this ever returns the stub's
    ``__STUB_*__`` string, the ownership layer has collapsed and needs
    attention BEFORE this lands in prod."""
    current = await two_sessions_store.get(CUSTOMER_A_SESSION) or {}
    current["app_id"] = CUSTOMER_B_LOAN  # tamper
    await two_sessions_store.set(CUSTOMER_A_SESSION, current)

    result = await tool(session_id=CUSTOMER_A_SESSION, **extra_args)
    assert "__STUB_" not in str(result), (
        f"{name}: tampered app_id reached the CRM call-site — ownership "
        f"helper failed. Got {result!r}"
    )
    assert "doesn't appear" in str(result).lower() or "select_loan" in str(
        result
    ), f"{name}: expected ownership rejection, got {result!r}"


@pytest.mark.asyncio
async def test_select_loan_rejects_cross_session_loan_number(
    two_sessions_store: RedisSessionStore,
) -> None:
    """Customer A calls select_loan with customer B's LN → must reject.

    This is the canonical cross-session attack: A authenticates legitimately
    but tries to pivot to B's resource by guessing the loan_number. The
    helper ``verify_loan_ownership`` is the lone line of defence."""
    select_loan_fn = _call("select_loan")
    result = await select_loan_fn(loan_number=CUSTOMER_B_LOAN, session_id=CUSTOMER_A_SESSION)
    assert (
        "doesn't appear" in str(result).lower()
    ), f"expected ownership rejection for cross-session loan, got {result!r}"
    # And the session's app_id must not have been flipped to B's loan.
    refreshed = await two_sessions_store.get(CUSTOMER_A_SESSION) or {}
    assert (
        refreshed.get("app_id") == CUSTOMER_A_LOAN
    ), "cross-session select_loan mutated the victim's app_id — critical break"


# ─────────────────────────────────────────────────────────────────────────────
# Happy-path — confirm the decorator DOESN'T spuriously block legit calls.
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_is_logged_in_happy_path(
    two_sessions_store: RedisSessionStore,
) -> None:
    result = await _call("is_logged_in")(session_id=CUSTOMER_A_SESSION)
    assert result == {"logged_in": True, "customer_id": "CUST-A"}


@pytest.mark.asyncio
async def test_list_loans_happy_path(
    two_sessions_store: RedisSessionStore,
) -> None:
    result = await _call("list_loans")(session_id=CUSTOMER_A_SESSION)
    assert CUSTOMER_A_LOAN in result
    assert CUSTOMER_B_LOAN not in result
    assert "active" in result  # header


@pytest.mark.asyncio
async def test_select_loan_happy_path(
    two_sessions_store: RedisSessionStore,
) -> None:
    # Pre-condition: wipe app_id so the call is a genuine selection.
    current = await two_sessions_store.get(CUSTOMER_A_SESSION) or {}
    current["app_id"] = None
    await two_sessions_store.set(CUSTOMER_A_SESSION, current)

    result = await _call("select_loan")(loan_number=CUSTOMER_A_LOAN, session_id=CUSTOMER_A_SESSION)
    assert CUSTOMER_A_LOAN in result
    refreshed = await two_sessions_store.get(CUSTOMER_A_SESSION) or {}
    assert refreshed.get("app_id") == CUSTOMER_A_LOAN


@pytest.mark.asyncio
async def test_dashboard_home_happy_path(
    two_sessions_store: RedisSessionStore,
    stubbed_core_api: None,
) -> None:
    result = await _call("dashboard_home")(session_id=CUSTOMER_A_SESSION)
    assert result == f"__STUB_DASHBOARD__{CUSTOMER_A_SESSION}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,stub_marker",
    [
        ("loan_details", "__STUB_LOAN_DETAILS__"),
        ("foreclosure_details", "__STUB_FORECLOSURE__"),
        ("overdue_details", "__STUB_OVERDUE__"),
        ("noc_details", "__STUB_NOC__"),
        ("repayment_schedule", "__STUB_REPAYMENT__"),
        ("download_welcome_letter", "__STUB_WELCOME__"),
    ],
)
async def test_app_id_tool_happy_path(
    two_sessions_store: RedisSessionStore,
    stubbed_core_api: None,
    name: str,
    stub_marker: str,
) -> None:
    result = await _call(name)(session_id=CUSTOMER_A_SESSION)
    assert result.startswith(
        stub_marker
    ), f"{name}: happy path didn't reach core_api stub, got {result!r}"


@pytest.mark.asyncio
async def test_download_soa_happy_path(
    two_sessions_store: RedisSessionStore,
    stubbed_core_api: None,
) -> None:
    result = await _call("download_soa")(
        start_date="2025-01-01",
        end_date="2025-12-31",
        session_id=CUSTOMER_A_SESSION,
    )
    assert result.startswith("__STUB_SOA__")
    assert "2025-01-01" in result
    assert "2025-12-31" in result


@pytest.mark.asyncio
async def test_logout_happy_path_deletes_session(
    two_sessions_store: RedisSessionStore,
) -> None:
    result = await _call("logout")(session_id=CUSTOMER_A_SESSION)
    assert "Logged out" in result
    # Session is gone from Redis; subsequent calls would now hit the
    # missing-session rejection path — sanity-check that.
    gone = await two_sessions_store.get(CUSTOMER_A_SESSION)
    assert gone is None


# ─────────────────────────────────────────────────────────────────────────────
# Meta — catalogue completeness
# ─────────────────────────────────────────────────────────────────────────────


def test_every_decorated_server_tool_is_in_corpus() -> None:
    """If a new authenticated tool lands in server.py without an entry in
    ``AUTHENTICATED_TOOLS``, this test fails. The corpus IS the contract
    — refuse to let a new tool ship without coverage."""
    # These 3 tools deliberately DO NOT wear @requires_authenticated_session.
    pre_auth_or_public = {"generate_otp", "validate_otp", "search_knowledge_base"}
    corpus_names = {name for name, *_rest in AUTHENTICATED_TOOLS}

    found_server_tools: set[str] = set()
    for attr_name in dir(server_mod):
        attr = getattr(server_mod, attr_name)
        if hasattr(attr, "parameters") and hasattr(attr, "fn"):
            tool_name = getattr(attr, "name", attr_name)
            found_server_tools.add(tool_name)

    authenticated = found_server_tools - pre_auth_or_public
    missing = authenticated - corpus_names
    assert not missing, (
        f"New authenticated tool(s) {missing} are not in AUTHENTICATED_TOOLS "
        "— add a corpus entry before shipping."
    )
