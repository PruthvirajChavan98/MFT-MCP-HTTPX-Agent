import sys
import logging
from redis_session_store import RedisSessionStore
from HFCL_Auth_APIs import HeroFincorpAuthAPIs
from HFCLAPIsNew import HeroFincorpAPIs

# --- CONFIGURATION (Match your real Dev/Prod Data) ---
# Use a fresh session ID to ensure no old data interferes
SESSION_ID = "LIVE_TEST_BLIND_002"
PHONE_NUMBER = "9412322182"  # Ensure this is a valid user in your system
OTP = "123456"             # Ensure this is the correct magic/mock OTP for your dev env

# Redis Config (Make sure this matches your docker-compose or local setup)
# If running outside docker but redis is exposed on 6380:
REDIS_URL = "redis://localhost:6380/0" 

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(message)s')
log = logging.getLogger("LIVE_TEST")

def run_live_test():
    print(f"\n{'='*60}")
    print(f"🚀 STARTING LIVE BLIND-STATE TEST against {REDIS_URL}")
    print(f"{'='*60}")

    # 1. Initialize Real Redis Store
    try:
        store = RedisSessionStore(REDIS_URL)
        # Clear previous test session to start fresh
        store.delete(SESSION_ID)
        log.info(f"Cleared session: {SESSION_ID}")
    except Exception as e:
        log.error(f"Failed to connect to Redis: {e}")
        return

    # 2. Initialize Auth Client
    auth_client = HeroFincorpAuthAPIs(SESSION_ID, session_store=store)

    # ------------------------------------------------------------------
    # STEP 1: Generate OTP (This seeds phone_number into Redis)
    # ------------------------------------------------------------------
    log.info(f"\n--- [Step 1] Requesting OTP for {PHONE_NUMBER} ---")
    gen_resp = auth_client.generate_otp(PHONE_NUMBER)
    print(f"Response: {gen_resp}")

    if "error" in gen_resp:
        log.error("❌ Generate OTP failed. Stopping.")
        return

    # Verify State: Redis should have Phone, but NO App ID yet (Blind State)
    state = store.get(SESSION_ID)
    log.info(f"Current Redis State: app_id={state.get('app_id')}, phone={state.get('phone_number')}")

    # ------------------------------------------------------------------
    # STEP 2: Validate OTP (The Critical Self-Healing Step)
    # ------------------------------------------------------------------
    log.info(f"\n--- [Step 2] Validating OTP {OTP} ---")
    val_resp = auth_client.validate_otp(OTP)
    print(f"Response: {val_resp}")

    if "error" in val_resp:
        log.error("❌ Validate OTP failed. Stopping.")
        return

    # ------------------------------------------------------------------
    # STEP 3: Verify "Self-Healing"
    # ------------------------------------------------------------------
    log.info(f"\n--- [Step 3] Verifying App ID Recovery ---")
    
    # Check 1: Did the function return the ID?
    returned_id = val_resp.get("loan_id")
    
    # Check 2: Is it saved in Redis?
    final_state = store.get(SESSION_ID)
    saved_id = final_state.get("app_id")
    token = final_state.get("access_token")

    if saved_id:
        print(f"✅ SUCCESS: App ID recovered and saved: {saved_id}")
    else:
        print(f"❌ FAILURE: Session is authenticated but 'app_id' is MISSING.")
        print(f"   Redis State: {final_state}")
        print("   This confirms the Self-Heal logic (Strategy A or B) failed on the real API.")
        return

    # ------------------------------------------------------------------
    # STEP 4: Prove API Access (Loan Details)
    # ------------------------------------------------------------------
    log.info(f"\n--- [Step 4] Fetching Loan Details (Proof of Life) ---")
    
    # Initialize API Client (Automatically loads the context we just saved)
    api_client = HeroFincorpAPIs(SESSION_ID, session_store=store)
    
    loan_resp = api_client.get_loan_details()
    print(f"Loan Details Response: {loan_resp}")

    if "error" not in loan_resp and loan_resp.get("status_code") != 404:
        print("\n🎉 TEST PASSED: Full flow from Phone -> Login -> Recovery -> Data Fetch worked.")
    else:
        print("\n⚠️ TEST PARTIAL: Login worked, ID recovered, but Loan Details endpoint failed.")

if __name__ == "__main__":
    run_live_test()