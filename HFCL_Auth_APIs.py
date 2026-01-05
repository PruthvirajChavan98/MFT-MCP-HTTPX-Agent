import os
import httpx
from typing import Optional, Any, Dict

from Loggers.StdOutLogger import StdoutLogger
from redis_session_store import RedisSessionStore

log = StdoutLogger(name="hfcl_auth")

def _valid_session_id(session_id: object) -> str:
    sid = str(session_id).strip() if session_id is not None else ""
    if not sid or sid.lower() in {"null", "none"}:
        raise ValueError(f"Invalid session_id: {session_id!r}")
    return sid

class HeroFincorpAuthAPIs:
    """
    Wraps REST auth-ish endpoints from your Postman collection:

      GET  /herofin-service/get-contact-hint/{appId}/        (Basic)
      POST /herofin-service/otp/generate_new/                (Basic)
      POST /herofin-service/otp/validate_new/                (Basic)
    """

    def __init__(
        self,
        session_id: str,
        session_store: Optional[RedisSessionStore] = None,
        base_url: Optional[str] = None,
        basic_username: Optional[str] = None,
        basic_password: Optional[str] = None,
    ):
        self.session_id = _valid_session_id(session_id)
        self.base_url = (base_url or os.getenv("CRM_BASE_URL", "http://localhost:8080")).rstrip("/")

        user = basic_username or os.getenv("BASIC_AUTH_USERNAME", "crm")
        pwd = basic_password or os.getenv("BASIC_AUTH_PASSWORD", "crm")
        self.auth = httpx.BasicAuth(user, pwd)

        self.logger = log
        self.session_store = session_store or RedisSessionStore()

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def get_contact_hint(self, app_id: str) -> Dict[str, Any]:
        app_id = (app_id or "").strip()
        if not app_id:
            return {"error": "app_id is required"}

        headers = {"Accept": "application/json"}
        try:
            with httpx.Client(auth=self.auth, headers=headers, follow_redirects=True, timeout=20.0) as client:
                url = self._url(f"/herofin-service/get-contact-hint/{app_id}/")
                resp = client.get(url)

                self.session_store.update(self.session_id, {
                    "last_contact_hint_app_id": app_id,
                    "last_contact_hint_status": resp.status_code,
                    "last_contact_hint_response": resp.text[:5000],
                })

                if resp.status_code != 200:
                    return {"status_code": resp.status_code, "error": resp.text}

                data = resp.json()
                # commonly returns phone_number + app_id
                phone = data.get("phone_number")
                resolved_app_id = data.get("app_id") or app_id

                # persist
                self.session_store.update(self.session_id, {
                    "phone_number": phone,
                    "app_id": resolved_app_id,
                })

                return data

        except Exception as e:
            self.logger.error(f"Contact hint error: {e}")
            self.session_store.update(self.session_id, {"last_contact_hint_exception": str(e)})
            return {"error": str(e)}

    def generate_otp(self, user_input: str):
        """
        Accepts either:
          - 10 digit phone number (e.g. 9000000000)
          - app_id (e.g. 5115292 or APP-9000000000)
        """
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        user_input = (user_input or "").strip()

        # touch session so key exists
        self.session_store.update(self.session_id, {"last_generate_otp_input": user_input})

        if not user_input:
            self.session_store.update(self.session_id, {"last_generate_otp_error": "empty"})
            return {"error": "Provide phone_number or app_id"}

        try:
            with httpx.Client(auth=self.auth, headers=headers, follow_redirects=True, timeout=30.0) as client:
                phone_number: Optional[str] = None
                app_id: Optional[str] = None

                # phone path
                if user_input.isdigit() and len(user_input) == 10:
                    phone_number = user_input
                    # keep whatever app_id we might already have
                    existing = self.session_store.get(self.session_id) or {}
                    app_id = existing.get("app_id")

                else:
                    # treat as app_id (supports numeric or "APP-xxxx")
                    app_id = user_input
                    hint = client.get(self._url(f"/herofin-service/get-contact-hint/{app_id}/"))
                    self.session_store.update(self.session_id, {
                        "last_contact_hint_status": hint.status_code,
                        "last_contact_hint_response": hint.text[:5000],
                    })

                    if hint.status_code != 200:
                        return {"status_code": hint.status_code, "error": hint.text}

                    hint_data = hint.json()
                    phone_number = hint_data.get("phone_number")
                    app_id = hint_data.get("app_id") or app_id

                # persist resolved values even if OTP fails
                self.session_store.update(self.session_id, {
                    "phone_number": phone_number,
                    "app_id": app_id,
                })

                if not phone_number:
                    self.session_store.update(self.session_id, {"last_generate_otp_error": "phone_number not resolved"})
                    return {"error": "Could not resolve phone number"}

                payload = {"phone_number": phone_number, "app_id": app_id}
                resp = client.post(self._url("/herofin-service/otp/generate_new/"), json=payload)
                self.logger.info(f"POST otp/generate_new - {resp.status_code}")

                self.session_store.update(self.session_id, {
                    "last_generate_otp_status": resp.status_code,
                    "last_generate_otp_response": resp.text[:5000],
                })

                if resp.status_code in (200, 201):
                    return {"status": "OTP Sent", "phone_number": phone_number, "app_id": app_id}

                return {"status_code": resp.status_code, "error": resp.text}

        except Exception as e:
            self.logger.error(f"OTP Generation Error: {e}")
            self.session_store.update(self.session_id, {"last_generate_otp_exception": str(e)})
            return {"error": str(e)}

    def validate_otp(self, otp: str):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        otp = (otp or "").strip()

        self.session_store.update(self.session_id, {"last_validate_otp_input": otp})

        session_data = self.session_store.get(self.session_id) or {}
        phone_number = session_data.get("phone_number")
        app_id = session_data.get("app_id")

        if not phone_number:
            return {"error": "phone_number missing in session (run generate_otp first)"}

        payload = {"phone_number": phone_number, "app_id": app_id, "otp": otp}

        try:
            with httpx.Client(auth=self.auth, headers=headers, follow_redirects=True, timeout=30.0) as client:
                resp = client.post(self._url("/herofin-service/otp/validate_new/"), json=payload)
                self.logger.info(f"POST otp/validate_new - {resp.status_code}")

                self.session_store.update(self.session_id, {
                    "last_validate_otp_status": resp.status_code,
                    "last_validate_otp_response": resp.text[:5000],
                })

                if resp.status_code not in (200, 201):
                    return {"status_code": resp.status_code, "error": resp.text}

                data = resp.json()
                access_token = data.get("access_token")
                resolved_app_id = data.get("loan_id") or data.get("app_id") or app_id

                if access_token:
                    self.session_store.update(self.session_id, {
                        "access_token": access_token,
                        "app_id": resolved_app_id,
                        "phone_number": phone_number,
                    })

                return data

        except Exception as e:
            self.logger.error(f"OTP Validation Error: {e}")
            self.session_store.update(self.session_id, {"last_validate_otp_exception": str(e)})
            return {"error": str(e)}

    def is_logged_in(self):
        data = self.session_store.get(self.session_id) or {}
        return bool(data.get("access_token"))
