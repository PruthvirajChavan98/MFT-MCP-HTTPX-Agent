import os
import httpx
from typing import Optional, Any, Dict

from Loggers.StdOutLogger import StdoutLogger
from redis_session_store import RedisSessionStore

log = StdoutLogger(name="hfcl_api")

def _valid_session_id(session_id: object) -> str:
    sid = str(session_id).strip() if session_id is not None else ""
    if not sid or sid.lower() in {"null", "none"}:
        raise ValueError(f"Invalid session_id: {session_id!r}")
    return sid

class HeroFincorpAPIs:
    """
    Wraps Bearer endpoints.
    
    CRITICAL CHANGE:
    - __init__ loads context (app_id, access_token) from Redis.
    - All methods are PARAMETER-LESS regarding ID/Auth (except transactional inputs).
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

        # Note: We do NOT raise here, because we might want to check methods that 
        # return a "Please Login" error cleanly rather than crashing the constructor.

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def _headers(self) -> Dict[str, str]:
        if not self.bearer_token:
            return {} # Will likely cause 401, which is handled
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _check_context(self) -> Optional[dict]:
        """Helper to return error if context is missing."""
        if not self.bearer_token:
            return {"error": "Authentication required. Please log in with OTP first."}
        if not self.app_id:
            return {"error": "No Loan Application ID found in session. Please log in."}
        return None

    def _handle(self, resp: httpx.Response) -> Any:
        if resp.status_code in (200, 201, 204, 208):
            try:
                return resp.json()
            except Exception:
                return {"status_code": resp.status_code, "raw": resp.text}
        return {"status_code": resp.status_code, "error": resp.text}

    def _request(self, method: str, path: str, json: Optional[dict] = None) -> Any:
        # 1. Check Context
        ctx_err = self._check_context()
        if ctx_err and path != "/herofin-service/home": 
            # Allow home to fail gracefully or serve partial content, but usually requires auth
            return ctx_err

        url = self._url(path)
        try:
            timeout = httpx.Timeout(30.0, connect=10.0)
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                headers = self._headers()
                if not headers:
                     return {"error": "Authentication Token missing. Please login."}
                
                resp = client.request(method, url, headers=headers, json=json)
                self.logger.info(f"{method} {url} - {resp.status_code}")
                return self._handle(resp)
        except Exception as e:
            self.logger.error(f"Request error: {e}")
            return {"error": str(e)}

    # -------------------------
    # REST endpoints (Auto-Context)
    # -------------------------
    
    def get_dashboard_home(self):
        """Fetches home dashboard for the current session user."""
        # Try both, since some routers support /home and /home/
        out = self._request("GET", "/herofin-service/home")
        if isinstance(out, dict) and out.get("status_code") == 404:
            return self._request("GET", "/herofin-service/home/")
        return out

    def get_loan_details(self):
        """Fetches loan details for the current session app_id."""
        if not self.app_id: return {"error": "No App ID in session."}
        return self._request("GET", f"/herofin-service/loan/details/{self.app_id}/")

    def get_foreclosure_details(self):
        """Fetches foreclosure details for the current session app_id."""
        if not self.app_id: return {"error": "No App ID in session."}
        return self._request("GET", f"/herofin-service/loan/foreclosuredetails/{self.app_id}/")

    def get_overdue_details(self):
        """Fetches overdue details for the current session app_id."""
        if not self.app_id: return {"error": "No App ID in session."}
        return self._request("GET", f"/herofin-service/loan/overdue-details/{self.app_id}/")

    def get_noc_details(self):
        """Fetches NOC details for the current session app_id."""
        if not self.app_id: return {"error": "No App ID in session."}
        return self._request("GET", f"/herofin-service/loan/noc-details/{self.app_id}/")

    def get_repayment_schedule(self):
        """Fetches repayment schedule for the current session app_id."""
        if not self.app_id: return {"error": "No App ID in session."}
        return self._request("GET", f"/herofin-service/loan/repayment-schedule/{self.app_id}/")

    def download_welcome_letter(self):
        """Downloads welcome letter for the current session."""
        return self._request("GET", "/herofin-service/download/welcome-letter/")

    def download_soa(self, start_date: str, end_date: str):
        """Downloads SOA. Only requires dates, app_id is inferred."""
        payload = {"start_date": start_date, "end_date": end_date}
        return self._request("POST", "/herofin-service/download/soa/", json=payload)

    def initiate_transaction(
        self,
        amount: str,
        otp: str,
        payment_type: str = "EMI",
        payment_mode: str = "UPI",
        latitude: str = "0",
        longitude: str = "0",
        emi_count: str = "1"
    ):
        """
        Initiates payment.
        Requires User Input: amount, otp.
        Infers: app_id, phone_number from Redis.
        """
        if not self.app_id: return {"error": "app_id missing in session"}
        if not self.phone_number: return {"error": "phone_number missing in session"}

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
        return self._request("POST", "/payments/initiate_transaction/", json=payload)

    # -------------------------
    # Profile update: phone_number
    # -------------------------
    def profile_phone_generate_otp(self, new_phone: str):
        payload = {"phone_number": new_phone}
        return self._request("PUT", "/herofin-service/profiles/?update=phone_number", json=payload)

    def profile_phone_validate_otp(self, new_phone: str, otp: str):
        payload = {"phone_number": new_phone, "otp": otp}
        out = self._request("PUT", "/herofin-service/profiles/?update=phone_number", json=payload)

        # Update Redis if token refreshes or phone changes
        if isinstance(out, dict):
            token = out.get("access_token") or out.get("token")
            if token:
                self.session_store.update(self.session_id, {"access_token": token, "phone_number": new_phone})
            elif out.get("status") == "success": # If successful but no new token, update phone
                 self.session_store.update(self.session_id, {"phone_number": new_phone})

        return out
