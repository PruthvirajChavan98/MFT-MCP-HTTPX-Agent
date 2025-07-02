# import httpx
# from Loggers.StdOutLogger import StdoutLogger
# from session_store import SessionStore

# # Instantiate session store (ideally shared instance across app)
# session_store = SessionStore()

# class HeroFincorpAPIs:
#     def __init__(self, session_id):
#         self.session_id = session_id
#         self.logger = StdoutLogger()
#         self.base_url = "https://herokuapi-dev.herofincorp.com"

#         # Load session data
#         session_data = session_store.get(session_id)
#         if not session_data:
#             raise ValueError(f"No session found for session_id: {session_id}")

#         self.bearer_token = session_data.get("access_token")
#         self.app_id = session_data.get("app_id")

#         if not self.bearer_token:
#             raise ValueError("Access token missing in session data")

#     def _create_headers(self):
#         return {
#             "Authorization": f"Bearer {self.bearer_token}",
#             "Content-Type": "application/json"
#         }

#     def _handle_response(self, response: httpx.Response):
#         if response.status_code in [200, 201, 208]:
#             return response.json()
#         return {
#             "status_code": response.status_code,
#             "error": response.text
#         }

#     def _request(self, method, endpoint, headers=None, json=None):
#         url = f"{self.base_url}{endpoint}"
#         try:
#             with httpx.Client() as client:
#                 response = client.request(method, url, headers=headers, json=json)
#                 self.logger.info(f"{method} {url} - {response.status_code}: {response.text}")
#                 return self._handle_response(response)
#         except httpx.RequestError as e:
#             self.logger.error(f"HTTP error occurred: {e}")
#             return {"error": str(e)}
#         except Exception as e:
#             self.logger.error(f"An error occurred: {e}")
#             return {"error": str(e)}

#     def get_dashboard_data(self):
#         return self._request("GET", "/herofin-service/home/", headers=self._create_headers())

#     def get_loan_details(self):
#         if not self.app_id:
#             return {"error": "App ID missing in session"}
#         return self._request("GET", f"/herofin-service/loan/details/{self.app_id}/", headers=self._create_headers())

#     def get_overdue_details(self):
#         if not self.app_id:
#             return {"error": "App ID missing in session"}
#         return self._request("GET", f"/herofin-service/loan_overdues/{self.app_id}/", headers=self._create_headers())

#     def get_repayment_schedule(self):
#         return self._request("GET", "/herofin-service/download/repayment-schedule", headers=self._create_headers())

#     def get_foreclosure_details(self):
#         if not self.app_id:
#             return {"error": "App ID missing in session"}
#         return self._request("GET", f"/herofin-service/loan/foreclosuredetails/{self.app_id}/", headers=self._create_headers())

#     def download_noc_letter(self):
#         return self._request("POST", "/herofin-service/download/noc-letter/", headers=self._create_headers())


# 2

import httpx
from Loggers.StdOutLogger import StdoutLogger
from session_store import SessionStore

# Instantiate session store (ideally shared instance across app)
session_store = SessionStore()

class HeroFincorpAPIs:
    def __init__(self, session_id):
        self.session_id = session_id
        self.logger = StdoutLogger()
        self.base_url = "https://herokuapi-dev.herofincorp.com"

        # Load session data
        session_data = session_store.get(session_id)
        if not session_data:
            raise ValueError(f"No session found for session_id: {session_id}")

        self.bearer_token = session_data.get("access_token")
        self.app_id = session_data.get("app_id")

        if not self.bearer_token:
            raise ValueError("Access token missing in session data")

    def _create_headers(self):
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json"
        }

    def _handle_response(self, response: httpx.Response):
        if response.status_code in [200, 201, 208]:
            return response.json()
        return {
            "status_code": response.status_code,
            "error": response.text
        }

    def _request(self, method, endpoint, headers=None, json=None):
        url = f"{self.base_url}{endpoint}"
        try:
            # Set a custom timeout (e.g., 30 seconds for connect/read)
            timeout = httpx.Timeout(30.0, connect=10.0)
            with httpx.Client(timeout=timeout) as client:
                response = client.request(method, url, headers=headers, json=json)
                self.logger.info(f"{method} {url} - {response.status_code}: {response.text}")
                return self._handle_response(response)
        except httpx.ReadTimeout as e:
            self.logger.error(f"Read timeout occurred: {e}")
            return {"error": "The request timed out while reading the response from the server."}
        except httpx.RequestError as e:
            self.logger.error(f"HTTP error occurred: {e}")
            return {"error": f"HTTP request error: {str(e)}"}
        except Exception as e:
            self.logger.error(f"An error occurred: {e}")
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
        """
        Updates the bike profile for the user (NOC flow).

        Args:
            chassis_no (str): Chassis number of the bike
            engine_no (str): Engine number of the bike
            vehicle_number (str): Vehicle registration number
            image_ref (str): Reference string for the uploaded RC image

        Returns:
            dict: API response
        """
        payload = {
            "case_type": "noc",
            "chassis_no": chassis_no,
            "engine_no": engine_no,
            "vehicle_number": vehicle_number,
            "bike_rc": [
                {
                    "imageUrl": image_base64
                }
            ],
            "file_name": f"{self.app_id}_{self.session_id}.jpg"
        }
        return self._request(
            "PUT",
            "/herofin-service/profiles/?update=bike",
            headers=self._create_headers(),
            json=payload
        )