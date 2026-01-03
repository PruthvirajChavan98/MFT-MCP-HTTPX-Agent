import httpx
from Loggers.StdOutLogger import StdoutLogger
from redis_session_store import RedisSessionStore

log = StdoutLogger(name="hfcl_api")

# IMPORTANT: use centralized REDIS_URL (same Redis you inspect)
session_store = RedisSessionStore()

def _valid_session_id(session_id: object) -> str:
    sid = str(session_id).strip() if session_id is not None else ""
    if not sid or sid.lower() in {"null", "none"}:
        raise ValueError(f"Invalid session_id: {session_id!r}")
    return sid

class HeroFincorpAPIs:
    def __init__(self, session_id):
        self.session_id = _valid_session_id(session_id)
        self.logger = log
        self.base_url = "https://herokuapi-dev.herofincorp.com"

        session_data = session_store.get(self.session_id)
        if not session_data:
            raise ValueError(f"No session found for session_id: {self.session_id}")

        self.bearer_token = session_data.get("access_token")
        self.app_id = session_data.get("app_id")

        if not self.bearer_token:
            raise ValueError("Access token missing in session data")

    def _create_headers(self):
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _handle_response(self, response: httpx.Response):
        if response.status_code in [200, 201, 208]:
            return response.json()
        return {"status_code": response.status_code, "error": response.text}

    def _request(self, method, endpoint, headers=None, json=None):
        url = f"{self.base_url}{endpoint}"
        try:
            timeout = httpx.Timeout(30.0, connect=10.0)
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.request(method, url, headers=headers, json=json)
                self.logger.info(f"{method} {url} - {resp.status_code}")
                return self._handle_response(resp)
        except Exception as e:
            self.logger.error(f"Request error: {e}")
            return {"error": str(e)}

    def get_dashboard_data(self):
        return self._request("GET", "/herofin-service/home/", headers=self._create_headers())

    def get_loan_details(self):
        if not self.app_id:
            return {"error": "App ID missing in session"}
        return self._request("GET", f"/herofin-service/loan/details/{self.app_id}/", headers=self._create_headers())

    def get_overdue_details(self):
        if not self.app_id:
            return {"error": "App ID missing in session"}
        return self._request("GET", f"/herofin-service/loan_overdues/{self.app_id}/", headers=self._create_headers())

    def get_repayment_schedule(self):
        return self._request("GET", "/herofin-service/download/repayment-schedule", headers=self._create_headers())

    def get_foreclosure_details(self):
        if not self.app_id:
            return {"error": "App ID missing in session"}
        return self._request("GET", f"/herofin-service/loan/foreclosuredetails/{self.app_id}/", headers=self._create_headers())

    def download_noc_letter(self):
        return self._request("POST", "/herofin-service/download/noc-letter/", headers=self._create_headers())

    def make_noc_request(self, chassis_no: str, engine_no: str, vehicle_number: str, image_base64: str):
        payload = {
            "case_type": "noc",
            "chassis_no": chassis_no,
            "engine_no": engine_no,
            "vehicle_number": vehicle_number,
            "bike_rc": [{"imageUrl": image_base64}],
            "file_name": f"{self.app_id}_{self.session_id}.jpg",
        }
        return self._request(
            "PUT",
            "/herofin-service/profiles/?update=bike",
            headers=self._create_headers(),
            json=payload,
        )
