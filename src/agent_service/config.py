import os

# Server Settings
SERVER_NAME = "hero_fincorp"
SERVER_URL = os.getenv("MCP_SERVER_URL", "http://0.0.0.0:8050/sse")
PORT = int(os.getenv("PORT", "8000"))

# Logic Settings
KEEP_LAST = int(os.getenv("KEEP_LAST_MESSAGES", "20"))
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# External Services
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# SECURITY: Never default to real keys in code
GROQ_API_KEY = os.getenv("GROQ_API_KEY") 
if not GROQ_API_KEY:
    # Optional: Raise error in production
    # raise ValueError("GROQ_API_KEY is not set")
    print("WARNING: GROQ_API_KEY is not set. LLM calls will fail.")

GROQ_BASE_URL = "https://api.groq.com"
MODEL_NAME = os.getenv("MODEL", "openai/gpt-oss-120b")
