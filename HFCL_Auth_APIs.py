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
    Wraps REST auth-ish endpoints.
    STRICT MODE: Checks JSON bodies for "soft errors" (HTTP 200 with error messages).
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
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        user_input = (user_input or "").strip()

        # NOTE: This can contain phone/app_id; keep only if you really want it persisted.
        self.session_store.update(self.session_id, {"last_generate_otp_input": user_input})

        if not user_input:
            return {"error": "Provide phone_number or app_id"}

        def _is_phone(s: str) -> bool:
            return s.isdigit() and len(s) == 10

        try:
            with httpx.Client(auth=self.auth, headers=headers, follow_redirects=True, timeout=30.0) as client:
                phone_number: Optional[str] = None
                app_id: Optional[str] = None

                def _try_contact_hint(value: str) -> Dict[str, Any]:
                    # Try a couple variants; some deployments differ on trailing slash
                    paths = [
                        f"/herofin-service/get-contact-hint/{value}/",
                        f"/herofin-service/get-contact-hint/{value}",
                    ]
                    for path in paths:
                        try:
                            r = client.get(self._url(path))
                            if r.status_code == 200:
                                return r.json()
                        except Exception:
                            pass
                    return {}

                # 1) Resolve input -> (phone_number, app_id)
                if _is_phone(user_input):
                    phone_number = user_input
                    existing = self.session_store.get(self.session_id) or {}
                    app_id = (existing.get("app_id") or "").strip() or None

                    # If app_id is missing, try resolving it via contact-hint using phone
                    if not app_id:
                        hint_data = _try_contact_hint(phone_number)
                        app_id = (
                            hint_data.get("app_id")
                            or hint_data.get("loan_id")
                            or hint_data.get("loan_application_id")
                            or hint_data.get("application_id")
                        )
                else:
                    app_id = user_input
                    # Try to resolve phone from app_id
                    hint_data = _try_contact_hint(app_id)
                    phone_number = hint_data.get("phone_number")
                    app_id = hint_data.get("app_id") or app_id

                # Persist what we know (avoid empty strings)
                self.session_store.update(self.session_id, {
                    "phone_number": phone_number,
                    "app_id": app_id,
                })

                if not phone_number:
                    return {"error": "Could not resolve phone number for OTP generation"}

                # 2) Generate OTP (CRITICAL: do NOT send app_id if you don't have it)
                payload: Dict[str, Any] = {"phone_number": phone_number}
                if app_id:
                    payload["app_id"] = app_id

                resp = client.post(self._url("/herofin-service/otp/generate_new/"), json=payload)
                self.logger.info(f"POST otp/generate_new - {resp.status_code}")

                self.session_store.update(self.session_id, {
                    "last_generate_otp_status": resp.status_code,
                    "last_generate_otp_response": resp.text[:5000],
                    "last_generate_otp_payload_keys": list(payload.keys()),
                })

                if resp.status_code in (200, 201):
                    # STRICT CHECK: treat "soft errors" in a 200 body as errors
                    try:
                        body = resp.json()
                        msg = (body.get("message") or body.get("detail") or "").lower()
                        if any(k in msg for k in ("invalid", "expired", "failed", "error")):
                            return {
                                "status_code": 422,
                                "error": body.get("message") or body.get("detail") or resp.text,
                                "hint": "OTP generate returned a soft-error body. Verify phone/app_id mapping in CRM.",
                            }
                    except Exception:
                        pass

                    return {
                        "status": "OTP Sent",
                        "phone_number": phone_number,
                        "app_id": app_id,
                        "message": "OTP has been sent to your registered mobile number.",
                    }

                return {"status_code": resp.status_code, "error": resp.text}

        except Exception as e:
            self.logger.error(f"OTP Generation Error: {e}")
            return {"error": str(e)}

    def validate_otp(self, otp: str):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        otp = (otp or "").strip()
        self.session_store.update(self.session_id, {"last_validate_otp_input": otp})

        session_data = self.session_store.get(self.session_id) or {}
        phone_number = session_data.get("phone_number")
        current_app_id = session_data.get("app_id")

        if not phone_number:
            return {"error": "Phone number missing in session. Please request OTP first."}

        safe_app_id = current_app_id if current_app_id is not None else ""
        payload = {"phone_number": phone_number, "app_id": safe_app_id, "otp": otp}

        try:
            with httpx.Client(auth=self.auth, headers=headers, follow_redirects=True, timeout=30.0) as client:
                resp = client.post(self._url("/herofin-service/otp/validate_new/"), json=payload)
                self.logger.info(f"POST otp/validate_new - {resp.status_code}")

                if resp.status_code not in (200, 201):
                    return {"status_code": resp.status_code, "error": resp.text}

                data = resp.json()
                
                # Check for Token (Accept 'access_token' or 'token')
                access_token = data.get("access_token") or data.get("token")
                
                # --- STRICT CHECK ---
                if not access_token:
                    # If status is 200 but no token, it's a Logic Failure
                    msg = data.get("message") or "Unknown error"
                    self.logger.error(f"Validate OTP: HTTP 200 but No Token. Msg: {msg}")
                    return {"status": "failed", "error": f"OTP Validation Failed: {msg}"}

                # Try to get App ID from Auth Response
                resolved_app_id = (
                    data.get("loan_id") or 
                    data.get("app_id") or 
                    data.get("application_id") or 
                    data.get("loan_application_id") or 
                    current_app_id
                )

                # ---------------------------------------------------------
                # SELF-HEALING (Only runs if we have a valid Token)
                # ---------------------------------------------------------
                if not resolved_app_id:
                    self.logger.info("⚠️ Login success but App ID missing. Attempting robust self-heal...")

                    # Strategy A: Contact Hint 
                    try:
                        hint_resp = client.get(self._url(f"/herofin-service/get-contact-hint/{phone_number}/"))
                        if hint_resp.status_code == 200:
                            hint_data = hint_resp.json()
                            resolved_app_id = hint_data.get("app_id") or hint_data.get("loan_application_id")
                    except Exception:
                        pass

                    # Strategy B: Dashboard/Home with Token
                    if not resolved_app_id:
                        self.logger.info("⚠️ Strategy A failed. Trying Strategy B: Fetch Dashboard with Token...")
                        try:
                            bearer_headers = {
                                "Authorization": f"Bearer {access_token}",
                                "Accept": "application/json"
                            }
                            dash_resp = client.get(self._url("/herofin-service/home/"), headers=bearer_headers)
                            if dash_resp.status_code == 200:
                                dash_data = dash_resp.json()
                                resolved_app_id = (
                                    dash_data.get("loan_id") or 
                                    dash_data.get("app_id") or
                                    dash_data.get("application_id") or
                                    (dash_data.get("loans") and dash_data["loans"][0].get("loan_id"))
                                )
                        except Exception as ex:
                            self.logger.warning(f"Strategy B failed: {ex}")

                    if resolved_app_id:
                        self.logger.info(f"✅ Self-heal successful. Found App ID: {resolved_app_id}")
                    else:
                        self.logger.error("❌ Self-heal failed. Session is authenticated but blind.")

                # Persist State
                updates = {
                    "access_token": access_token,
                    "phone_number": phone_number,
                    "user_details": data.get("user", {})
                }
                if resolved_app_id:
                    updates["app_id"] = resolved_app_id
                
                self.session_store.update(self.session_id, updates)
                self.logger.info(f"✅ Session {self.session_id} authenticated. keys_updated={list(updates.keys())}")
                
                return {
                    "status": "success",
                    "message": "OTP Verified. You are now logged in.",
                    "loan_id": resolved_app_id,
                    "user_details": data.get("user", {}),
                    "action": "Token secured in backend session."
                }

        except Exception as e:
            self.logger.error(f"OTP Validation Error: {e}")
            return {"error": str(e)}

    def is_logged_in(self):
        data = self.session_store.get(self.session_id) or {}
        return bool(data.get("access_token"))