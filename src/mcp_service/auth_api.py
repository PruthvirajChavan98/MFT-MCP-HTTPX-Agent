import logging
import os
from typing import Any, Dict, Optional

import httpx

from .config import CRM_BASE_URL
from .session_store import RedisSessionStore
from .utils import JsonConverter

conv = JsonConverter(sep=".")
log = logging.getLogger(name="mft_auth")


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

    @staticmethod
    def _is_phone(s: str) -> bool:
        return s.isdigit() and len(s) == 10

    def get_contact_hint(self, app_id: str) -> str:
        app_id = (app_id or "").strip()
        if not app_id:
            return self._to_vsc({"error": "app_id is required"})

        headers = {"Accept": "application/json"}
        try:
            with httpx.Client(
                auth=self.auth, headers=headers, follow_redirects=True, timeout=20.0
            ) as client:
                resp = client.get(self._url(f"/mockfin-service/get-contact-hint/{app_id}/"))
                self.session_store.update(
                    self.session_id,
                    {
                        "last_contact_hint_app_id": app_id,
                        "last_contact_hint_status": resp.status_code,
                        "last_contact_hint_response": resp.text[:5000],
                    },
                )
                if resp.status_code != 200:
                    return self._to_vsc(
                        {"status_code": resp.status_code, "error": resp.text[:5000]}
                    )

                data = resp.json()
                phone = data.get("phone_number")
                resolved_app_id = (
                    data.get("app_id")
                    or data.get("loan_application_id")
                    or data.get("application_id")
                    or app_id
                )
                resolved_loan_id = data.get("loan_id") or data.get("loanId")

                updates: Dict[str, Any] = {"phone_number": phone, "app_id": resolved_app_id}
                if resolved_loan_id:
                    updates["loan_id"] = resolved_loan_id
                self.session_store.update(self.session_id, updates)
                return self._to_vsc(data)
        except Exception as e:
            self.logger.error(f"Contact hint error: {e}")
            self.session_store.update(self.session_id, {"last_contact_hint_exception": str(e)})
            return self._to_vsc({"error": str(e)})

    def generate_otp(self, user_input: str) -> str:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        user_input = (user_input or "").strip()
        self.session_store.update(self.session_id, {"last_generate_otp_input": user_input})
        if not user_input:
            return self._to_vsc({"error": "Provide phone_number or app_id"})

        try:
            with httpx.Client(
                auth=self.auth, headers=headers, follow_redirects=True, timeout=30.0
            ) as client:
                phone_number: Optional[str] = None
                app_id: Optional[str] = None

                if self._is_phone(user_input):
                    phone_number = user_input
                    self.session_store.update(self.session_id, {"phone_number": phone_number})
                else:
                    app_id = user_input
                    s = self.session_store.get(self.session_id) or {}
                    phone_number = s.get("phone_number")
                    # Intentionally removed the blocking check for phone_number here

                payload: Dict[str, Any] = {}
                if phone_number:
                    payload["phone_number"] = phone_number
                if app_id:
                    payload["app_id"] = app_id

                if not payload:
                    return self._to_vsc(
                        {"error": "Phone number unknown. Please provide phone number explicitly."}
                    )

                resp = client.post(self._url("/mockfin-service/otp/generate_new/"), json=payload)
                self.logger.info(f"POST otp/generate_new - {resp.status_code}")

                try:
                    resp_json = resp.json() if resp.text else {}
                except:
                    resp_json = {}

                if isinstance(resp_json, dict):
                    updates: Dict[str, Any] = {}

                    # 1. Capture App ID if returned
                    if resp_json.get("app_id"):
                        updates["app_id"] = resp_json.get("app_id")
                        app_id = app_id or resp_json.get("app_id")

                    # 2. CRITICAL FIX: Capture Phone Number if returned
                    if resp_json.get("phone_number"):
                        updates["phone_number"] = resp_json.get("phone_number")
                        phone_number = phone_number or resp_json.get("phone_number")

                    if updates:
                        self.session_store.update(self.session_id, updates)

                if resp.status_code in (200, 201):
                    return self._to_vsc(
                        {
                            "status": "OTP Sent",
                            "phone_number": phone_number,
                            "app_id": app_id,
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
        self.session_store.update(self.session_id, {"last_validate_otp_input": otp})

        session_data = self.session_store.get(self.session_id) or {}
        phone_number = (session_data.get("phone_number") or "").strip()
        app_id = (session_data.get("app_id") or "").strip()

        if not phone_number:
            return self._to_vsc({"error": "Phone number missing."})
        if not app_id:
            return self._to_vsc({"error": "app_id missing."})

        payload = {"phone_number": phone_number, "app_id": app_id, "otp": otp}
        try:
            with httpx.Client(
                auth=self.auth, headers=headers, follow_redirects=True, timeout=30.0
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

                updates = {
                    "access_token": access_token,
                    "phone_number": phone_number,
                    "app_id": app_id,
                    "user_details": auth_data.get("user", {}),
                }
                if auth_data.get("loan_id"):
                    updates["loan_id"] = auth_data.get("loan_id")

                self.session_store.update(self.session_id, updates)
                self.logger.info(f"✅ Session {self.session_id} authenticated.")

                return self._to_vsc(
                    {
                        "status": "success",
                        "message": "Logged in.",
                        "app_id": app_id,
                        "user_details": updates["user_details"],
                    }
                )
        except Exception as e:
            self.logger.error(f"OTP Validate Error: {e}")
            return self._to_vsc({"error": str(e)})

    def is_logged_in(self) -> bool:
        data = self.session_store.get(self.session_id) or {}
        return bool(data.get("access_token"))
