import os
import time
import httpx
from typing import Any, Optional

from fastmcp import FastMCP

from HFCL_Auth_APIs import HeroFincorpAuthAPIs
from HFCLAPIsNew import HeroFincorpAPIs
from redis_image_store import RedisImageStore
from redis_session_store import RedisSessionStore
from Loggers.StdOutLogger import StdoutLogger

log = StdoutLogger(name="mcp_server")

CRM_BASE_URL = os.getenv("CRM_BASE_URL", "http://localhost:8080").rstrip("/")

mcp = FastMCP(name="HFCL MCP Server (Blind State Architecture)")

# Shared Session Store
session_store = RedisSessionStore()
image_store = RedisImageStore(session_store=session_store)

def _touch(session_id: str, tool_name: str, extra: Optional[dict] = None):
    """Updates Redis metadata for traceability."""
    payload: dict[str, Any] = {
        "_last_tool": tool_name,
        "_last_touch_ts": time.time(),
    }
    if extra:
        payload.update(extra)
    session_store.update(session_id, payload)

def get_auth_api_client(session_id: str) -> HeroFincorpAuthAPIs:
    """Returns Auth Client (Pre-Login)."""
    if not session_id:
        raise ValueError("session_id is required")
    return HeroFincorpAuthAPIs(session_id, session_store=session_store)

def get_api_client(session_id: str) -> HeroFincorpAPIs:
    """Returns API Client (Post-Login). Auto-hydrates context from Redis."""
    if not session_id:
        raise ValueError("session_id is required")
    return HeroFincorpAPIs(session_id, session_store=session_store)

# ---------------------------------------------------------
# AUTH TOOLS (User Input Required)
# ---------------------------------------------------------

@mcp.tool(name="get_contact_hint")
def get_contact_hint(app_id: str, session_id: str) -> dict:
    """
    Step 0: Resolves a masked phone number from a Loan App ID.
    """
    _touch(session_id, "get_contact_hint", {"app_id": app_id})
    return get_auth_api_client(session_id).get_contact_hint(app_id)

@mcp.tool(name="generate_otp")
def generate_otp(user_input: str, session_id: str) -> dict:
    """
    Step 1: Generates OTP.
    Input: Phone Number OR Loan App ID.
    """
    _touch(session_id, "generate_otp", {"user_input": user_input})
    return get_auth_api_client(session_id).generate_otp(user_input)

@mcp.tool(name="validate_otp")
def validate_otp(otp: str, session_id: str) -> dict:
    """
    Step 2: Validates OTP.
    Returns: Success/Fail status. (Token is HIDDEN from LLM).
    """
    _touch(session_id, "validate_otp", {"otp": otp})
    return get_auth_api_client(session_id).validate_otp(otp)

@mcp.tool(name="is_logged_in")
def is_logged_in(session_id: str) -> dict:
    """Checks if valid session exists."""
    _touch(session_id, "is_logged_in")
    return {"logged_in": get_auth_api_client(session_id).is_logged_in()}

# ---------------------------------------------------------
# DATA TOOLS (Parameter-less / Blind)
# ---------------------------------------------------------

@mcp.tool(name="dashboard_home")
def dashboard_home(session_id: str) -> dict:
    """Fetches the home dashboard for the logged-in user."""
    _touch(session_id, "dashboard_home")
    return get_api_client(session_id).get_dashboard_home()

@mcp.tool(name="loan_details")
def loan_details(session_id: str) -> dict:
    """Fetches details for the active loan in session."""
    _touch(session_id, "loan_details")
    return get_api_client(session_id).get_loan_details()

@mcp.tool(name="foreclosure_details")
def foreclosure_details(session_id: str) -> dict:
    """Fetches foreclosure details for the active loan."""
    _touch(session_id, "foreclosure_details")
    return get_api_client(session_id).get_foreclosure_details()

@mcp.tool(name="overdue_details")
def overdue_details(session_id: str) -> dict:
    """Fetches overdue/payment status for the active loan."""
    _touch(session_id, "overdue_details")
    return get_api_client(session_id).get_overdue_details()

@mcp.tool(name="noc_details")
def noc_details(session_id: str) -> dict:
    """Fetches NOC availability status."""
    _touch(session_id, "noc_details")
    return get_api_client(session_id).get_noc_details()

@mcp.tool(name="repayment_schedule")
def repayment_schedule(session_id: str) -> dict:
    """Fetches future repayment schedule."""
    _touch(session_id, "repayment_schedule")
    return get_api_client(session_id).get_repayment_schedule()

@mcp.tool(name="download_welcome_letter")
def download_welcome_letter(session_id: str) -> dict:
    """Downloads the Welcome Letter."""
    _touch(session_id, "download_welcome_letter")
    return get_api_client(session_id).download_welcome_letter()

@mcp.tool(name="download_soa")
def download_soa(session_id: str, start_date: str, end_date: str) -> dict:
    """
    Downloads Statement of Account (SOA).
    Requires: start_date, end_date (YYYY-MM-DD).
    """
    _touch(session_id, "download_soa", {"start_date": start_date, "end_date": end_date})
    return get_api_client(session_id).download_soa(start_date=start_date, end_date=end_date)

# ---------------------------------------------------------
# TRANSACTIONAL TOOLS (Mixed Input)
# ---------------------------------------------------------

@mcp.tool(name="initiate_transaction")
def initiate_transaction(
    amount: str, 
    otp: str, 
    session_id: str,
    payment_mode: str = "UPI"
) -> dict:
    """
    Initiates a payment transaction.
    Requires: amount, otp. 
    (Loan ID is inferred from session).
    """
    _touch(session_id, "initiate_transaction", {"amount": amount})
    return get_api_client(session_id).initiate_transaction(
        amount=amount, 
        otp=otp, 
        payment_mode=payment_mode
    )

# ---------------------------------------------------------
# PROFILE TOOLS
# ---------------------------------------------------------

@mcp.tool(name="profile_phone_generate_otp")
def profile_phone_generate_otp(session_id: str, new_phone: str) -> dict:
    """Request OTP to update profile phone number."""
    _touch(session_id, "profile_phone_generate_otp", {"new_phone": new_phone})
    return get_api_client(session_id).profile_phone_generate_otp(new_phone)

@mcp.tool(name="profile_phone_validate_otp")
def profile_phone_validate_otp(session_id: str, new_phone: str, otp: str) -> dict:
    """Verify OTP to update profile phone number."""
    _touch(session_id, "profile_phone_validate_otp", {"new_phone": new_phone})
    return get_api_client(session_id).profile_phone_validate_otp(new_phone, otp)

if __name__ == "__main__":
    log.info("Starting HFCL 'Blind State' MCP Server on 0.0.0.0:8050")
    mcp.run(transport="sse", host="0.0.0.0", port=8050)