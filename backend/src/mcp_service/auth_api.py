import logging
import os
from typing import Any, Dict, Optional

import httpx

from .config import CRM_BASE_URL
from .session_store import RedisSessionStore
from .utils import JsonConverter

conv = JsonConverter(sep=".")
log = logging.getLogger(name="mft_auth")

_AUTH_TIMEOUT = httpx.Timeout(connect=5.0, read=25.0, write=10.0, pool=5.0)


def _valid_session_id(session_id: object) -> str:
    sid = str(session_id).strip() if session_id is not None else ""
    if not sid or sid.lower() in {"null", "none"}:
        raise ValueError(f"Invalid session_id: {session_id!r}")
    return sid


class MockFinTechAuthAPIs:
    def __init__(self, session_id: str, session_store: Optional[RedisSessionStore] = None):
        self.session_id = _valid_session_id(session_id)
        self.base_url = CRM_BASE_URL
        user = os.getenv("BASIC_AUTH_USERNAME", "crm")
        pwd = os.getenv("BASIC_AUTH_PASSWORD", "crm")
        self.auth = httpx.BasicAuth(user, pwd)
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

    def generate_otp(self, user_input: str) -> str:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        phone_number = (user_input or "").strip()
        if not phone_number:
            return self._to_vsc({"error": "phone_number is required"})

        self.session_store.update(self.session_id, {"phone_number": phone_number})

        try:
            with httpx.Client(
                auth=self.auth, headers=headers, follow_redirects=True, timeout=_AUTH_TIMEOUT
            ) as client:
                resp = client.post(
                    self._url("/mockfin-service/otp/generate_new/"),
                    json={"phone_number": phone_number},
                )
                self.logger.info(f"POST otp/generate_new - {resp.status_code}")

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
            self.logger.error(f"OTP Gen Error: {e}")
            return self._to_vsc({"error": str(e)})

    def validate_otp(self, otp: str) -> str:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        otp = (otp or "").strip()

        session_data = self.session_store.get(self.session_id) or {}
        phone_number = (session_data.get("phone_number") or "").strip()

        if not phone_number:
            return self._to_vsc({"error": "Phone number missing. Call generate_otp first."})

        payload = {"phone_number": phone_number, "otp": otp}
        try:
            with httpx.Client(
                auth=self.auth, headers=headers, follow_redirects=True, timeout=_AUTH_TIMEOUT
            ) as client:
                resp = client.post(self._url("/mockfin-service/otp/validate_new/"), json=payload)
                self.logger.info(f"POST otp/validate_new - {resp.status_code}")

                if resp.status_code not in (200, 201):
                    return self._to_vsc(
                        {"status_code": resp.status_code, "error": resp.text[:5000]}
                    )

                auth_data = resp.json() if resp.text else {}
                access_token = auth_data.get("access_token") or auth_data.get("token")

                if not access_token:
                    return self._to_vsc({"status": "failed", "error": "No token in response."})

                loans: list = auth_data.get("loans") or []

                updates: Dict[str, Any] = {
                    "access_token": access_token,
                    "phone_number": phone_number,
                    "user_details": auth_data.get("user", {}),
                    "loans": loans,
                }

                # Auto-select the active loan when there is exactly one
                if len(loans) == 1:
                    updates["app_id"] = loans[0].get("loan_number")

                self.session_store.update(self.session_id, updates)
                self.logger.info(f"✅ Session {self.session_id} authenticated.")

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
            self.logger.error(f"OTP Validate Error: {e}")
            return self._to_vsc({"error": str(e)})

    def is_logged_in(self) -> bool:
        data = self.session_store.get(self.session_id) or {}
        return bool(data.get("access_token"))
