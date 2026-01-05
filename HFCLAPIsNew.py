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
    Wraps Bearer endpoints from your Postman collection (baseUrl = CRM_BASE_URL):

      GET  /herofin-service/home
      GET  /herofin-service/loan/details/{appId}/
      GET  /herofin-service/loan/foreclosuredetails/{appId}/
      GET  /herofin-service/loan/overdue-details/{appId}/
      GET  /herofin-service/loan/noc-details/{appId}/
      GET  /herofin-service/loan/repayment-schedule/{appId}/
      PUT  /herofin-service/profiles/?update=phone_number        (step1, step2)
      GET  /herofin-service/download/welcome-letter/
      POST /herofin-service/download/soa/
      POST /payments/initiate_transaction/
    """

    def __init__(self, session_id: str, session_store: Optional[RedisSessionStore] = None, base_url: Optional[str] = None):
        self.session_id = _valid_session_id(session_id)
        self.logger = log
        self.base_url = (base_url or os.getenv("CRM_BASE_URL", "http://localhost:8080")).rstrip("/")

        self.session_store = session_store or RedisSessionStore()
        session_data = self.session_store.get(self.session_id) or {}

        self.bearer_token = session_data.get("access_token")
        self.app_id = session_data.get("app_id")
        self.phone_number = session_data.get("phone_number")

        if not self.bearer_token:
            raise ValueError("Access token missing in session data (run validate_otp first)")

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _handle(self, resp: httpx.Response) -> Any:
        if resp.status_code in (200, 201, 204, 208):
            try:
                return resp.json()
            except Exception:
                return {"status_code": resp.status_code, "raw": resp.text}
        return {"status_code": resp.status_code, "error": resp.text}

    def _request(self, method: str, path: str, json: Optional[dict] = None) -> Any:
        url = self._url(path)
        try:
            timeout = httpx.Timeout(30.0, connect=10.0)
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.request(method, url, headers=self._headers(), json=json)
                self.logger.info(f"{method} {url} - {resp.status_code}")
                return self._handle(resp)
        except Exception as e:
            self.logger.error(f"Request error: {e}")
            return {"error": str(e)}

    # -------------------------
    # REST endpoints (Bearer)
    # -------------------------
    def get_dashboard_home(self):
        # Try both, since some routers support /home and /home/
        out = self._request("GET", "/herofin-service/home")
        if isinstance(out, dict) and out.get("status_code") == 404:
            return self._request("GET", "/herofin-service/home/")
        return out

    def get_loan_details(self, app_id: Optional[str] = None):
        aid = app_id or self.app_id
        if not aid:
            return {"error": "app_id missing (provide app_id or login first)"}
        return self._request("GET", f"/herofin-service/loan/details/{aid}/")

    def get_foreclosure_details(self, app_id: Optional[str] = None):
        aid = app_id or self.app_id
        if not aid:
            return {"error": "app_id missing"}
        return self._request("GET", f"/herofin-service/loan/foreclosuredetails/{aid}/")

    def get_overdue_details(self, app_id: Optional[str] = None):
        aid = app_id or self.app_id
        if not aid:
            return {"error": "app_id missing"}
        return self._request("GET", f"/herofin-service/loan/overdue-details/{aid}/")

    def get_noc_details(self, app_id: Optional[str] = None):
        aid = app_id or self.app_id
        if not aid:
            return {"error": "app_id missing"}
        return self._request("GET", f"/herofin-service/loan/noc-details/{aid}/")

    def get_repayment_schedule(self, app_id: Optional[str] = None):
        aid = app_id or self.app_id
        if not aid:
            return {"error": "app_id missing"}
        return self._request("GET", f"/herofin-service/loan/repayment-schedule/{aid}/")

    def download_welcome_letter(self):
        return self._request("GET", "/herofin-service/download/welcome-letter/")

    def download_soa(self, start_date: str, end_date: str):
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
        emi_count: str = "1",
        app_id: Optional[str] = None,
        phone_number: Optional[str] = None,
    ):
        aid = app_id or self.app_id
        phone = phone_number or self.phone_number
        if not aid:
            return {"error": "app_id missing"}
        if not phone:
            return {"error": "phone_number missing"}

        payload = {
            "phone_number": phone,
            "otp": otp,
            "amount": amount,
            "paymentType": payment_type,
            "PaymentMode": payment_mode,
            "loan_app_id": aid,
            "latitude": latitude,
            "longitude": longitude,
            "emiCount": emi_count,
        }
        return self._request("POST", "/payments/initiate_transaction/", json=payload)

    # -------------------------
    # Profile update: phone_number (Bearer)
    # -------------------------
    def profile_phone_generate_otp(self, new_phone: str):
        # Step 1: body has only phone_number
        payload = {"phone_number": new_phone}
        return self._request("PUT", "/herofin-service/profiles/?update=phone_number", json=payload)

    def profile_phone_validate_otp(self, new_phone: str, otp: str):
        # Step 2: phone_number + otp, may return access_token -> update session
        payload = {"phone_number": new_phone, "otp": otp}
        out = self._request("PUT", "/herofin-service/profiles/?update=phone_number", json=payload)

        if isinstance(out, dict):
            token = out.get("access_token") or out.get("token")
            if token:
                self.session_store.update(self.session_id, {"access_token": token, "phone_number": new_phone})

        return out

    # -------------------------
    # Existing NOC flow (kept)
    # -------------------------
    def make_noc_request(self, chassis_no: str, engine_no: str, vehicle_number: str, image_base64: str):
        payload = {
            "case_type": "noc",
            "chassis_no": chassis_no,
            "engine_no": engine_no,
            "vehicle_number": vehicle_number,
            "bike_rc": [{"imageUrl": image_base64}],
            "file_name": f"{self.app_id}_{self.session_id}.jpg",
        }
        return self._request("PUT", "/herofin-service/profiles/?update=bike", json=payload)
