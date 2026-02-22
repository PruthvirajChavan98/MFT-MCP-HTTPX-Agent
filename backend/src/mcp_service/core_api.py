import logging
from typing import Any, Dict, Optional

import httpx

from .config import CRM_BASE_URL
from .session_store import RedisSessionStore
from .utils import JsonConverter, ToonOptions

conv = JsonConverter(sep=".")
log = logging.getLogger(name="mft_api")

_CRM_TIMEOUT = httpx.Timeout(connect=5.0, read=25.0, write=10.0, pool=5.0)


def _valid_session_id(session_id: object) -> str:
    sid = str(session_id).strip() if session_id is not None else ""
    if not sid or sid.lower() in {"null", "none"}:
        raise ValueError(f"Invalid session_id: {session_id!r}")
    return sid


class MockFinTechAPIs:
    def __init__(self, session_id: str, session_store: Optional[RedisSessionStore] = None):
        self.session_id = _valid_session_id(session_id)
        self.logger = log
        self.base_url = CRM_BASE_URL
        self.session_store = session_store or RedisSessionStore()
        self.bearer_token: Optional[str] = None
        self.app_id: Optional[str] = None
        self.loan_id: Optional[str] = None
        self.phone_number: Optional[str] = None
        self._hydrate()

    def _hydrate(self) -> None:
        s = self.session_store.get(self.session_id) or {}
        self.bearer_token = s.get("access_token")
        self.app_id = s.get("app_id")
        self.loan_id = s.get("loan_id")
        self.phone_number = s.get("phone_number")

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def _headers(self) -> Dict[str, str]:
        self._hydrate()
        if not self.bearer_token:
            return {}
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _check_context(self) -> Optional[dict]:
        self._hydrate()
        if not self.bearer_token:
            return {"error": "Auth token missing."}
        if not self.app_id:
            return {"error": "app_id missing."}
        return None

    def _to_toon(self, obj: Any) -> str:
        if not isinstance(obj, (dict, list)):
            obj = {"value": obj}
        try:
            return conv.json_to_toon_text(
                obj, options=ToonOptions(delimiter="|", indent=2, length_marker="")
            )
        except RuntimeError:
            import json

            return json.dumps(obj, indent=2)

    def _request(self, method: str, path: str, json_body: Optional[dict] = None) -> Any:
        self._hydrate()
        ctx_err = self._check_context()
        if ctx_err and "home" not in path:
            return ctx_err

        try:
            with httpx.Client(timeout=_CRM_TIMEOUT) as client:
                resp = client.request(
                    method, self._url(path), headers=self._headers(), json=json_body
                )
                self.logger.info(f"{method} {path} - {resp.status_code}")
                try:
                    return resp.json()
                except Exception:
                    return {"status_code": resp.status_code, "raw": resp.text[:1000]}
        except Exception as e:
            return {"error": str(e)}

    def get_dashboard_home(self) -> str:
        return self._to_toon(self._request("GET", "/mockfin-service/home"))

    def get_loan_details(self) -> str:
        if not self.app_id:
            return self._to_toon({"error": "No app_id"})
        return self._to_toon(self._request("GET", f"/mockfin-service/loan/details/{self.app_id}/"))

    def get_foreclosure_details(self) -> str:
        if not self.app_id:
            return self._to_toon({"error": "No app_id"})
        return self._to_toon(
            self._request("GET", f"/mockfin-service/loan/foreclosuredetails/{self.app_id}/")
        )

    def get_overdue_details(self) -> str:
        if not self.app_id:
            return self._to_toon({"error": "No app_id"})
        return self._to_toon(
            self._request("GET", f"/mockfin-service/loan/overdue-details/{self.app_id}/")
        )

    def get_noc_details(self) -> str:
        if not self.app_id:
            return self._to_toon({"error": "No app_id"})
        return self._to_toon(
            self._request("GET", f"/mockfin-service/loan/noc-details/{self.app_id}/")
        )

    def get_repayment_schedule(self) -> str:
        ident = self.app_id or self.loan_id
        if not ident:
            return self._to_toon({"error": "No app_id/loan_id"})
        return self._to_toon(
            self._request("GET", f"/mockfin-service/loan/repayment-schedule/{ident}/")
        )

    def download_welcome_letter(self) -> str:
        return self._to_toon(self._request("GET", "/mockfin-service/download/welcome-letter/"))

    def download_soa(self, start_date: str, end_date: str) -> str:
        return self._to_toon(
            self._request(
                "POST",
                "/mockfin-service/download/soa/",
                json_body={"start_date": start_date, "end_date": end_date},
            )
        )

    def initiate_transaction(self, amount: str, otp: str, payment_mode: str = "UPI") -> str:
        payload = {
            "phone_number": self.phone_number,
            "otp": otp,
            "amount": amount,
            "PaymentMode": payment_mode,
            "loan_app_id": self.app_id,
        }
        return self._to_toon(
            self._request("POST", "/payments/initiate_transaction/", json_body=payload)
        )

    def profile_phone_generate_otp(self, new_phone: str) -> str:
        return self._to_toon(
            self._request(
                "PUT",
                "/mockfin-service/profiles/?update=phone_number",
                json_body={"phone_number": new_phone},
            )
        )

    def profile_phone_validate_otp(self, new_phone: str, otp: str) -> str:
        return self._to_toon(
            self._request(
                "PUT",
                "/mockfin-service/profiles/?update=phone_number",
                json_body={"phone_number": new_phone, "otp": otp},
            )
        )
