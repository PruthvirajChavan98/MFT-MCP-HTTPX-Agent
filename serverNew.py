from fastmcp import FastMCP
from fastapi import Request
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_request

from HFCL_Auth_APIs import HeroFincorpAuthAPIs
from HFCLAPIsNew import HeroFincorpAPIs
from image_store import ImageStore

mcp = FastMCP(name="HFCL MCP Server httpx tools")
image_store = ImageStore(db_path="/Users/pruthvi/Developer/HFCL-Langchain-MCP-Client-New/image_store.db")

def extract_custom_headers():
    """
    Extracts custom headers 'X-Bearer-Token' and 'X-App-ID' from an HTTP request.

    Parameters:
        request (Request): FastAPI request object

    Returns:
        dict: Dictionary containing bearer_token and app_id
    """

    request : Request = get_http_request()
    session_id = request.headers.get("X-Session-ID", "")

    return session_id


def get_auth_api_client() -> HeroFincorpAuthAPIs:
    """Initialize and return HeroFincorpAuthAPIs client using headers from request."""
    session_id = extract_custom_headers()
    return HeroFincorpAuthAPIs(session_id)


def get_api_client() -> HeroFincorpAPIs:
    """Initialize and return HeroFincorpAPIs client using headers from request."""
    session_id = extract_custom_headers()
    return HeroFincorpAPIs(session_id)


@mcp.tool
def generate_otp(user_input: str) -> dict:
    """
    Generate OTP using Hero Fincorp Auth APIs, Helps user to login
    - ONLY 1 of these needed:
        5-8 digit app id or 10 digit Mobile Number in arguments
    """
    try:
        auth_api = get_auth_api_client()
        return auth_api.generate_otp(user_input)
    except Exception as e:
        return {"error": f"Failed to generate OTP: {str(e)}"}

@mcp.tool
def validate_otp(otp: str) -> dict:
    """
    Verify OTP using Hero Fincorp Auth APIs, Helps user to login
    - TO BE CALLED AFTER 'generate_otp'
    """
    try:
        auth_api = get_auth_api_client()
        return auth_api.validate_otp(otp)
    except Exception as e:
        return {"error": f"Failed to verify OTP: {str(e)}"}
    

@mcp.tool
def get_dashboard_data() -> dict:
    """Get dashboard data from Hero Fincorp API"""
    try:
        api = get_api_client()
        return api.get_dashboard_data()
    except Exception as e:
        return {"error": f"Failed to get dashboard data: {str(e)}"}


@mcp.tool
def get_loan_details() -> dict:
    """Get loan details from Hero Fincorp API"""
    try:
        api = get_api_client()
        return api.get_loan_details()
    except Exception as e:
        return {"error": f"Failed to get loan details: {str(e)}"}


@mcp.tool
def get_overdue_details() -> dict:
    """Get overdue details from Hero Fincorp API"""
    try:
        api = get_api_client()
        return api.get_overdue_details()
    except Exception as e:
        return {"error": f"Failed to get overdue details: {str(e)}"}


@mcp.tool
def get_repayment_schedule() -> dict:
    """Get repayment schedule from Hero Fincorp API"""
    try:
        api = get_api_client()
        return api.get_repayment_schedule()
    except Exception as e:
        return {"error": f"Failed to get repayment schedule: {str(e)}"}


@mcp.tool
def get_foreclosure_details() -> dict:
    """Get foreclosure details from Hero Fincorp API"""
    try:
        api = get_api_client()
        return api.get_foreclosure_details()
    except Exception as e:
        return {"error": f"Failed to get foreclosure details: {str(e)}"}
    

@mcp.tool
def download_noc_letter() -> dict:
    """Download NOC letter from Hero Fincorp API"""
    try:
        api = get_api_client()
        return api.download_noc_letter()
    except Exception as e:
        return {"error": f"Failed to download NOC letter: {str(e)}"}


@mcp.tool
def make_noc_request(chassis_number: str, engine_no: str, vehicle_number: str) -> dict:
    """
        makes Noc request for vehicle (NOC flow).
        ONLY called when user is Logged In - First Check that explicitly.

        Args:
            chassis_no (str): Chassis number of the bike
            engine_no (str): Engine number of the bike
            vehicle_number (str): Vehicle registration number

        Returns:
            dict: API response
        """
    try:
        api = get_api_client()

        if not api.bearer_token:
            return {"error": "Bearer token not found. Please login first."}
        
        image_base64 = image_store.get_image(image_ref=f"{api.app_id}_{api.session_id}")
        if not image_base64:
            return {"error": "Image not uploaded. Please upload the image first and provide a valid image_ref."}

        return api.make_noc_request(
            chassis_no=chassis_number,
            engine_no=engine_no,
            vehicle_number=vehicle_number,
            image_base64=image_base64
        )
    except Exception as e:
        return {"error": f"Failed to upload NOC documents: {str(e)}"}
    
@mcp.tool
def is_logged_in():
    """
    Checks if user is logged in
    """
    auth_api = get_auth_api_client()
    return auth_api.is_logged_in()

# Start the FastMCP server
if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8050)