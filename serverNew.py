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

mcp = FastMCP(name="HFCL MCP Server (tools aligned to Postman endpoints)")

# One shared session store for the MCP server process
session_store = RedisSessionStore()

# Image store uses same session store / redis uri
image_store = RedisImageStore(session_store=session_store)

def _touch(session_id: str, tool_name: str, extra: Optional[dict] = None):
    """
    Internal: Updates the Redis session record with "last tool used" metadata.

    Why this exists
    --------------
    MCP clients often execute multiple tools in a workflow. When something goes wrong,
    it is invaluable to know "what ran last" and "when" for a given session. This helper
    provides lightweight traceability without requiring full request logging.

    What is written
    ---------------
    - _last_tool: name of the tool that ran
    - _last_touch_ts: unix timestamp (float seconds since epoch)
    - plus any optional fields in `extra` for debugging/correlation

    Notes
    -----
    - This is *not* a security mechanism. Treat `session_id` as an opaque key and keep it
      unguessable in production.
    """
    payload: dict[str, Any] = {
        "_last_tool": tool_name,
        "_last_touch_ts": time.time(),
    }
    if extra:
        payload.update(extra)
    session_store.update(session_id, payload)

def get_auth_api_client(session_id: str) -> HeroFincorpAuthAPIs:
    """
    Internal: Returns a pre-login auth client bound to this session.

    This client typically implements the legacy Basic Auth OTP flow:
    - get-contact-hint (resolve masked phone by app_id)
    - otp/generate_new (OTP generation)
    - otp/validate_new (OTP validation + token minting)

    The client is given the shared `session_store` so it can persist/consume
    session context across calls.
    """
    if not session_id:
        raise ValueError("session_id is required")
    return HeroFincorpAuthAPIs(session_id, session_store=session_store)

def get_api_client(session_id: str) -> HeroFincorpAPIs:
    """
    Internal: Returns a post-login API client bound to this session.

    This client typically implements Bearer-authenticated legacy endpoints:
    - dashboard/home
    - loan details + loan-related endpoints
    - document downloads
    - payment initiation
    - profile phone update

    The client is given the shared `session_store` so it can read the access token
    and other contextual values (phone_number, app_id) saved during login.
    """
    if not session_id:
        raise ValueError("session_id is required")
    return HeroFincorpAPIs(session_id, session_store=session_store)

def _crm_url(path: str) -> str:
    """
    Internal: Join the configured CRM base URL with a path.

    Behavior
    --------
    - Ensures the path begins with a leading '/'.
    - Uses `CRM_BASE_URL` environment variable (default: http://localhost:8080).
    - Ensures `CRM_BASE_URL` does not end with '/', so joining is stable.

    Example
    -------
    CRM_BASE_URL=http://localhost:8080 and path='/health' -> 'http://localhost:8080/health'
    """
    if not path.startswith("/"):
        path = "/" + path
    return f"{CRM_BASE_URL}{path}"

def _bearer_headers(session_id: str) -> dict:
    """
    Internal: Build Authorization headers from Redis session state.

    Reads
    -----
    - access_token: If present, emits: {"Authorization": "Bearer <token>"}.

    Returns
    -------
    - dict suitable for httpx headers
    - empty dict if no token is present (caller may receive 401/GraphQL auth errors)
    """
    data = session_store.get(session_id) or {}
    token = data.get("access_token")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


@mcp.tool(name="get_contact_hint")
def get_contact_hint(app_id: str, session_id: str) -> dict:
    """
    Purpose
    -------
    The legacy mobile app often stores/uses a masked phone (e.g., "xxxxxx1234") and needs
    a "contact hint" step to map an app_id to that masked phone representation. This tool
    provides that behavior and is typically the first step in the OTP flow.

    Inputs
    ------
    app_id (str)
      Loan application identifier.

    Returns
    -------
    Returns whatever the backend/auth client returns, typically:
    - Success: { "phone_number": "xxxxxx1234", "app_id": "..." }
    - Legacy failure (often HTTP 200): { "details": "Loan app id is incorrect" }

    Compatibility notes
    -------------------
    - Some legacy endpoints intentionally return HTTP 200 even on logical errors.
      Callers must inspect the JSON body, not just HTTP status.
    """
    _touch(session_id, "get_contact_hint", {"app_id": app_id})
    return get_auth_api_client(session_id).get_contact_hint(app_id)

@mcp.tool(name="generate_otp")
def generate_otp(user_input: str, session_id: str) -> dict:
    """
    Purpose
    -------
    Triggers OTP generation for a user attempting to log in via the legacy app.
    This tool is deliberately tolerant of different "user_input" shapes because
    upstream clients vary in what they provide (phone, app_id, masked phone, or
    combined text).

    Inputs
    ------
    user_input (str)
      A flexible input that your HeroFincorpAuthAPIs client interprets to build the request.
      Common patterns include:
      - plain phone number: "9000000000"
      - app id: "APP-9000000000"
      - masked phone: "xxxxxx0000"
      - combined hint text that contains both phone and app_id
      
    Returns
    -------
    Typical responses include:
    - Success: { "phone_number": "...", "app_id": "...", "message": "OTP generated Successfully" }
    - Legacy failure (often HTTP 200): { "message": "Invalid Phone Number and/or App Id or Request Expired" }

    Notes
    -----
    - OTP expiry and throttling rules are enforced by the backend mock.
    - In strict-compat mode, exact casing/wording of "message" may matter for mobile clients.
    """
    _touch(session_id, "generate_otp", {"user_input": user_input})
    return get_auth_api_client(session_id).generate_otp(user_input)

@mcp.tool(name="validate_otp")
def validate_otp(otp: str, session_id: str) -> dict:
    """
    Purpose
    -------
    Validates a 6-digit OTP and, on success, returns a JWT access token that is required for
    post-login REST endpoints and authenticated GraphQL queries.

    Inputs
    ------
    otp (str)
      6-digit OTP. In dev/mock environments a universal OTP such as "123456" may be accepted
      (depending on backend configuration).

    Returns
    -------
    Typical success response:
      {
        "message": "OTP verified Successfully",
        "access_token": "<jwt>",  # MAKE SURE THAT LLM DOES NOT SEE TOKEN
        "loan_id": "...",
        "user": { ... }
      }
    Typical legacy failure response:
      { "message": "Invalid Phone Number and/or App Id or Request Expired" }

    Compatibility notes
    -------------------
    - Some legacy failure modes return HTTP 200; treat the response body as authoritative.
    """
    _touch(session_id, "validate_otp", {"otp": otp})
    return get_auth_api_client(session_id).validate_otp(otp)

@mcp.tool(name="is_logged_in")
def is_logged_in(session_id: str) -> dict:
    """
    Purpose
    -------
    Lightweight guard before calling post-login endpoints. This tool answers:
    "Does the auth client believe we have a valid logged-in state for this session?"

    Returns
    -------
    { "logged_in": true|false }
    """
    _touch(session_id, "is_logged_in")
    return {"logged_in": get_auth_api_client(session_id).is_logged_in()}

@mcp.tool(name="dashboard_home")
def dashboard_home(session_id: str) -> dict:
    """
    Purpose
    -------
    Returns the JSON structure consumed by the mobile app home screen:
    flags + loan lists (often including both "loans" and "all_loans").

    Returns
    -------
    The backend home JSON (shape depends on strict-compat contract). Example fields:
    - "agency_flag": "true"/"false" (string, not boolean)
    - "loans": [...]
    - "all_loans": [...]
    """
    _touch(session_id, "dashboard_home")
    return get_api_client(session_id).get_dashboard_home()

@mcp.tool(name="loan_details")
def loan_details(session_id: str, app_id: Optional[str] = None) -> dict:
    """
    Purpose
    -------
    Returns the core loan details response consumed by multiple screens in the mobile app.
    In strict-compat mode this response may include:
    - mixed casing keys (snake_case + camelCase)
    - numerics represented as strings in some fields
    - legacy null handling

    Inputs
    ------
    app_id (str)
      If provided, fetches details for that specific app id.
      If omitted/None, the API client may fall back to:
        - app_id stored in session state
        - app_id embedded in JWT claims
      (implementation-dependent)

    Returns
    -------
    A JSON document representing LoanDetailsResponse as defined by the backend contract.
    """
    _touch(session_id, "loan_details", {"app_id": app_id})
    return get_api_client(session_id).get_loan_details(app_id=app_id)

@mcp.tool(name="foreclosure_details")
def foreclosure_details(session_id: str, app_id: Optional[str] = None) -> dict:
    """
    Purpose
    -------
    Provides foreclosure eligibility and net payable breakup. In the mock backend, values
    may be deterministic per app_id to ensure repeatable QA and integration tests.

    Inputs
    ------
    app_id (Optional[str])
      If omitted, the API client may infer app_id from token/session context.

    Returns
    -------
    ForeclosureDetailsResponse JSON (strict-compat shape).
    """
    _touch(session_id, "foreclosure_details", {"app_id": app_id})
    return get_api_client(session_id).get_foreclosure_details(app_id=app_id)

@mcp.tool(name="overdue_details")
def overdue_details(session_id: str, app_id: Optional[str] = None) -> dict:
    """
    Purpose
    -------
    Returns overdue totals and last-payment information used by the mobile overdue UI.
    This typically includes breakup amounts (EMI/LPP/BCC/Other) and status fields.

    Inputs
    ------
    app_id (str).

    Returns
    -------
    OverdueDetailsResponse JSON (strict-compat shape).
    """
    _touch(session_id, "overdue_details", {"app_id": app_id})
    return get_api_client(session_id).get_overdue_details(app_id=app_id)

@mcp.tool(name="noc_details")
def noc_details(session_id: str, app_id: Optional[str] = None) -> dict:
    """
    Purpose
    -------
    Returns whether a No Objection Certificate is available and relevant dates/status.
    In strict-compat mode, field names and nullability should match the legacy app.

    Inputs
    ------
    app_id (Optional[str])

    Returns
    -------
    NocDetailsResponse JSON (strict-compat shape).
    """
    _touch(session_id, "noc_details", {"app_id": app_id})
    return get_api_client(session_id).get_noc_details(app_id=app_id)

@mcp.tool(name="repayment_schedule")
def repayment_schedule(session_id: str, app_id: Optional[str] = None) -> dict:
    """
    Purpose
    -------
    Returns the installment schedule + totals as consumed by the repayment schedule UI.
    Mock backend may return canonical schedules for specific app_ids to support
    deterministic regression testing.

    Inputs
    ------
    app_id (Optional[str])
      If omitted, the API client may infer app_id from token/session context.

    Returns
    -------
    RepaymentScheduleResponse JSON (strict-compat shape).
    """
    _touch(session_id, "repayment_schedule", {"app_id": app_id})
    return get_api_client(session_id).get_repayment_schedule(app_id=app_id)

@mcp.tool(name="download_welcome_letter")
def download_welcome_letter(session_id: str) -> dict:
    """
    Purpose
    -------
    The legacy app expects a "secure document" object rather than raw PDF bytes.
    This tool returns document metadata (and a secure reference/URL depending on backend),
    and the backend may write an audit record (e.g., to MongoDB) for document generation.

    Returns
    -------
    SecureDocument-style JSON (strict-compat shape), commonly including:
    - document identifiers / type
    - a secure download reference or pre-signed URL (backend dependent)
    - timestamps/audit metadata (backend dependent)
    """
    _touch(session_id, "download_welcome_letter")
    return get_api_client(session_id).download_welcome_letter()

@mcp.tool(name="download_soa")
def download_soa(session_id: str, start_date: str, end_date: str) -> dict:
    """
    Purpose
    -------
    Generates/returns metadata for a Statement of Account for a given period.
    The backend commonly records the request for auditing.
    
    start_date (str)
      Inclusive start date in ISO format: YYYY-MM-DD
    end_date (str)
      Inclusive end date in ISO format: YYYY-MM-DD

    Returns
    -------
    SecureDocument-style JSON (strict-compat shape).
    """
    _touch(session_id, "download_soa", {"start_date": start_date, "end_date": end_date})
    return get_api_client(session_id).download_soa(start_date=start_date, end_date=end_date)


@mcp.tool(name="profile_phone_generate_otp")
def profile_phone_generate_otp(session_id: str, new_phone: str) -> dict:
    """
    Purpose
    -------
    Initiates a phone number update by requesting an OTP to be sent/issued for `new_phone`.
    This is the first step of a two-step flow:
      1) request OTP for new phone
      2) validate OTP and apply update

    Inputs
    ------
    new_phone (str)
      The new phone number to verify.

    Returns
    -------
    Backend JSON indicating OTP was generated/queued (strict-compat shape).
    """
    _touch(session_id, "profile_phone_generate_otp", {"new_phone": new_phone})
    return get_api_client(session_id).profile_phone_generate_otp(new_phone)

@mcp.tool(name="profile_phone_validate_otp")
def profile_phone_validate_otp(session_id: str, new_phone: str, otp: str) -> dict:
    """
    REST (Post-login): Profile phone update — Step 2 (validate OTP + apply update).

    Backend call (legacy)
    ---------------------
    PUT /herofin-service/profiles/?update=phone_number

    Auth
    ----
    Bearer JWT.

    Purpose
    -------
    Validates the OTP for `new_phone` and applies the phone update. Some implementations
    refresh the auth context after change (e.g., return a new token).

    Inputs
    ------
    new_phone (str)
      The phone number being confirmed.
    otp (str)
      OTP for phone update confirmation (mock may accept a universal OTP).

    Returns
    -------
    Backend JSON indicating update success/failure (strict-compat shape).
    """
    _touch(session_id, "profile_phone_validate_otp", {"new_phone": new_phone})
    return get_api_client(session_id).profile_phone_validate_otp(new_phone, otp)

if __name__ == "__main__":
    log.info("Starting MCP server on 0.0.0.0:8050 (SSE)")
    mcp.run(transport="sse", host="0.0.0.0", port=8050)
