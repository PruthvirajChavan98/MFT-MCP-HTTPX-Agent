from datetime import datetime
import os
import json
import requests
from fastapi import HTTPException
from requests.auth import HTTPBasicAuth

from Loggers.StdOutLogger import StdoutLogger

authentication_error = HTTPException(
    status_code=401,
    detail="User is not authenticated, please login and try again"
)
bearer_token_missing = {
    "error": authentication_error.status_code,
    "detail": authentication_error.detail
}


logger = StdoutLogger()

# cred = os.getenv("secrets")

# cred_dict = json.loads(cred)

class HeroFincorpAPIs:
    def __init__(self, bearer_token=None, app_id=None):
        self.bearer_token = bearer_token
        self.app_id = app_id
        self.base_url = "https://herokuapi-dev.herofincorp.com"
    
    def get_dashboard_data(self):
        """Retrieves the name of the user."""
        try:

            if not self.bearer_token:
                return bearer_token_missing

            headers = self._create_headers()
            response = requests.get(
                f"{self.base_url}/herofin-service/home/", headers=headers
            )
            if response.status_code == 200:
                logger.info("Successfully retrieved dashboard data")
            else:
                logger.error(f"Failed to retrieve dashboard data\n status code: {response.status_code}, details: {response.text}")
            return self._handle_response(response)
        except Exception as e:
            print(f"An error occurred: {e}")
            return None 
    
    
    def check_user_logged_in(self):
        """Check if user is not logged in"""
        if not self.bearer_token:
            return bearer_token_missing

    
    def login_helper_tool(self):
        """This function is called only when user wants to login"""
        if not self.bearer_token:
            return {"message": "login screen will be displayed"}
        return {"message": f"you are already logged-in with app_id {self.app_id}"}

    
    def get_loan_details(self):
        """Retrieves loan details."""
        try:

            if not self.bearer_token:
                return bearer_token_missing

            headers = self._create_headers()
            response = requests.get(
                f'{self.base_url}/herofin-service/loan/details/{self.app_id}/',
                headers=headers
            )
            
            if response.status_code == 200:
                logger.info("Successfully retrieved loan details")
                response_data = response.json()
                return response_data
            else:
                logger.error(f"Failed to retrieve loan details\n status code: {response.status_code}, details: {response.text}")
                return response.json()
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            return None 

    
    def show_profiles(self):
        """Retrieve and display user profiles from the HeroFincorp API."""
        try:

            if not self.bearer_token:
                return bearer_token_missing

            headers = self._create_headers()
            response = requests.get(
                f"{self.base_url}/herofin-service/profiles/", headers=headers
            )
            if response.status_code == 200:
                logger.info("Successfully retrieved profiles data")
            else:
                logger.error(f"Failed to retrieve profile data\n status code: {response.status_code}, details: {response.text}")
            return self._handle_response(response)
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            return None 

    
    def make_foreclosure_case_request(self):
        """POST request for 'Foreclosure of Loan' case."""
        try:

            if not self.bearer_token:
                return bearer_token_missing

            data = {
                "app_id": self.app_id,
                "query_description": "Foreclosure of Loan",
                "description": ("plz close the loan account and process noc "
                                "in customer address only"),
            }
            headers = self._create_headers()
            response = requests.post(
                f"{self.base_url}/case/download/sc-request/",
                json=data, headers=headers
            )
            if response.status_code == 201:
                logger.info("Successfully created foreclosure case")
            logger.error(f"Failed to create foreclosure case\n status code: {response.status_code}, details: {response.text}")
            return self._handle_response_foreclosure(response)
        except Exception as e:
            logger.error(f"An error occurred in making forecloser case: {e}")
            return None 

    
    def make_maturity_closure_case_request(self):
        """POST request for 'Maturity Closure' case."""
        try:

            if not self.bearer_token:
                return bearer_token_missing

            data = {
                "app_id": self.app_id,
                "query_description": "Maturity Closure",
                "description": "Close the loan account",
            }
            headers = self._create_headers()
            response = requests.post(
                f"{self.base_url}/case/download/sc-request/",
                json=data, headers=headers
            )
            if response.status_code == 201:
                logger.info("Successfully created maturity closure case")
            logger.error(f"Failed to create maturity closure case\n status code: {response.status_code}, details: {response.text}")
            return self._handle_response(response)
        except Exception as e:
            logger.error(f"An error occurred in making maturity closure case: {e}")
            return None 

    
    def make_noc_request(self):
        """POST request for NOC (No Objection Certificate)."""
        try:

            if not self.bearer_token:
                return bearer_token_missing

            data = {
                "app_id": self.app_id,
                "query_description": "NOC Request",
                "description": "Need NOC for the loan account",
            }
            headers = self._create_headers()
            response = requests.post(
                f"{self.base_url}/case/download/sc-request/",
                json=data, headers=headers
            )
            if response.status_code == 201:
                logger.info("Successfully created NOC request")
            logger.error(f"Failed to create NOC request\n status code: {response.status_code}, details: {response.text}")
            return self._handle_response(response)
        except Exception as e:
            logger.error(f"An error occurred in making NOC request: {e}")
            return None 
    
    
    def download_noc_letter(self):
        """GET request for NOC letter."""
        try:

            if not self.bearer_token:
                return bearer_token_missing
            
            data = {
                "loan_id": self.app_id
            }

            headers = self._create_headers()
            response = requests.post(
                f"{self.base_url}/herofin-service/download/noc-letter/",
                json=data, headers=headers
            )
            if response.status_code == 200:
                logger.info("Successfully downloaded NOC letter")
            logger.error(f"Failed to download NOC letter\n status code: {response.status_code}, details: {response.text}")
            return self._handle_response(response)
        except Exception as e:
            logger.error(f"An error occurred in downloading NOC letter: {e}")
            return None 

    
    def get_overdue_details(self):
        """GET request for overdue details."""
        try:
            logger.info(f"app_id in overdue details >>>>>>>>>> {self.app_id}")
            if not self.bearer_token:
                return bearer_token_missing

            headers = self._create_headers()
            response = requests.get(
                f"{self.base_url}/herofin-service/loan_overdues/{self.app_id}/",
                headers=headers
            )
            if response.status_code == 200:
                logger.info("Successfully retrieved overdue details")
                overdue_details = response.json()
                overdue_details["loan"].pop("user_name", None)
                overdue_details["loan"].pop("phone_number", None)
                overdue_details["loan"].pop("app_id", None)
                return overdue_details
            else:
                logger.error(f"Failed to retrieve overdue details\n status code: {response.status_code}, details: {response.text}")
                return {
                    response.status_code: response.text
                    }
        except Exception as e:
            logger.error(f"An error occurred in calling overdue details api: {e}")
            return None 

    
    def get_repayment_schedule(self):
        """GET request for repayment schedule."""
        try:

            if not self.bearer_token:
                return bearer_token_missing

            headers = self._create_headers()
            response = requests.get(
                f"{self.base_url}/herofin-service/download/repayment-schedule",
                headers=headers
            )
            if response.status_code == 200:
                logger.info("Successfully retrieved repayment schedule")
            logger.error(f"Failed to retrieve repayment schedule\n status code: {response.status_code}, details: {response.text}")
            return response.json()
        except Exception as e:
            logger.error(f"An error occurred in sending repayment schedule request: {e}")
            return None 
    
    
    def get_foreclosure_details(self):
        """GET request for foreclosure details."""
        try:

            if not self.bearer_token:
                return bearer_token_missing

            headers = self._create_headers()
            response = requests.get(
                f"{self.base_url}/herofin-service/loan/foreclosuredetails/{self.app_id}/",
                headers=headers
            )
            if response.status_code == 200:
                logger.info("Successfully retrieved foreclosure details")
            logger.error(f"Failed to retrieve foreclosure details\n status code: {response.status_code}, details: {response.text}")
            return self._handle_response(response)
        except Exception as e:
            logger.error(f"An error occurred in calling foreclosure details api: {e}")
            return None 

    
    def get_loan_offers(self):
        """GET request for loan offers."""
        try:

            if not self.bearer_token:
                return bearer_token_missing

            headers = self._create_headers()
            response = requests.get(
                f"{self.base_url}/cross-sell/loan-info",
                headers=headers
            )
            if response.status_code == 200:
                logger.info("Successfully retrieved loan offers")
            logger.error(f"Failed to retrieve loan offers\n status code: {response.status_code}, details: {response.text}")
            return self._handle_response(response)
        except Exception as e:
            logger.error(f"An error occurred in calling loan offers api: {e}")
            return None 
    
    
    def download_soa(self):
        """
        Makes a POST request to download Statement of Account SOA
        """
        try:

            if not self.bearer_token:
                return bearer_token_missing
            
            loan_details = self.get_loan_details()
            dashboard_data = self.get_dashboard_data()
            if 'loan' not in loan_details:
                print("Loan details not found")
                return {"error": "Failed to make request, Loan details not found"}
            
            loan_disbursed_date = loan_details['loan']['loan_details']['loan_disbursed_on']
            last_emi_date = loan_details['loan']['loan_details']['last_emi_date']

            formatted_emi_start_date = datetime.strptime(loan_disbursed_date, "%d/%m/%Y").strftime("%Y-%m-%d")
            formatted_emi_end_date = datetime.strptime(last_emi_date, "%d/%m/%Y").strftime("%Y-%m-%d")
            
            data = {
                "start_date": formatted_emi_start_date,
                "end_date": formatted_emi_end_date
                }
            headers = self._create_headers()

            response = requests.post(
                f"{self.base_url}/herofin-service/download/soa/",
                json=data, headers=headers
            )

            if response.status_code == 200:
                logger.info("Successfully downloaded SOA")
            else:
                logger.info(f"Download SOA\n status code: {response.status_code}, details: {response.text}")
            response_data = response.json()
            response_data["Additional instructions for assistant"] = "do not generate possible follow-up questions for this tool"

            if dashboard_data["offer_flag"] == "Eligible":
                response_data["loan offers available"] = "Yes"
                response_data["loan_offer_upto_amount"] = self.get_loan_offers()["loan_offer_upto_amount"]

            return response_data
        except Exception as e:
            logger.error(f"An error occurred in calling soa api: {e}")
            return None 

    
    def get_welcome_letter(self):
        """GET request for welcome letter."""
        try:
            if not self.bearer_token:
                return bearer_token_missing

            headers = self._create_headers()
            response = requests.get(
                f"{self.base_url}/herofin-service/download/welcome-letter/",
                headers=headers
            )
            if response.status_code == 200:
                logger.info("Successfully retrieved welcome letter")
            logger.error(f"Failed to retrieve welcome letter\n status code: {response.status_code}, details: {response.text}")
            return self._handle_response(response)
        except Exception as e:
            logger.error(f"An error occurred in calling welcome letter api: {e}")
            return None 
    
    
    def get_closure_letter(self):
        """GET request for closure letter"""
        try:

            if not self.bearer_token:
                return bearer_token_missing
            
            loan_details = self.get_loan_details()
            
            if loan_details and 'loan' in loan_details and 'loan_details' in loan_details['loan']:
                loan_details = loan_details['loan']['loan_details']
                loan_status = loan_details.get('loan_status', '').lower()
                if loan_status == "active" or loan_status == "a":
                    return {"message": "Loan is still active, user cannot get closure letter"}
            
            headers = self._create_headers()
            response = requests.get(
                f"{self.base_url}/herofin-service/download/closure-letter/", 
                headers=headers
                )
            if response.status_code == 200 or 400:
                logger.info("Successfully retrieved closure letter")
                return response.json()
            else:
                logger.error(f"Failed to retrieve closure letter\n status code: {response.status_code}, details: {response.text}")
                return {
                    "status_code": response.status_code,
                    "error": response.text
                }
        except Exception as e:
            logger.error(f"An error occurred in calling closure letter api: {e}")
            return None 

    
    def check_noc_status(self):
        """Check the NOC status of the loan."""
        try:

            if not self.bearer_token:
                return bearer_token_missing

            loan_details_response = self.get_loan_details()
            if loan_details_response and 'loan' in loan_details_response and 'loan_details' in loan_details_response['loan']:
                loan_details = loan_details_response['loan']['loan_details']
                loan_status = loan_details.get('loan_status', '').lower()
                product_code = loan_details.get('product_code', '')

                if loan_status and loan_status == 'closed' or loan_status == "c":
                    if product_code in ['TW', 'TWL', 'UTWL', 'ETWL', 'UC', 'RUC', 'RUCF', 'UCL', 'RUCL']:
                        profiles_response = self.show_profiles()
                        if profiles_response and 'bike_details' in profiles_response:
                            bike_details = profiles_response['bike_details']
                            return {
                                "Additional instructions for assistant": (
                                "Make sure to ask the user to verify these vehicle details, "
                                "are these up-to-date or whether they want to update these or not. "
                                "If the user wants to update these details, use the 'update_pdd_details' tool. "
                                "If the user does not want to update these details, use the 'DownloadNOCLetter' "
                                "to create a Download NOC letter case. You must not use the 'CheckNocStatus' tool again."
                            ),
                            "bike_details": bike_details,
                            "Additional instructions for assistant: generate exactly these possible follow-up questions in DICT Format": [
                                "These details are up-to-date and correct, I do not want to update these.",
                                "These details are incorrect or not up-to-date, I want to update these.",
                                "I am looking for something else."
                            ]
                        }
                        else:
                            logger.error(f"{self.app_id} is elligible for NOC, but Vehicle details not found")
                            return {
                                'noc_status': 'Eligible but Vehicle Details Missing',
                                'message': (
                                    'NOC is eligible for issuance, but vehicle details are missing. '
                                    'Please contact customer support.'
                                )
                            }

                    else:
                        logger.error(f"Sending closure letter to {self.app_id}")
                        return {
                            "closure letter response": self.get_closure_letter()
                            }

                elif loan_status == 'active' or loan_status == 'a':
                    logger.error(f"NOC cannot be issued for {self.app_id} as the loan is still active.")
                    return {
                        'noc_status': 'Not Eligible',
                        'message': 'NOC cannot be issued as the loan is still active.'
                    }

                else:
                    logger.error("Loan status is unknown or not applicable for NOC.")
                    return {
                        'noc_status': 'Unknown',
                        'message': 'Loan status is unknown or not applicable for NOC.'
                    }

            else:
                logger.error("Loan details not found")
                return 'Loan details not available or failed to retrieve loan details.'
        except Exception as e:
            print(f"An error occurred: {e}")
            return None 
    
    
    def update_pdd_details(self):
        "Function trigger for updating pdd details"
        try:

            if not self.bearer_token:
                return bearer_token_missing
            logger.info("update_pdd_details was hit")
            return {"trigger": "update_pdd_details was hit"}
        except Exception as e:
            logger.error(f"An error occurred in update_pdd_details: {e}")
            return None 
        
    
    def check_foreclosure(self): 
        """
        Checks foreclosure status of the Loan.
        """
        try:
            if not self.bearer_token:
                return bearer_token_missing

            loan_details = self.get_loan_details()
            if loan_details and 'loan' in  loan_details and 'loan_details' in loan_details['loan']:
                loan = loan_details['loan']['loan_details']
                print("loan>>>>>>",loan)
                summary = loan_details['loan']['loan_summary']
                first_emi_date_hfcl = loan['first_emi_date']
                print("FEMI HFCL>>>",first_emi_date_hfcl)
                logger.info(f"FEMI - {first_emi_date_hfcl}")
                first_emi_date = datetime.strptime(loan['first_emi_date'], "%d/%m/%Y").date()
                print("FEMI",first_emi_date)
                loan_maturity_date = datetime.strptime(loan['loan_maturity_date'], "%d/%m/%Y").date()                
                current_date = datetime.now().date()           
                day_of_month = current_date.day               
                overdue_amount = summary['overdue_amount']               
                app_id = summary['app_id']
                loan_status = loan['loan_status'].lower()

                ##############
                if current_date > first_emi_date:
                    if loan_status == 'active' or loan_status == 'a':
                        if current_date > loan_maturity_date:                            
                            if overdue_amount == '0.00':
                                logger.info("Loan is matured, cannot foreclose, but can request NOC/Closure letter")
                                return {"response":f"Your Loan is matured, you cannot foreclose your amount. Once your loan is closed , you may request for NOC/Closure letter"}
                            else:
                                logger.info(f"Loan is matured, cannot foreclose becasuse overdue amount {overdue_amount}")
                                return {
                                    "response":f"Your Loan is matured, you cannot foreclose your amount ,you have pending overdue amount of Rs.{overdue_amount}.Here is the link to pay the overdue amount   **** https://www.herofincorp.com/pay-online ****. Once your loan is closed , you may request for NOC/Closure letter",
                                    "Additional instructions for assistant: generate exactly this possible follow-up questions in DICT Format": ["Give me my loan overdue details"]
                            }

                        # Check if the current date is between 6 and 8
                        if 6 <= day_of_month <= 8:
                            logger.info("Presentation for the current month is in process, we request you to raise a new query for forclosure of your loan post 8th of the month")
                            return "Your EMi Presentation for the current month is in process, we request you to raise a new query for forclosure of your loan post 8th of the month"
                        elif not 6 <= day_of_month <= 8:
                            if 'product_code' not in loan:
                                logger.error("Product code not found in loan details")
                                return {
                                    "Addtiontional instructions for assistant": "Make sure to ask the user to either download foreclosure statement or pay foreclosure amount,if user wants to download foreclosure statement, use the 'downloadforeclosurestatement' tool,  if the user wants to pay foreclosure amount use the 'payforeclosureamount' tool, for possible follow up questions in case of foreclosure,return only what the output is, do not generate any extra follow up questions, strictly return the response do not paraphrase it",
                                    "foreclosure_response":"You can foreclose your loan anytime during your loan tenure,subject to the terms and conditions of your loan agreement. Would you like to download foreclosure statement or pay foreclosure amount?",
                                    "Additional instructions for assistant: generate exactly these possible follow-up questions in DICT Format": ["Download foreclosure statement,","Pay foreclosure amount","I need something else"]
                                    }      
                                # return "Could not get details at the moment,please try again later"
                            product_code = loan['product_code']
                            logger.info(f"Product code is {product_code}")
                
                            if product_code in ['UC', 'RUC', 'UCL', 'RUCL']:
                                return {
                                    "Addtiontional instructions for assistant": "Make sure to ask the user to download foreclosure statement ,if user wants to download foreclosure statement, use the 'downloadforeclosurestatement' tool,for possible follow up questions in case of foreclosure,return only what the output is, do not generate any extra follow up questions, strictly return the response do not paraphrase it",
                                    "foreclosure_response":"You can foreclose your loan anytime during your loan tenure,subject to the terms and conditions of your loan agreement. Would you like to download foreclosure statement",
                                    "Additional instructions for assistant: generate exactly these possible follow-up questions in DICT Format" :["Download foreclosure statement"]
                                    }
                            else:
                                return {
                                    "Addtiontional instructions for assistant": "Make sure to ask the user to either download foreclosure statement or pay foreclosure amount,if user wants to download foreclosure statement, use the 'downloadforeclosurestatement' tool,  if the user wants to pay foreclosure amount use the 'payforeclosureamount' tool, for possible follow up questions in case of foreclosure,return only what the output is, do not generate any extra follow up questions, strictly return the response do not paraphrase it",
                                    "foreclosure_response":"You can foreclose your loan anytime during your loan tenure,subject to the terms and conditions of your loan agreement. Would you like to download foreclosure statement or pay foreclosure amount?",
                                    "Additional instructions for assistant: generate exactly these possible follow-up questions in DICT Format" :["Download foreclosure statement,","Pay foreclosure amount","I need something else"]
                                    }
                                                        
                    if loan_status == 'closed' or loan_status == 'c':
                        logger.info(f"Loan is closed for {app_id}")
                        return {
                            "foreclosure_response": f"Your loan of Application ID {app_id} is closed, there is no amount pending, you can request for NOC/Closure letter if not done already",
                            "Additional instructions for assistant: generate exactly these possible follow-up questions in DICT Format": [
                                "I want NOC for my loan",
                                "I want closure letter for my loan",
                                "I need something else"
                                ]
                                }

                else:
                    logger.info("Presentation for the current month is in process, we request you to download foreclosure statement post 8th of the month")
                    return "Your EMI presenation for the current month is in process, we request you to download the foreclosure statement post 8th of the month"

            else:
                logger.error("Loan details not found")
                return "Something went wrong, could not get details at the moment, try after sometime"
        except Exception as e:
            logger.error(f"An error occurred in check_foreclosure: {e}")
            return None
   
    def format_foreclosure_details(self, foreclosure_details):
        """Function to format foreclosure details"""
        formatted_output = "Foreclosure_details:\n"
        for key, value in foreclosure_details.items():
            formatted_output += f"    {key}: {value},\n"
        return formatted_output
    
    
    def download_foreclosure_statement(self):
        """This function retrieves the statement of foreclosure after checking foreclosure function. it will only trigger when user says to download foreclosure statement"""

        try:
            if not self.bearer_token:
                return bearer_token_missing
            
            headers = self._create_headers()
            response = requests.get(
                f"{self.base_url}/herofin-service/download/foreclosure-statement/", headers=headers
            )
            if response.status_code == 208:
                logger.info(f"foreclosure response: {response.json()}")
                return {"response":"As per the records, To download the foreclosure statement " + str(response.json().get("message")) + " Please contact customer support for further details"
                        ,"possible follow-up questions":["What is the contact number for customer support?"],
                }
                
            elif response.status_code in [201, 202]:
                logger.info(f"foreclosure response: {response.json()}")
                return response.json().get("message")
            else:
                logger.error(f"Unexpected response: {response.text}")
                return "An unexpected response was received while downloading foreclosure statement."
        
        except Exception as e:
            logger.error(f"An error occurred in download_foreclosure_statement: {e}")
            return None 

     
    def pay_foreclosure_amount(self):
        """This function is called only after checking the foreclosure status, and when the user says to pay the foreclosure amount"""
        try:
            if not self.bearer_token:
                return bearer_token_missing

            loan_foreclosure_details = self.get_foreclosure_details()
            logger.info(f"loan_foreclosure_details: {loan_foreclosure_details}")
            if loan_foreclosure_details and "foreclosure_details" in loan_foreclosure_details:
                formatted_foreclosure_details = self.format_foreclosure_details(loan_foreclosure_details["foreclosure_details"])
                total_payable_amount = float(loan_foreclosure_details["foreclosure_details"]["total_payable_amount"])
                if total_payable_amount > 0.00:
                    logger.info(f"total_payable_amount: {total_payable_amount}")
                    return f"As per the records you have a Total payable amount of Rs {total_payable_amount}. Here is your breakup of foreclosure details: {formatted_foreclosure_details}, please pay the foreclosure amount first. Here is the link **** https://www.herofincorp.com/pay-online **** for paying the remaining amount."
                else:
                    foreclosure_request = self.make_foreclosure_case_request()
                    if foreclosure_request:
                        # message = foreclosure_request.get("message")
                        if foreclosure_request.get("status_code") == 208:
                            logger.info(f"foreclosure response: {foreclosure_request}")
                            return {"response":f"As per the records you do not have any amount left to pay,but The foreclosure {foreclosure_request['message']['message']} Please contact our customer support for further details",
                                    "possible follow-up questions":["How can i contact customer support"],
                            }
                        
                        elif foreclosure_request.get("status_code") == 201:
                            logger.info(f"foreclosure response: {foreclosure_request}")
                            return {"response":f"Since you do not have any payable amount left, {foreclosure_request['message']['message']} For further details,please contact cutomer support"
                                    ,"possible follow-up questions":["How can i contact customer support","Download Foreclosure Statement"]
                            }
                        
            else:
                logger.error("Failed to retrieve foreclosure details")
                return "An unexpected error occurred while retrieving foreclosure details."
            
        except Exception as e:
            logger.error(f"An error occurred in pay_foreclosure_amount: {e}")
            return None 
        
    def _create_headers(self):
        """Helper function to create request headers."""
        return {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
        }

    def _handle_response(self, response):
        """Helper function to process the response."""
        # if response.status_code == 200 or response.status_code == 208:
        if response.status_code == 200 or response.status_code == 208 or response.status_code == 201:

            return response.json()
        else:
            return {
                "status_code": response.status_code,
                "error": response.text
            }
        
    def _handle_response_foreclosure(self, response):
        """Helper function to process the response."""
        if response.status_code == 200 or response.status_code == 201 or response.status_code == 208:
            return {
                "status_code": response.status_code,
                "message": response.json()
            }
        else:
            return {
                "status_code": response.status_code,
                "error": response.text
            }