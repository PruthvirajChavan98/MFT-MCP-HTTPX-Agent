import os
import httpx
import json
from typing import Optional, Any, Dict

from Loggers.StdOutLogger import StdoutLogger
from redis_session_store import RedisSessionStore
from token_reducer import JsonConverter  # <-- add this

conv = JsonConverter(sep=".")
log = StdoutLogger(name="hfcl_api")


def _valid_session_id(session_id: object) -> str:
    sid = str(session_id).strip() if session_id is not None else ""
    if not sid or sid.lower() in {"null", "none"}:
        raise ValueError(f"Invalid session_id: {session_id!r}")
    return sid


class HeroFincorpAPIs:
    """
    Wraps Bearer endpoints.

    Output policy (token-safe + token-cheap):
    - Public methods return VSC (string) ALWAYS.
    - Any token fields are stripped from output.
    """

    def __init__(self, session_id: str, session_store: Optional[RedisSessionStore] = None, base_url: Optional[str] = None):
        self.session_id = _valid_session_id(session_id)
        self.logger = log
        self.base_url = (base_url or os.getenv("CRM_BASE_URL", "http://localhost:8080")).rstrip("/")

        self.session_store = session_store or RedisSessionStore()

        # Hydrate Context from Redis
        session_data = self.session_store.get(self.session_id) or {}
        self.bearer_token = session_data.get("access_token")
        self.app_id = session_data.get("app_id")
        self.phone_number = session_data.get("phone_number")

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def _headers(self) -> Dict[str, str]:
        if not self.bearer_token:
            return {}
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _check_context(self) -> Optional[dict]:
        if not self.bearer_token:
            return {"error": "Authentication required. Please log in with OTP first."}
        if not self.app_id:
            return {"error": "No Loan Application ID found in session. Please log in."}
        return None

    # -------------------------
    # Output helpers: sanitize + VSC
    # -------------------------
    @staticmethod
    def _sanitize(obj: Any) -> Any:
        """Strip secrets from tool output (never leak tokens)."""
        if isinstance(obj, dict):
            clean: Dict[str, Any] = {}
            for k, v in obj.items():
                lk = str(k).lower()
                if lk in {"access_token", "token", "refresh_token", "id_token", "authorization"}:
                    continue
                clean[k] = HeroFincorpAPIs._sanitize(v)
            return clean
        if isinstance(obj, list):
            return [HeroFincorpAPIs._sanitize(x) for x in obj]
        return obj

    def _to_vsc(self, obj: Any) -> str:
        obj = self._sanitize(obj)
        # Ensure CSV has a key if primitive
        if not isinstance(obj, (dict, list)):
            obj = {"value": "" if obj is None else obj}
        vsc, _ = conv.json_to_vsc_text(obj)
        return vsc

    # -------------------------
    # HTTP plumbing (internal returns JSON-ish)
    # -------------------------
    def _handle(self, resp: httpx.Response) -> Any:
        if resp.status_code in (200, 201, 204, 208):
            try:
                out = resp.json()
                if isinstance(out, dict):
                    out.setdefault("status_code", resp.status_code)
                    return out
                return {"status_code": resp.status_code, "data": out}
            except Exception:
                return {"status_code": resp.status_code, "raw": resp.text[:5000]}
        return {"status_code": resp.status_code, "error": resp.text[:5000]}

    def _request(self, method: str, path: str, json_body: Optional[dict] = None) -> Any:
        ctx_err = self._check_context()
        if ctx_err and path != "/herofin-service/home":
            return ctx_err

        url = self._url(path)
        try:
            timeout = httpx.Timeout(30.0, connect=10.0)
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                headers = self._headers()
                if not headers:
                    return {"error": "Authentication Token missing. Please login."}

                resp = client.request(method, url, headers=headers, json=json_body)
                self.logger.info(f"{method} {url} - {resp.status_code}")
                return self._handle(resp)
        except Exception as e:
            self.logger.error(f"Request error: {e}")
            return {"error": str(e)}

    # -------------------------
    # REST endpoints (Public: VSC-only)
    # -------------------------
    def get_dashboard_home(self) -> str:
        out = self._request("GET", "/herofin-service/home")
        if isinstance(out, dict) and out.get("status_code") == 404:
            out = self._request("GET", "/herofin-service/home/")
        return self._to_vsc(out)

    def get_loan_details(self) -> str:
        if not self.app_id:
            return self._to_vsc({"error": "No App ID in session."})
        return self._to_vsc(self._request("GET", f"/herofin-service/loan/details/{self.app_id}/"))

    def get_foreclosure_details(self) -> str:
        if not self.app_id:
            return self._to_vsc({"error": "No App ID in session."})
        return self._to_vsc(self._request("GET", f"/herofin-service/loan/foreclosuredetails/{self.app_id}/"))

    def get_overdue_details(self) -> str:
        if not self.app_id:
            return self._to_vsc({"error": "No App ID in session."})
        return self._to_vsc(self._request("GET", f"/herofin-service/loan/overdue-details/{self.app_id}/"))

    def get_noc_details(self) -> str:
        if not self.app_id:
            return self._to_vsc({"error": "No App ID in session."})
        return self._to_vsc(self._request("GET", f"/herofin-service/loan/noc-details/{self.app_id}/"))

    def get_repayment_schedule(self) -> str:
        if not self.app_id:
            return self._to_vsc({"error": "No App ID in session."})
        return self._to_vsc(self._request("GET", f"/herofin-service/loan/repayment-schedule/{self.app_id}/"))

    def download_welcome_letter(self) -> str:
        return self._to_vsc(self._request("GET", "/herofin-service/download/welcome-letter/"))

    def download_soa(self, start_date: str, end_date: str) -> str:
        payload = {"start_date": start_date, "end_date": end_date}
        return self._to_vsc(self._request("POST", "/herofin-service/download/soa/", json_body=payload))

    def initiate_transaction(
        self,
        amount: str,
        otp: str,
        payment_type: str = "EMI",
        payment_mode: str = "UPI",
        latitude: str = "0",
        longitude: str = "0",
        emi_count: str = "1",
    ) -> str:
        if not self.app_id:
            return self._to_vsc({"error": "app_id missing in session"})
        if not self.phone_number:
            return self._to_vsc({"error": "phone_number missing in session"})

        payload = {
            "phone_number": self.phone_number,
            "otp": otp,
            "amount": amount,
            "paymentType": payment_type,
            "PaymentMode": payment_mode,
            "loan_app_id": self.app_id,
            "latitude": latitude,
            "longitude": longitude,
            "emiCount": emi_count,
        }
        return self._to_vsc(self._request("POST", "/payments/initiate_transaction/", json_body=payload))

    # -------------------------
    # Profile update: phone_number (Public: VSC-only + token-safe)
    # -------------------------
    def profile_phone_generate_otp(self, new_phone: str) -> str:
        payload = {"phone_number": new_phone}
        out = self._request("PUT", "/herofin-service/profiles/?update=phone_number", json_body=payload)
        return self._to_vsc(out)

    def profile_phone_validate_otp(self, new_phone: str, otp: str) -> str:
        payload = {"phone_number": new_phone, "otp": otp}
        out = self._request("PUT", "/herofin-service/profiles/?update=phone_number", json_body=payload)

        # Update Redis if token refreshes or phone changes (token never returned to caller)
        if isinstance(out, dict):
            token = out.get("access_token") or out.get("token")
            if token:
                self.session_store.update(self.session_id, {"access_token": token, "phone_number": new_phone})
            elif out.get("status") == "success":
                self.session_store.update(self.session_id, {"phone_number": new_phone})

        return self._to_vsc(out)