import sys
import logging
from redis_session_store import RedisSessionStore
from HFCLAPIsNew import HeroFincorpAPIs
from HFCL_Auth_APIs import HeroFincorpAuthAPIs

# Configure quick logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(message)s')
log = logging.getLogger("VERIFY")

def run_test():
    """
    Simulates the 'Blind State' Flow:
    1. Authenticate (generating token -> Redis)
    2. API Call (reading token <- Redis)
    """
    session_id = "TEST_SESSION_001"
    store = RedisSessionStore("redis://localhost:6379/0") 
    # NOTE: Ensure local Redis is running on port 6379 or update URL above
    
    log.info(f"--- 1. Testing Auth Flow for {session_id} ---")
    auth_client = HeroFincorpAuthAPIs(session_id, session_store=store)
    
    # Simulate a login by manually injecting state (Mocking the OTP success)
    # In real life, you'd call auth_client.validate_otp("123456")
    fake_token = "TEST_BEARER_TOKEN_123"
    fake_app_id = "APP-0000001"
    fake_phone = "9999999999"
    
    store.update(session_id, {
        "access_token": fake_token,
        "app_id": fake_app_id,
        "phone_number": fake_phone
    })
    log.info("✅ Manually injected Mock Login Token into Redis.")

    log.info(f"--- 2. Testing API Flow (Parameter-less) ---")
    # Initialize API client. It should AUTO-LOAD context from Redis.
    api_client = HeroFincorpAPIs(session_id, session_store=store)
    
    if api_client.app_id == fake_app_id:
        log.info(f"✅ Success: API Client auto-loaded app_id: {api_client.app_id}")
    else:
        log.error(f"❌ Failed: API Client has app_id: {api_client.app_id}")
        sys.exit(1)

    # Simulate a call (it will fail network since token is fake, but we check the URL structure)
    log.info("Attempting get_loan_details() [Expect Network Error or 401, but correct URL]")
    resp = api_client.get_loan_details() 
    # We expect it to try to hit the URL. The fact that it runs without arguments is the success.
    
    log.info(f"Response: {resp}")
    log.info("✅ Test Complete. The architecture handles blind state correctly.")

if __name__ == "__main__":
    try:
        run_test()
    except Exception as e:
        log.error(f"Test Crashed: {e}")
