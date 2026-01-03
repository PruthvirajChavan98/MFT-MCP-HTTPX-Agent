import time
from fastmcp import FastMCP

from HFCL_Auth_APIs import HeroFincorpAuthAPIs
from HFCLAPIsNew import HeroFincorpAPIs

from redis_image_store import RedisImageStore
from redis_session_store import RedisSessionStore, StdoutLogger  # StdoutLogger imported from your logger module

# If the line above fails because StdoutLogger isn't exported there, use:
# from Loggers.StdOutLogger import StdoutLogger
from Loggers.StdOutLogger import StdoutLogger
from redis_session_store import RedisSessionStore

log = StdoutLogger(name="mcp_server")

mcp = FastMCP(name="HFCL MCP Server httpx tools")

# One shared session store instance for the MCP server process
session_store = RedisSessionStore()

# Image store (uses same Redis URL logic internally via RedisSessionStore default)
image_store = RedisImageStore()

def _touch(session_id: str, tool_name: str, extra: dict | None = None):
    payload = {
        "_last_tool": tool_name,
        "_last_touch_ts": time.time(),
    }
    if extra:
        payload.update(extra)
    session_store.update(session_id, payload)

def get_auth_api_client(session_id: str) -> HeroFincorpAuthAPIs:
    if not session_id:
        raise ValueError("session_id is required")
    return HeroFincorpAuthAPIs(session_id)

def get_api_client(session_id: str) -> HeroFincorpAPIs:
    if not session_id:
        raise ValueError("session_id is required")
    return HeroFincorpAPIs(session_id)

# -------------------------
# DEBUG TOOLS
# -------------------------
@mcp.tool
def debug_redis_touch(session_id: str) -> dict:
    """
    HARD PROOF TOOL:
    Writes to Redis for this session_id and reads it back.
    Use this to confirm you're writing to the same Redis you inspect (crm_redis).
    """
    _touch(session_id, "debug_redis_touch", {"debug": True})
    value = session_store.get(session_id)
    return {
        "ok": True,
        "session_id": session_id,
        "redis_uri": getattr(session_store, "redis_uri", None),
        "value": value,
    }

@mcp.tool
def debug_redis_get(session_id: str) -> dict:
    """Read session_id from Redis and return it with redis_uri."""
    return {
        "session_id": session_id,
        "redis_uri": getattr(session_store, "redis_uri", None),
        "value": session_store.get(session_id),
    }

# -------------------------
# REAL TOOLS
# -------------------------
@mcp.tool
def generate_otp(user_input: str, session_id: str) -> dict:
    _touch(session_id, "generate_otp", {"user_input": user_input})
    try:
        auth_api = get_auth_api_client(session_id)
        return auth_api.generate_otp(user_input)
    except Exception as e:
        _touch(session_id, "generate_otp_error", {"error": str(e)})
        return {"error": f"Failed to generate OTP: {str(e)}"}

@mcp.tool
def validate_otp(otp: str, session_id: str) -> dict:
    _touch(session_id, "validate_otp", {"otp": otp})
    try:
        auth_api = get_auth_api_client(session_id)
        return auth_api.validate_otp(otp)
    except Exception as e:
        _touch(session_id, "validate_otp_error", {"error": str(e)})
        return {"error": f"Failed to verify OTP: {str(e)}"}

@mcp.tool
def get_dashboard_data(session_id: str) -> dict:
    _touch(session_id, "get_dashboard_data")
    try:
        api = get_api_client(session_id)
        return api.get_dashboard_data()
    except Exception as e:
        _touch(session_id, "get_dashboard_data_error", {"error": str(e)})
        return {"error": f"Failed to get dashboard data: {str(e)}"}

@mcp.tool
def get_loan_details(session_id: str) -> dict:
    _touch(session_id, "get_loan_details")
    try:
        api = get_api_client(session_id)
        return api.get_loan_details()
    except Exception as e:
        _touch(session_id, "get_loan_details_error", {"error": str(e)})
        return {"error": f"Failed to get loan details: {str(e)}"}

@mcp.tool
def get_overdue_details(session_id: str) -> dict:
    _touch(session_id, "get_overdue_details")
    try:
        api = get_api_client(session_id)
        return api.get_overdue_details()
    except Exception as e:
        _touch(session_id, "get_overdue_details_error", {"error": str(e)})
        return {"error": f"Failed to get overdue details: {str(e)}"}

@mcp.tool
def get_repayment_schedule(session_id: str) -> dict:
    _touch(session_id, "get_repayment_schedule")
    try:
        api = get_api_client(session_id)
        return api.get_repayment_schedule()
    except Exception as e:
        _touch(session_id, "get_repayment_schedule_error", {"error": str(e)})
        return {"error": f"Failed to get repayment schedule: {str(e)}"}

@mcp.tool
def get_foreclosure_details(session_id: str) -> dict:
    _touch(session_id, "get_foreclosure_details")
    try:
        api = get_api_client(session_id)
        return api.get_foreclosure_details()
    except Exception as e:
        _touch(session_id, "get_foreclosure_details_error", {"error": str(e)})
        return {"error": f"Failed to get foreclosure details: {str(e)}"}

@mcp.tool
def download_noc_letter(session_id: str) -> dict:
    _touch(session_id, "download_noc_letter")
    try:
        api = get_api_client(session_id)
        return api.download_noc_letter()
    except Exception as e:
        _touch(session_id, "download_noc_letter_error", {"error": str(e)})
        return {"error": f"Failed to download NOC letter: {str(e)}"}

@mcp.tool
def make_noc_request(chassis_number: str, engine_no: str, vehicle_number: str, session_id: str) -> dict:
    _touch(session_id, "make_noc_request", {"vehicle_number": vehicle_number})
    try:
        api = get_api_client(session_id)

        if not api.bearer_token:
            return {"error": "Bearer token not found. Please login first."}

        image_base64 = image_store.get_image(image_ref=f"{api.app_id}_{api.session_id}")
        if not image_base64:
            return {"error": "Image not uploaded. Please upload the image first."}

        return api.make_noc_request(
            chassis_no=chassis_number,
            engine_no=engine_no,
            vehicle_number=vehicle_number,
            image_base64=image_base64
        )
    except Exception as e:
        _touch(session_id, "make_noc_request_error", {"error": str(e)})
        return {"error": f"Failed to upload NOC documents: {str(e)}"}

@mcp.tool
def is_logged_in(session_id: str):
    _touch(session_id, "is_logged_in")
    auth_api = get_auth_api_client(session_id)
    return auth_api.is_logged_in()

if __name__ == "__main__":
    log.info("Starting MCP server on 0.0.0.0:8050 (SSE)")
    mcp.run(transport="sse", host="0.0.0.0", port=8050)
