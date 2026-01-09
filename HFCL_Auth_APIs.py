# =========================
# HFCL_Auth_APIs.py
# =========================
import os
import json
import httpx
from typing import Optional, Any, Dict

from Loggers.StdOutLogger import StdoutLogger
from redis_session_store import RedisSessionStore
from token_reducer import JsonConverter

conv = JsonConverter(sep=".")
log = StdoutLogger(name="hfcl_auth")


def _valid_session_id(session_id: object) -> str:
    sid = str(session_id).strip() if session_id is not None else ""
    if not sid or sid.lower() in {"null", "none"}:
        raise ValueError(f"Invalid session_id: {session_id!r}")
    return sid


class HeroFincorpAuthAPIs:
    """
    Wraps REST auth-ish endpoints.

    Output policy:
    - Methods return VSC (string) ALWAYS.
    - Never return tokens (token stays in Redis session).
    - app_id and loan_id are stored separately (never overwrite app_id with loan_id).
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

    def _to_vsc(self, obj: Any, explode_key: Optional[str] = None) -> str:
        vsc, _ = conv.json_to_vsc_text(
            obj,
            include_header=True,
            preserve_key_order=True,
            explode_key=explode_key,
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
            with httpx.Client(auth=self.auth, headers=headers, follow_redirects=True, timeout=20.0) as client:
                resp = client.get(self._url(f"/herofin-service/get-contact-hint/{app_id}/"))

                self.session_store.update(self.session_id, {
                    "last_contact_hint_app_id": app_id,
                    "last_contact_hint_status": resp.status_code,
                    "last_contact_hint_response": resp.text[:5000],
                })

                if resp.status_code != 200:
                    return self._to_vsc({"status_code": resp.status_code, "error": resp.text[:5000]})

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
        """
        IMPORTANT: if user_input is a PHONE NUMBER, we do NOT call get_contact_hint.
        We call generate_new with just phone_number and store app_id from the response (DIRECT).
        """
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        user_input = (user_input or "").strip()
        self.session_store.update(self.session_id, {"last_generate_otp_input": user_input})

        if not user_input:
            return self._to_vsc({"error": "Provide phone_number or app_id"})

        try:
            with httpx.Client(auth=self.auth, headers=headers, follow_redirects=True, timeout=30.0) as client:
                phone_number: Optional[str] = None
                app_id: Optional[str] = None

                if self._is_phone(user_input):
                    # ✅ no contact hint here
                    phone_number = user_input
                    self.session_store.update(self.session_id, {"phone_number": phone_number})
                else:
                    # app_id-like input: we must resolve phone to send OTP
                    app_id = user_input
                    hint = {}
                    for path in (f"/herofin-service/get-contact-hint/{app_id}/", f"/herofin-service/get-contact-hint/{app_id}"):
                        try:
                            r = client.get(self._url(path))
                            if r.status_code == 200:
                                hint = r.json()
                                break
                        except Exception:
                            pass

                    phone_number = hint.get("phone_number")
                    app_id = (
                        hint.get("app_id")
                        or hint.get("loan_application_id")
                        or hint.get("application_id")
                        or app_id
                    )

                    self.session_store.update(self.session_id, {"phone_number": phone_number, "app_id": app_id})

                if not phone_number:
                    return self._to_vsc({"error": "Could not resolve phone number for OTP generation"})

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

                # Even if you didn't send app_id, server returns it (DIRECT). Store it.
                resp_json: Dict[str, Any] = {}
                try:
                    resp_json = resp.json() if resp.text else {}
                except Exception:
                    resp_json = {}

                if isinstance(resp_json, dict):
                    resp_app_id = resp_json.get("app_id")
                    if resp_app_id:
                        self.session_store.update(self.session_id, {"app_id": resp_app_id})
                        app_id = app_id or resp_app_id  # for response only

                if resp.status_code in (200, 201):
                    # soft-error check
                    try:
                        msg = (resp_json.get("message") or resp_json.get("detail") or "").lower()
                        if any(k in msg for k in ("invalid", "expired", "failed", "error")):
                            return self._to_vsc({
                                "status_code": 422,
                                "error": resp_json.get("message") or resp_json.get("detail") or resp.text,
                                "hint": "OTP generate returned a soft-error body.",
                            })
                    except Exception:
                        pass

                    return self._to_vsc({
                        "status": "OTP Sent",
                        "phone_number": phone_number,
                        "app_id": app_id,
                        "message": resp_json.get("message") or "OTP has been sent to your registered mobile number.",
                    })

                return self._to_vsc({"status_code": resp.status_code, "error": resp.text[:5000]})

        except Exception as e:
            self.logger.error(f"OTP Generation Error: {e}")
            return self._to_vsc({"error": str(e)})

    def validate_otp(self, otp: str) -> str:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        otp = (otp or "").strip()
        self.session_store.update(self.session_id, {"last_validate_otp_input": otp})

        session_data = self.session_store.get(self.session_id) or {}
        phone_number = (session_data.get("phone_number") or "").strip() or None
        app_id = (session_data.get("app_id") or "").strip() or None

        if not phone_number:
            return self._to_vsc({"error": "Phone number missing in session. Please request OTP first."})

        # If app_id still missing, try extracting from last_generate_otp_response JSON
        if not app_id:
            raw = session_data.get("last_generate_otp_response") or ""
            try:
                j = json.loads(raw) if raw and raw.lstrip().startswith("{") else {}
                if isinstance(j, dict) and j.get("app_id"):
                    app_id = str(j["app_id"])
                    self.session_store.update(self.session_id, {"app_id": app_id})
            except Exception:
                pass

        if not app_id:
            return self._to_vsc({"error": "app_id missing in session. Generate OTP first (server returns app_id= DIRECT) and retry."})

        payload = {"phone_number": phone_number, "app_id": app_id, "otp": otp}

        try:
            with httpx.Client(auth=self.auth, headers=headers, follow_redirects=True, timeout=30.0) as client:
                resp = client.post(self._url("/herofin-service/otp/validate_new/"), json=payload)
                self.logger.info(f"POST otp/validate_new - {resp.status_code}")

                if resp.status_code not in (200, 201):
                    return self._to_vsc({"status_code": resp.status_code, "error": resp.text[:5000]})

                auth_data = resp.json() if resp.text else {}
                if not isinstance(auth_data, dict):
                    return self._to_vsc({"status_code": resp.status_code, "error": "Unexpected response type"})

                access_token = auth_data.get("access_token") or auth_data.get("token")
                if not access_token:
                    msg = auth_data.get("message") or "Unknown error"
                    self.logger.error(f"Validate OTP: HTTP 200 but No Token. Msg: {msg}")
                    return self._to_vsc({"status": "failed", "error": f"OTP Validation Failed: {msg}"})

                loan_id = auth_data.get("loan_id") or auth_data.get("loanId") or session_data.get("loan_id")

                updates: Dict[str, Any] = {
                    "access_token": access_token,  # stored only
                    "phone_number": phone_number,
                    "app_id": app_id,              # keep app_id as DIRECT
                    "user_details": auth_data.get("user", {}) if isinstance(auth_data.get("user"), dict) else {},
                }
                if loan_id:
                    updates["loan_id"] = loan_id

                self.session_store.update(self.session_id, updates)
                self.logger.info(f"✅ Session {self.session_id} authenticated. keys_updated={list(updates.keys())}")

                return self._to_vsc({
                    "status": "success",
                    "message": auth_data.get("message") or "OTP Verified. You are now logged in.",
                    "app_id": app_id,
                    "loan_id": loan_id,
                    "user_details": updates["user_details"],
                    "action": "Token secured in backend session.",
                })

        except Exception as e:
            self.logger.error(f"OTP Validation Error: {e}")
            return self._to_vsc({"error": str(e)})

    def is_logged_in(self) -> bool:
        data = self.session_store.get(self.session_id) or {}
        return bool(data.get("access_token"))
