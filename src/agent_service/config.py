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

# Provider 1: Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = "https://api.groq.com"

# Provider 2: OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Default Model
MODEL_NAME = os.getenv("MODEL", "openai/gpt-oss-120b")

if not GROQ_API_KEY:
    print("WARNING: GROQ_API_KEY is not set.")
if not OPENROUTER_API_KEY:
    print("WARNING: OPENROUTER_API_KEY is not set (OpenRouter models will be unavailable).")
