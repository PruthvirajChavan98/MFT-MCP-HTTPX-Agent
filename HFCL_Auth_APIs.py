# import httpx
# from Loggers.StdOutLogger import StdoutLogger

# class HeroFincorpAuthAPI:
#     def __init__(self):
#         self.base_url = "https://herokuapi-dev.herofincorp.com"
#         self.auth = httpx.BasicAuth("mobile-client", "5PhxdQ4r9PY7gh")
#         self.logger = StdoutLogger()

#     def generate_otp(self, user_input: str):
#         headers = {
#             "Content-Type": "application/json",
#             "Accept": "application/json"
#         }

#         try:
#             with httpx.Client(auth=self.auth, headers=headers, follow_redirects=True) as client:
#                 if len(user_input) == 10 and user_input.isdigit():
#                     payload = {"phone_number": user_input}
#                     response = client.post(f"{self.base_url}/herofin-service/otp/generate_new/", json=payload)
#                     phone_number = user_input
#                     app_id = None

#                 elif 5 <= len(user_input) <= 8 and user_input.isdigit():
#                     contact_hint_resp = client.get(f"{self.base_url}/herofin-service/get-contact-hint/{user_input}/")
#                     if contact_hint_resp.status_code != 200:
#                         return {"status_code": contact_hint_resp.status_code, "error": contact_hint_resp.text}

#                     contact_hint_data = contact_hint_resp.json()
#                     phone_number = contact_hint_data.get("phone_number")
#                     app_id = contact_hint_data.get("app_id")

#                     if not phone_number or not app_id:
#                         return {"error": "Invalid contact hint response"}

#                     payload = {"phone_number": phone_number, "app_id": app_id}
#                     response = client.post(f"{self.base_url}/herofin-service/otp/generate_new/", json=payload)
#                 else:
#                     return {"error": "Invalid input. Provide 10-digit phone number or 5–8 digit app_id."}

#                 self.logger.info(f"POST OTP - {response.status_code}: {response.text}")
#                 if response.status_code in [200, 201]:
#                     return {
#                         "status": "OTP Sent",
#                         "phone_number": phone_number,
#                         "app_id": app_id  # might be None if not from contact hint
#                     }
#                 else:
#                     return {"status_code": response.status_code, "error": response.text}

#         except Exception as e:
#             self.logger.error(f"OTP Generation Error: {str(e)}")
#             return {"error": str(e)}

#     def validate_otp(self, app_id: str, phone_number: str, otp: str):
#         url = f"{self.base_url}/herofin-service/otp/validate_new/"
#         headers = {
#             "Content-Type": "application/json",
#             "Accept": "application/json"
#         }
#         payload = {
#             "phone_number": phone_number,
#             "app_id": app_id,
#             "otp": otp
#         }

#         try:
#             with httpx.Client(auth=self.auth, headers=headers, follow_redirects=True) as client:
#                 response = client.post(url, json=payload)
#                 self.logger.info(f"POST OTP Validate - {response.status_code}: {response.text}")

#                 if response.status_code in [200, 201]:
#                     data = response.json()
#                     return {
#                         "status": "OTP Validated",
#                         "access_token": data.get("access_token"),
#                         "app_id": data['loan_id'],
#                         "phone_number": phone_number
#                     }
#                 else:
#                     return {"status_code": response.status_code, "error": response.text}
#         except Exception as e:
#             self.logger.error(f"OTP Validation Error: {str(e)}")
#             return {"error": str(e)}





# 2

# import httpx
# from Loggers.StdOutLogger import StdoutLogger

# # Session store for mapping session_id to user details
# session_store = {}

# class HeroFincorpAuthAPIs:
#     def __init__(self):
#         self.base_url = "https://herokuapi-dev.herofincorp.com"
#         self.auth = httpx.BasicAuth("mobile-client", "5PhxdQ4r9PY7gh")
#         self.logger = StdoutLogger()

#     def generate_otp(self, user_input: str, session_id: str):
#         headers = {
#             "Content-Type": "application/json",
#             "Accept": "application/json"
#         }

#         try:
#             with httpx.Client(auth=self.auth, headers=headers, follow_redirects=True) as client:
#                 if len(user_input) == 10 and user_input.isdigit():
#                     payload = {"phone_number": user_input}
#                     response = client.post(f"{self.base_url}/herofin-service/otp/generate_new/", json=payload)
#                     phone_number = user_input
#                     app_id = None

#                 elif 5 <= len(user_input) <= 8 and user_input.isdigit():
#                     contact_hint_resp = client.get(f"{self.base_url}/herofin-service/get-contact-hint/{user_input}/")
#                     if contact_hint_resp.status_code != 200:
#                         return {"status_code": contact_hint_resp.status_code, "error": contact_hint_resp.text}

#                     contact_hint_data = contact_hint_resp.json()
#                     phone_number = contact_hint_data.get("phone_number")
#                     app_id = contact_hint_data.get("app_id")

#                     if not phone_number or not app_id:
#                         return {"error": "Invalid contact hint response"}

#                     payload = {"phone_number": phone_number, "app_id": app_id}
#                     response = client.post(f"{self.base_url}/herofin-service/otp/generate_new/", json=payload)
#                 else:
#                     return {"error": "Invalid input. Provide 10-digit phone number or 5–8 digit app_id."}

#                 self.logger.info(f"POST OTP - {response.status_code}: {response.text}")
#                 if response.status_code in [200, 201]:
#                     otp_resp = {
#                         "status": "OTP Sent",
#                         "phone_number": phone_number,
#                         "app_id": app_id
#                     }

#                     # Save session data
#                     session_store[session_id] = {
#                         "phone_number": phone_number,
#                         "app_id": app_id
#                     }

#                     return otp_resp
#                 else:
#                     return {"status_code": response.status_code, "error": response.text}

#         except Exception as e:
#             self.logger.error(f"OTP Generation Error: {str(e)}")
#             return {"error": str(e)}

#     def validate_otp(self, otp: str, session_id: str):
#         # Fetch stored session data
#         session_data = session_store.get(session_id)
#         if not session_data:
#             return {"error": "Session not found or expired"}

#         phone_number = session_data.get("phone_number")
#         app_id = session_data.get("app_id")

#         url = f"{self.base_url}/herofin-service/otp/validate_new/"
#         headers = {
#             "Content-Type": "application/json",
#             "Accept": "application/json"
#         }
#         payload = {
#             "phone_number": phone_number,
#             "app_id": app_id,
#             "otp": otp
#         }

#         try:
#             with httpx.Client(auth=self.auth, headers=headers, follow_redirects=True) as client:
#                 response = client.post(url, json=payload)
#                 self.logger.info(f"POST OTP Validate - {response.status_code}: {response.text}")

#                 if response.status_code in [200, 201]:
#                     data = response.json()
#                     validate_otp_response = {
#                         "status": "OTP Validated",
#                         "access_token": data.get("access_token"),
#                         "app_id": data['loan_id'],
#                         "phone_number": phone_number
#                     }

#                     # Update session store with access token and updated app_id
#                     session_store[session_id]["access_token"] = validate_otp_response["access_token"]
#                     session_store[session_id]["app_id"] = validate_otp_response["app_id"]

#                     return validate_otp_response
#                 else:
#                     return {"status_code": response.status_code, "error": response.text}

#         except Exception as e:
#             self.logger.error(f"OTP Validation Error: {str(e)}")
#             return {"error": str(e)}
        

# def get_sessions():
#     return session_store







# 3


import httpx
from Loggers.StdOutLogger import StdoutLogger
from session_store import SessionStore

session_store = SessionStore()

class HeroFincorpAuthAPIs:
    def __init__(self, session_id):
        self.base_url = "https://herokuapi-dev.herofincorp.com"
        self.auth = httpx.BasicAuth("mobile-client", "5PhxdQ4r9PY7gh")
        self.logger = StdoutLogger()
        self.session_store = session_store
        self.session_id = session_id


    def generate_otp(self, user_input: str):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        try:
            with httpx.Client(auth=self.auth, headers=headers, follow_redirects=True) as client:
                if len(user_input) == 10 and user_input.isdigit():
                    payload = {"phone_number": user_input}
                    response = client.post(f"{self.base_url}/herofin-service/otp/generate_new/", json=payload)
                    phone_number = user_input
                    app_id = None

                elif 5 <= len(user_input) <= 8 and user_input.isdigit():
                    contact_hint_resp = client.get(f"{self.base_url}/herofin-service/get-contact-hint/{user_input}/")
                    if contact_hint_resp.status_code != 200:
                        return {"status_code": contact_hint_resp.status_code, "error": contact_hint_resp.text}

                    contact_hint_data = contact_hint_resp.json()
                    phone_number = contact_hint_data.get("phone_number")
                    app_id = contact_hint_data.get("app_id")

                    if not phone_number or not app_id:
                        return {"error": "Invalid contact hint response"}

                    payload = {"phone_number": phone_number, "app_id": app_id}
                    response = client.post(f"{self.base_url}/herofin-service/otp/generate_new/", json=payload)
                else:
                    return {"error": "Invalid input. Provide 10-digit phone number or 5–8 digit app_id."}

                self.logger.info(f"POST OTP - {response.status_code}: {response.text}")
                if response.status_code in [200, 201]:
                    otp_resp = {
                        "status": "OTP Sent",
                        "phone_number": phone_number,
                        "app_id": app_id
                    }

                    # Save session data
                    self.session_store.set(self.session_id, {
                        "phone_number": phone_number,
                        "app_id": app_id
                    })

                    return otp_resp
                else:
                    return {"status_code": response.status_code, "error": response.text}

        except Exception as e:
            self.logger.error(f"OTP Generation Error: {str(e)}")
            return {"error": str(e)}

    def validate_otp(self, otp: str):
        session_data = self.session_store.get(self.session_id)
        if not session_data:
            return {"error": "Session not found or expired"}

        phone_number = session_data.get("phone_number")
        app_id = session_data.get("app_id")

        url = f"{self.base_url}/herofin-service/otp/validate_new/"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        payload = {
            "phone_number": phone_number,
            "app_id": app_id,
            "otp": otp
        }

        try:
            with httpx.Client(auth=self.auth, headers=headers, follow_redirects=True) as client:
                response = client.post(url, json=payload)
                self.logger.info(f"POST OTP Validate - {response.status_code}: {response.text}")

                if response.status_code in [200, 201]:
                    data = response.json()
                    validate_otp_response = {
                        "status": "OTP Validated",
                        "access_token": data.get("access_token"),
                        "app_id": data['loan_id'],
                        "phone_number": phone_number
                    }

                    # Update session store
                    self.session_store.update(self.session_id, {
                        "access_token": validate_otp_response["access_token"],
                        "app_id": validate_otp_response["app_id"]
                    })

                    return validate_otp_response
                else:
                    return {"status_code": response.status_code, "error": response.text}

        except Exception as e:
            self.logger.error(f"OTP Validation Error: {str(e)}")
            return {"error": str(e)}
        
    def is_logged_in(self):
        """
        Checks if the user is logged in by verifying if a valid access token exists in the session store.

        Returns:
            bool: True if logged in, False otherwise.
        """
        session_data = self.session_store.get(self.session_id)
        access_token = session_data.get("access_token") if session_data else None
        return bool(access_token)

    def get_sessions(self):
        return self.session_store