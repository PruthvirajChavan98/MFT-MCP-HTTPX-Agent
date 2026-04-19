from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

from fastmcp import FastMCP

from . import auth_api as _auth_api_mod
from . import core_api as _core_api_mod
from . import session_store as _session_store_mod
from .auth_api import MockFinTechAuthAPIs
from .auth_decorators import requires_authenticated_session
from .config import MCP_SERVER_HOST, MCP_SERVER_PORT
from .core_api import MockFinTechAPIs
from .description_utils import _d
from .kb_search import format_results as _format_kb_results
from .kb_search import semantic_search as _kb_semantic_search
from .ownership import OwnershipError, active_loan_or_raise, verify_loan_ownership
from .session_context import SessionContext
from .session_store import RedisSessionStore

log = logging.getLogger(name="mcp_server")


# ---------------------------------------------------------------------------
# Lifespan — warm Redis on startup, close all async resources on shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(_app: Any) -> AsyncIterator[None]:
    log.info("MCP lifespan: warming async Redis connection pool")
    await _session_store_mod.get_redis()
    yield
    log.info("MCP lifespan: shutting down async resources")
    await _auth_api_mod._close_http_client()
    await _core_api_mod._close_http_client()
    await _session_store_mod.close_redis()


mcp = FastMCP(name="MFT MCP Server", lifespan=lifespan)
session_store = RedisSessionStore()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _touch(session_id: str, tool_name: str, extra: Optional[dict] = None) -> None:
    """Write the last-tool marker for pre-auth tools (generate_otp /
    validate_otp / search_knowledge_base). Authenticated tools get the
    same marker written inside @requires_authenticated_session.
    """
    payload: dict[str, Any] = {"_last_tool": tool_name, "_last_touch_ts": time.time()}
    if extra:
        payload.update(extra)
    await session_store.update(session_id, payload)


def get_auth(session_id: str) -> MockFinTechAuthAPIs:
    return MockFinTechAuthAPIs(session_id, session_store=session_store)


def get_api(session_id: str) -> MockFinTechAPIs:
    return MockFinTechAPIs(session_id, session_store=session_store)


# ---------------------------------------------------------------------------
# Pre-auth tools — run BEFORE the caller is authenticated. These may not
# wear @requires_authenticated_session because the session doesn't yet
# have auth_state="authenticated".
# ---------------------------------------------------------------------------
@mcp.tool(name="generate_otp", description=_d("generate_otp"))
async def generate_otp(user_input: str, session_id: str) -> str:
    await _touch(session_id, "generate_otp")
    return await get_auth(session_id).generate_otp(user_input)


@mcp.tool(name="validate_otp", description=_d("validate_otp"))
async def validate_otp(otp: str, session_id: str) -> str:
    await _touch(session_id, "validate_otp")
    return await get_auth(session_id).validate_otp(otp)


@mcp.tool(name="search_knowledge_base", description=_d("search_knowledge_base"))
async def search_knowledge_base(query: str, session_id: str) -> str:
    """Public FAQ semantic search over the shared kb_faqs Milvus collection.

    No authentication required — FAQ content is public product knowledge.
    Returns top-5 matches formatted as plaintext for LLM consumption.
    """
    await _touch(session_id, "search_knowledge_base")
    results = await _kb_semantic_search(query, limit=5)
    return _format_kb_results(results)


# ---------------------------------------------------------------------------
# Authenticated tools — wear @requires_authenticated_session, which
# (a) enforces auth_state, (b) injects a typed SessionContext, and
# (c) writes the audit-trail _last_tool marker automatically.
# ---------------------------------------------------------------------------
@mcp.tool(name="is_logged_in", description=_d("is_logged_in"))
@requires_authenticated_session
async def is_logged_in(ctx: SessionContext) -> dict:
    # If execution reaches here, the decorator has already proven the
    # caller is authenticated — no need to re-check anything.
    return {"logged_in": True, "customer_id": ctx.customer_id}


@mcp.tool(name="list_loans", description=_d("list_loans"))
@requires_authenticated_session
async def list_loans(ctx: SessionContext) -> str:
    if not ctx.loans:
        return "No loans found on your account."
    lines = ["loan_number|status|product_code|active"]
    for loan in ctx.loans:
        active_flag = "yes" if loan.loan_number == ctx.app_id else "no"
        lines.append(
            f"{loan.loan_number}|{loan.status or ''}|{loan.product_code or ''}|{active_flag}"
        )
    return "\n".join(lines)


@mcp.tool(name="select_loan", description=_d("select_loan"))
@requires_authenticated_session
async def select_loan(loan_number: str, ctx: SessionContext) -> str:
    try:
        loan = verify_loan_ownership(ctx, loan_number, tool="select_loan")
    except OwnershipError as err:
        return err.message
    await session_store.update(ctx.session_id, {"app_id": loan.loan_number})
    return f"Active loan set to '{loan.loan_number}'."


@mcp.tool(name="dashboard_home", description=_d("dashboard_home"))
@requires_authenticated_session
async def dashboard_home(ctx: SessionContext) -> str:
    # Dashboard is a per-customer overview, not scoped to a specific loan,
    # so no active_loan_or_raise — the CRM bearer token already binds
    # output to the authenticated customer.
    return await get_api(ctx.session_id).get_dashboard_home()


@mcp.tool(name="loan_details", description=_d("loan_details"))
@requires_authenticated_session
async def loan_details(ctx: SessionContext) -> str:
    try:
        active_loan_or_raise(ctx, tool="loan_details")
    except OwnershipError as err:
        return err.message
    return await get_api(ctx.session_id).get_loan_details()


@mcp.tool(name="foreclosure_details", description=_d("foreclosure_details"))
@requires_authenticated_session
async def foreclosure_details(ctx: SessionContext) -> str:
    try:
        active_loan_or_raise(ctx, tool="foreclosure_details")
    except OwnershipError as err:
        return err.message
    return await get_api(ctx.session_id).get_foreclosure_details()


@mcp.tool(name="overdue_details", description=_d("overdue_details"))
@requires_authenticated_session
async def overdue_details(ctx: SessionContext) -> str:
    try:
        active_loan_or_raise(ctx, tool="overdue_details")
    except OwnershipError as err:
        return err.message
    return await get_api(ctx.session_id).get_overdue_details()


@mcp.tool(name="noc_details", description=_d("noc_details"))
@requires_authenticated_session
async def noc_details(ctx: SessionContext) -> str:
    try:
        active_loan_or_raise(ctx, tool="noc_details")
    except OwnershipError as err:
        return err.message
    return await get_api(ctx.session_id).get_noc_details()


@mcp.tool(name="repayment_schedule", description=_d("repayment_schedule"))
@requires_authenticated_session
async def repayment_schedule(ctx: SessionContext) -> str:
    try:
        active_loan_or_raise(ctx, tool="repayment_schedule")
    except OwnershipError as err:
        return err.message
    return await get_api(ctx.session_id).get_repayment_schedule()


@mcp.tool(name="download_welcome_letter", description=_d("download_welcome_letter"))
@requires_authenticated_session
async def download_welcome_letter(ctx: SessionContext) -> str:
    try:
        active_loan_or_raise(ctx, tool="download_welcome_letter")
    except OwnershipError as err:
        return err.message
    return await get_api(ctx.session_id).download_welcome_letter()


@mcp.tool(name="download_soa", description=_d("download_soa"))
@requires_authenticated_session
async def download_soa(start_date: str, end_date: str, ctx: SessionContext) -> str:
    try:
        active_loan_or_raise(ctx, tool="download_soa")
    except OwnershipError as err:
        return err.message
    return await get_api(ctx.session_id).download_soa(start_date, end_date)


@mcp.tool(
    name="logout",
    description="logout() -> str\nPurpose: Clear the current session authentication and access tokens.\nInput variables: (none)",
)
@requires_authenticated_session
async def logout(ctx: SessionContext) -> str:
    await session_store.delete(ctx.session_id)
    return "Logged out successfully. Please reload the page or generate a new OTP to log in again."


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def main() -> None:
    log.info("Starting MCP Server on %s:%s", MCP_SERVER_HOST, MCP_SERVER_PORT)
    mcp.run(transport="sse", host=MCP_SERVER_HOST, port=MCP_SERVER_PORT)


if __name__ == "__main__":
    main()
