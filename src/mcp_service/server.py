import time
from typing import Any, Optional
from fastmcp import FastMCP
from src.common.logger import StdoutLogger
from .session_store import RedisSessionStore
from .auth_api import HeroFincorpAuthAPIs
from .core_api import HeroFincorpAPIs
from .config import MCP_SERVER_HOST, MCP_SERVER_PORT
from .description_utils import _d

log = StdoutLogger(name="mcp_server")

mcp = FastMCP(name="HFCL MCP Server")
session_store = RedisSessionStore()

def _touch(session_id: str, tool_name: str, extra: Optional[dict] = None):
    payload: dict[str, Any] = {"_last_tool": tool_name, "_last_touch_ts": time.time()}
    if extra: payload.update(extra)
    session_store.update(session_id, payload)

def get_auth(session_id: str):
    return HeroFincorpAuthAPIs(session_id, session_store=session_store)

def get_api(session_id: str):
    return HeroFincorpAPIs(session_id, session_store=session_store)

# @mcp.tool(name="get_contact_hint", description=<description>)
# def get_contact_hint(app_id: str, session_id: str) -> str:
#     _touch(session_id, "get_contact_hint")
#     return get_auth(session_id).get_contact_hint(app_id)

@mcp.tool(name="generate_otp", description=_d("generate_otp"))
def generate_otp(user_input: str, session_id: str) -> str:
    _touch(session_id, "generate_otp")
    return get_auth(session_id).generate_otp(user_input)

@mcp.tool(name="validate_otp", description=_d("validate_otp"))
def validate_otp(otp: str, session_id: str) -> str:
    _touch(session_id, "validate_otp")
    return get_auth(session_id).validate_otp(otp)

@mcp.tool(name="is_logged_in", description=_d("is_logged_in"))
def is_logged_in(session_id: str) -> dict:
    _touch(session_id, "is_logged_in")
    return {"logged_in": get_auth(session_id).is_logged_in()}

@mcp.tool(name="dashboard_home", description=_d("dashboard_home"))
def dashboard_home(session_id: str) -> str:
    _touch(session_id, "dashboard_home")
    return get_api(session_id).get_dashboard_home()

@mcp.tool(name="loan_details", description=_d("loan_details"))
def loan_details(session_id: str) -> str:
    _touch(session_id, "loan_details")
    return get_api(session_id).get_loan_details()

@mcp.tool(name="foreclosure_details", description=_d("foreclosure_details"))
def foreclosure_details(session_id: str) -> str:
    _touch(session_id, "foreclosure_details")
    return get_api(session_id).get_foreclosure_details()

@mcp.tool(name="overdue_details", description=_d("overdue_details"))
def overdue_details(session_id: str) -> str:
    _touch(session_id, "overdue_details")
    return get_api(session_id).get_overdue_details()

@mcp.tool(name="noc_details", description=_d("noc_details"))
def noc_details(session_id: str) -> str:
    _touch(session_id, "noc_details")
    return get_api(session_id).get_noc_details()

@mcp.tool(name="repayment_schedule", description=_d("repayment_schedule"))
def repayment_schedule(session_id: str) -> str:
    _touch(session_id, "repayment_schedule")
    return get_api(session_id).get_repayment_schedule()

@mcp.tool(name="download_welcome_letter", description=_d("download_welcome_letter"))
def download_welcome_letter(session_id: str) -> str:
    _touch(session_id, "download_welcome_letter")
    return get_api(session_id).download_welcome_letter()

@mcp.tool(name="download_soa", description=_d("download_soa"))
def download_soa(session_id: str, start_date: str, end_date: str) -> str:
    _touch(session_id, "download_soa")
    return get_api(session_id).download_soa(start_date, end_date)

# @mcp.tool(name="initiate_transaction")
# def initiate_transaction(amount: str, otp: str, session_id: str, payment_mode: str = "UPI") -> str:
#     _touch(session_id, "initiate_transaction")
#     return get_api(session_id).initiate_transaction(amount, otp, payment_mode)

# @mcp.tool(name="profile_phone_generate_otp")
# def profile_phone_generate_otp(session_id: str, new_phone: str) -> str:
#     _touch(session_id, "profile_phone_generate_otp")
#     return get_api(session_id).profile_phone_generate_otp(new_phone)

# @mcp.tool(name="profile_phone_validate_otp")
# def profile_phone_validate_otp(session_id: str, new_phone: str, otp: str) -> str:
#     _touch(session_id, "profile_phone_validate_otp")
#     return get_api(session_id).profile_phone_validate_otp(new_phone, otp)

def main():
    log.info(f"Starting MCP Server on {MCP_SERVER_HOST}:{MCP_SERVER_PORT}")
    mcp.run(transport="sse", host=MCP_SERVER_HOST, port=MCP_SERVER_PORT)

if __name__ == "__main__":
    main()
