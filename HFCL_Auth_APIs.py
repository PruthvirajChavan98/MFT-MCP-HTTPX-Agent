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
    Wraps REST auth-ish endpoints from your Postman collection.
    
    CRITICAL CHANGE:
    - validate_otp now writes the access_token to Redis.
    - validate_otp returns a SANITIZED dictionary (no token) to the caller.
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
                phone = data.get("phone_number")
                resolved_app_id = data.get("app_id") or app_id

                # Persist hints
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
        Accepts: 10 digit phone OR app_id.
        Resolves to phone_number and triggers OTP.
        """
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        user_input = (user_input or "").strip()

        self.session_store.update(self.session_id, {"last_generate_otp_input": user_input})

        if not user_input:
            return {"error": "Provide phone_number or app_id"}

        try:
            with httpx.Client(auth=self.auth, headers=headers, follow_redirects=True, timeout=30.0) as client:
                phone_number: Optional[str] = None
                app_id: Optional[str] = None

                # 1. Resolve Input to Phone/AppID
                if user_input.isdigit() and len(user_input) == 10:
                    phone_number = user_input
                    # Keep existing app_id if we have it
                    existing = self.session_store.get(self.session_id) or {}
                    app_id = existing.get("app_id")
                else:
                    # Treat as app_id -> call contact hint
                    app_id = user_input
                    hint = client.get(self._url(f"/herofin-service/get-contact-hint/{app_id}/"))
                    if hint.status_code != 200:
                        return {"status_code": hint.status_code, "error": hint.text}
                    
                    hint_data = hint.json()
                    phone_number = hint_data.get("phone_number")
                    app_id = hint_data.get("app_id") or app_id

                # Save resolved context
                self.session_store.update(self.session_id, {
                    "phone_number": phone_number,
                    "app_id": app_id,
                })

                if not phone_number:
                    return {"error": "Could not resolve phone number for OTP generation"}

                # 2. Call Generate OTP
                payload = {"phone_number": phone_number, "app_id": app_id}
                resp = client.post(self._url("/herofin-service/otp/generate_new/"), json=payload)
                self.logger.info(f"POST otp/generate_new - {resp.status_code}")

                self.session_store.update(self.session_id, {
                    "last_generate_otp_status": resp.status_code,
                    "last_generate_otp_response": resp.text[:5000],
                })

                if resp.status_code in (200, 201):
                    return {
                        "status": "OTP Sent", 
                        "phone_number": phone_number, 
                        "app_id": app_id,
                        "message": "OTP has been sent to your registered mobile number."
                    }

                return {"status_code": resp.status_code, "error": resp.text}

        except Exception as e:
            self.logger.error(f"OTP Generation Error: {e}")
            return {"error": str(e)}

    def validate_otp(self, otp: str):
        """
        Validates OTP.
        ON SUCCESS: Saves access_token to Redis. Returns SANITIZED dict (no token) to LLM.
        """
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        otp = (otp or "").strip()

        self.session_store.update(self.session_id, {"last_validate_otp_input": otp})

        session_data = self.session_store.get(self.session_id) or {}
        phone_number = session_data.get("phone_number")
        app_id = session_data.get("app_id")

        if not phone_number:
            return {"error": "Phone number missing in session. Please request OTP first."}

        payload = {"phone_number": phone_number, "app_id": app_id, "otp": otp}

        try:
            with httpx.Client(auth=self.auth, headers=headers, follow_redirects=True, timeout=30.0) as client:
                resp = client.post(self._url("/herofin-service/otp/validate_new/"), json=payload)
                self.logger.info(f"POST otp/validate_new - {resp.status_code}")

                if resp.status_code not in (200, 201):
                    return {"status_code": resp.status_code, "error": resp.text}

                data = resp.json()
                
                # --- CRITICAL: CAPTURE STATE ---
                access_token = data.get("access_token")
                resolved_app_id = data.get("loan_id") or data.get("app_id") or app_id
                user_details = data.get("user", {})

                if access_token:
                    self.session_store.update(self.session_id, {
                        "access_token": access_token,
                        "app_id": resolved_app_id,
                        "phone_number": phone_number,
                        "user_details": user_details # Optional: save user profile bits
                    })
                    self.logger.info(f"✅ Session {self.session_id} authenticated. Token saved to Redis.")
                
                # --- CRITICAL: SANITIZE RETURN ---
                # We return a success message but deliberately exclude the raw token.
                return {
                    "status": "success",
                    "message": "OTP Verified. You are now logged in.",
                    "loan_id": resolved_app_id,
                    "user_details": user_details,
                    "action": "Token secured in backend session."
                }

        except Exception as e:
            self.logger.error(f"OTP Validation Error: {e}")
            return {"error": str(e)}

    def is_logged_in(self):
        data = self.session_store.get(self.session_id) or {}
        return bool(data.get("access_token"))
