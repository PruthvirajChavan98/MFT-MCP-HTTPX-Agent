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
from .config import MCP_SERVER_HOST, MCP_SERVER_PORT
from .core_api import MockFinTechAPIs
from .description_utils import _d
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
    payload: dict[str, Any] = {"_last_tool": tool_name, "_last_touch_ts": time.time()}
    if extra:
        payload.update(extra)
    await session_store.update(session_id, payload)


def get_auth(session_id: str) -> MockFinTechAuthAPIs:
    return MockFinTechAuthAPIs(session_id, session_store=session_store)


def get_api(session_id: str) -> MockFinTechAPIs:
    return MockFinTechAPIs(session_id, session_store=session_store)


# ---------------------------------------------------------------------------
# MCP Tools — all async
# ---------------------------------------------------------------------------
@mcp.tool(name="generate_otp", description=_d("generate_otp"))
async def generate_otp(user_input: str, session_id: str) -> str:
    await _touch(session_id, "generate_otp")
    return await get_auth(session_id).generate_otp(user_input)


@mcp.tool(name="validate_otp", description=_d("validate_otp"))
async def validate_otp(otp: str, session_id: str) -> str:
    await _touch(session_id, "validate_otp")
    return await get_auth(session_id).validate_otp(otp)


@mcp.tool(name="is_logged_in", description=_d("is_logged_in"))
async def is_logged_in(session_id: str) -> dict:
    await _touch(session_id, "is_logged_in")
    return {"logged_in": await get_auth(session_id).is_logged_in()}


@mcp.tool(name="list_loans", description=_d("list_loans"))
async def list_loans(session_id: str) -> str:
    await _touch(session_id, "list_loans")
    s = await session_store.get(session_id) or {}
    loans = s.get("loans") or []
    active = s.get("app_id")
    if not loans:
        return "No loans found. Please log in first."
    lines = ["loan_number|status|product_code|active"]
    for loan in loans:
        ln = loan.get("loan_number", "")
        lines.append(
            f"{ln}|{loan.get('status', '')}|{loan.get('product_code', '')}|{'yes' if ln == active else 'no'}"
        )
    return "\n".join(lines)


@mcp.tool(name="select_loan", description=_d("select_loan"))
async def select_loan(loan_number: str, session_id: str) -> str:
    await _touch(session_id, "select_loan")
    s = await session_store.get(session_id) or {}
    loans = s.get("loans") or []
    known = [loan.get("loan_number") for loan in loans]
    if loan_number not in known:
        return f"Loan '{loan_number}' not found. Available: {', '.join(str(x) for x in known)}"
    await session_store.update(session_id, {"app_id": loan_number})
    return f"Active loan set to '{loan_number}'."


@mcp.tool(name="dashboard_home", description=_d("dashboard_home"))
async def dashboard_home(session_id: str) -> str:
    await _touch(session_id, "dashboard_home")
    return await get_api(session_id).get_dashboard_home()


@mcp.tool(name="loan_details", description=_d("loan_details"))
async def loan_details(session_id: str) -> str:
    await _touch(session_id, "loan_details")
    return await get_api(session_id).get_loan_details()


@mcp.tool(name="foreclosure_details", description=_d("foreclosure_details"))
async def foreclosure_details(session_id: str) -> str:
    await _touch(session_id, "foreclosure_details")
    return await get_api(session_id).get_foreclosure_details()


@mcp.tool(name="overdue_details", description=_d("overdue_details"))
async def overdue_details(session_id: str) -> str:
    await _touch(session_id, "overdue_details")
    return await get_api(session_id).get_overdue_details()


@mcp.tool(name="noc_details", description=_d("noc_details"))
async def noc_details(session_id: str) -> str:
    await _touch(session_id, "noc_details")
    return await get_api(session_id).get_noc_details()


@mcp.tool(name="repayment_schedule", description=_d("repayment_schedule"))
async def repayment_schedule(session_id: str) -> str:
    await _touch(session_id, "repayment_schedule")
    return await get_api(session_id).get_repayment_schedule()


@mcp.tool(name="download_welcome_letter", description=_d("download_welcome_letter"))
async def download_welcome_letter(session_id: str) -> str:
    await _touch(session_id, "download_welcome_letter")
    return await get_api(session_id).download_welcome_letter()


@mcp.tool(name="download_soa", description=_d("download_soa"))
async def download_soa(session_id: str, start_date: str, end_date: str) -> str:
    await _touch(session_id, "download_soa")
    return await get_api(session_id).download_soa(start_date, end_date)


@mcp.tool(
    name="logout",
    description="logout() -> str\nPurpose: Clear the current session authentication and access tokens.\nInput variables: (none)",
)
async def logout(session_id: str) -> str:
    await _touch(session_id, "logout")
    await session_store.delete(session_id)
    return "Logged out successfully. Please reload the page or generate a new OTP to log in again."


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
def main() -> None:
    log.info("Starting MCP Server on %s:%s", MCP_SERVER_HOST, MCP_SERVER_PORT)
    mcp.run(transport="sse", host=MCP_SERVER_HOST, port=MCP_SERVER_PORT)


if __name__ == "__main__":
    main()
