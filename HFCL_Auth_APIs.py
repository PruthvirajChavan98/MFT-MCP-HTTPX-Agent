import httpx
from Loggers.StdOutLogger import StdoutLogger
from redis_session_store import RedisSessionStore

log = StdoutLogger(name="hfcl_auth")
session_store = RedisSessionStore()

def _valid_session_id(session_id: object) -> str:
    sid = str(session_id).strip() if session_id is not None else ""
    if not sid or sid.lower() in {"null", "none"}:
        raise ValueError(f"Invalid session_id: {session_id!r}")
    return sid

class HeroFincorpAuthAPIs:
    def __init__(self, session_id):
        self.session_id = _valid_session_id(session_id)
        self.base_url = "https://herokuapi-dev.herofincorp.com"
        self.auth = httpx.BasicAuth("mobile-client", "5PhxdQ4r9PY7gh")
        self.logger = log
        self.session_store = session_store

    def generate_otp(self, user_input: str):
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        user_input = (user_input or "").strip()

        # ✅ Touch session immediately so key exists in Redis
        self.session_store.update(self.session_id, {
            "last_generate_otp_input": user_input,
        })

        if not user_input.isdigit():
            self.session_store.update(self.session_id, {"last_generate_otp_error": "non-digit input"})
            return {"error": "Invalid input. Digits only."}

        try:
            with httpx.Client(auth=self.auth, headers=headers, follow_redirects=True) as client:
                phone_number = None
                app_id = None

                if len(user_input) == 10:
                    phone_number = user_input

                elif 5 <= len(user_input) <= 8:
                    hint = client.get(f"{self.base_url}/herofin-service/get-contact-hint/{user_input}/")
                    if hint.status_code != 200:
                        self.session_store.update(self.session_id, {
                            "last_contact_hint_status": hint.status_code,
                            "last_contact_hint_error": hint.text,
                        })
                        return {"status_code": hint.status_code, "error": hint.text}

                    hint_data = hint.json()
                    phone_number = hint_data.get("phone_number")
                    app_id = hint_data.get("app_id")

                else:
                    self.session_store.update(self.session_id, {"last_generate_otp_error": "bad length"})
                    return {"error": "Provide 10-digit phone or 5–8 digit app_id."}

                # ✅ Persist resolved values even if OTP fails
                self.session_store.update(self.session_id, {
                    "phone_number": phone_number,
                    "app_id": app_id,
                })

                if not phone_number:
                    self.session_store.update(self.session_id, {"last_generate_otp_error": "phone_number not resolved"})
                    return {"error": "Could not resolve phone number."}

                payload = {"phone_number": phone_number, "app_id": app_id}
                resp = client.post(f"{self.base_url}/herofin-service/otp/generate_new/", json=payload)
                self.logger.info(f"POST otp/generate_new - {resp.status_code}")

                # ✅ Always record OTP attempt result
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
        # ✅ Touch session so you can see attempts
        self.session_store.update(self.session_id, {"last_validate_otp_input": otp})

        session_data = self.session_store.get(self.session_id)
        if not session_data:
            return {"error": "Session not found or expired"}

        phone_number = session_data.get("phone_number")
        app_id = session_data.get("app_id")

        if not phone_number:
            return {"error": "phone_number missing in session"}

        url = f"{self.base_url}/herofin-service/otp/validate_new/"
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        payload = {"phone_number": phone_number, "app_id": app_id, "otp": otp}

        try:
            with httpx.Client(auth=self.auth, headers=headers, follow_redirects=True) as client:
                resp = client.post(url, json=payload)
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

                if not access_token:
                    return {"error": "access_token missing in validate response"}

                self.session_store.update(self.session_id, {
                    "access_token": access_token,
                    "app_id": resolved_app_id,
                    "phone_number": phone_number,
                })

                return {
                    "status": "OTP Validated",
                    "access_token": access_token,
                    "app_id": resolved_app_id,
                    "phone_number": phone_number,
                }

        except Exception as e:
            self.logger.error(f"OTP Validation Error: {e}")
            self.session_store.update(self.session_id, {"last_validate_otp_exception": str(e)})
            return {"error": str(e)}

    def is_logged_in(self):
        data = self.session_store.get(self.session_id)
        return bool(data and data.get("access_token"))
