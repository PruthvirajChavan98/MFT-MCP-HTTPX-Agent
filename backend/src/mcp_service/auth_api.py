from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, Optional

import httpx

from .config import CRM_BASE_URL
from .session_store import RedisSessionStore
from .session_store import valid_session_id as _valid_session_id
from .utils import JsonConverter

conv = JsonConverter(sep=".")
log = logging.getLogger(name="mft_auth")

_AUTH_TIMEOUT = httpx.Timeout(connect=5.0, read=25.0, write=10.0, pool=5.0)

# ---------------------------------------------------------------------------
# Module-level async HTTP client singleton
# ---------------------------------------------------------------------------
_http_client: httpx.AsyncClient | None = None
_http_lock = asyncio.Lock()


async def _get_http_client() -> httpx.AsyncClient:
    global _http_client

    if _http_client is not None:
        return _http_client

    async with _http_lock:
        if _http_client is None:
            _http_client = httpx.AsyncClient(
                timeout=_AUTH_TIMEOUT,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
                follow_redirects=True,
            )
            log.info("Initialized async HTTP client for auth API")
    return _http_client


async def _close_http_client() -> None:
    global _http_client

    async with _http_lock:
        if _http_client is not None:
            await _http_client.aclose()
            _http_client = None
            log.info("Closed async HTTP client for auth API")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_basic_auth() -> httpx.BasicAuth:
    """Load CRM credentials from env vars. Fails loudly if unset."""
    user = os.environ.get("BASIC_AUTH_USERNAME")
    pwd = os.environ.get("BASIC_AUTH_PASSWORD")
    if not user or not pwd:
        raise RuntimeError(
            "BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD environment variables are required. "
            "Set them before starting the MCP server."
        )
    return httpx.BasicAuth(user, pwd)


# ---------------------------------------------------------------------------
# Auth API wrapper — fully async
# ---------------------------------------------------------------------------
class MockFinTechAuthAPIs:
    def __init__(self, session_id: str, session_store: Optional[RedisSessionStore] = None):
        self.session_id = _valid_session_id(session_id)
        self.base_url = CRM_BASE_URL
        self.auth = _load_basic_auth()
        self.logger = log
        self.session_store = session_store or RedisSessionStore()

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def _to_vsc(self, obj: Any, explode_key: Optional[str] = None) -> str:
        vsc, _ = conv.json_to_vsc_text(
            obj, include_header=True, preserve_key_order=True, explode_key=explode_key
        )
        return vsc

    async def generate_otp(self, user_input: str) -> str:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        phone_number = (user_input or "").strip()
        if not phone_number:
            return self._to_vsc({"error": "phone_number is required"})

        await self.session_store.update(self.session_id, {"phone_number": phone_number})

        try:
            client = await _get_http_client()
            resp = await client.post(
                self._url("/mockfin-service/otp/generate_new/"),
                json={"phone_number": phone_number},
                headers=headers,
                auth=self.auth,
            )
            self.logger.info("POST otp/generate_new - %d", resp.status_code)

            try:
                resp_json = resp.json() if resp.text else {}
            except Exception:
                resp_json = {}

            if resp.status_code in (200, 201):
                return self._to_vsc(
                    {
                        "status": "OTP Sent",
                        "phone_number": phone_number,
                        "message": resp_json.get("message") or "OTP sent.",
                    }
                )
            return self._to_vsc({"status_code": resp.status_code, "error": resp.text[:5000]})
        except Exception as e:
            self.logger.error("OTP Gen Error: %s", e)
            return self._to_vsc({"error": str(e)})

    async def validate_otp(self, otp: str) -> str:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        otp = (otp or "").strip()

        session_data = await self.session_store.get(self.session_id) or {}
        phone_number = (session_data.get("phone_number") or "").strip()

        if not phone_number:
            return self._to_vsc({"error": "Phone number missing. Call generate_otp first."})

        payload = {"phone_number": phone_number, "otp": otp}
        try:
            client = await _get_http_client()
            resp = await client.post(
                self._url("/mockfin-service/otp/validate_new/"),
                json=payload,
                headers=headers,
                auth=self.auth,
            )
            self.logger.info("POST otp/validate_new - %d", resp.status_code)

            if resp.status_code not in (200, 201):
                return self._to_vsc({"status_code": resp.status_code, "error": resp.text[:5000]})

            auth_data = resp.json() if resp.text else {}
            access_token = auth_data.get("access_token") or auth_data.get("token")

            if not access_token:
                return self._to_vsc({"status": "failed", "error": "No token in response."})

            loans: list = auth_data.get("loans") or []
            user = auth_data.get("user") or {}
            # Explicit customer identity anchor (GD6 TA1). Previously identity
            # was implicit via phone_number; now downstream authorization
            # checks can assert customer_id directly without dict-digging.
            customer_id = str(user.get("id") or user.get("customer_id") or "").strip()

            # Refuse to mark the session authenticated without a customer_id.
            # Otherwise SessionContext.from_session_dict raises on every
            # subsequent tool call and the user is stuck in a perpetual
            # "Please log in first" loop that can only be broken by Redis
            # intervention or session TTL. (code-review HIGH-1)
            if not customer_id:
                self.logger.error(
                    "OTP validated but CRM returned no user.id/customer_id "
                    "for %s — refusing to mark authenticated.",
                    phone_number,
                )
                return self._to_vsc(
                    {
                        "status": "failed",
                        "error": (
                            "Login succeeded at the bank but your customer "
                            "identity could not be resolved. Please try again "
                            "or contact support."
                        ),
                    }
                )

            updates: Dict[str, Any] = {
                "access_token": access_token,
                "phone_number": phone_number,
                "customer_id": customer_id,
                # Explicit auth state — the @requires_authenticated_session
                # decorator checks this rather than inferring from field
                # presence.
                "auth_state": "authenticated",
                "user_details": user,
                "loans": loans,
            }

            # Auto-select the active loan when there is exactly one
            if len(loans) == 1:
                updates["app_id"] = loans[0].get("loan_number")

            await self.session_store.update(self.session_id, updates)
            self.logger.info("Session %s authenticated.", self.session_id)

            result: Dict[str, Any] = {
                "status": "success",
                "message": "Logged in.",
                "user_details": updates["user_details"],
                "loans": loans,
            }
            if len(loans) == 1:
                result["active_loan"] = loans[0].get("loan_number")
            elif len(loans) > 1:
                result["hint"] = (
                    "Multiple loans found. Call list_loans() then select_loan(loan_number)."
                )

            return self._to_vsc(result)
        except Exception as e:
            self.logger.error("OTP Validate Error: %s", e)
            return self._to_vsc({"error": str(e)})

    async def is_logged_in(self) -> bool:
        data = await self.session_store.get(self.session_id) or {}
        return bool(data.get("access_token"))
