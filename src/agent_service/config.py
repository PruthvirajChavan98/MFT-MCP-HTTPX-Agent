import os
import itertools

# Server Settings
SERVER_NAME = "hero_fincorp"
SERVER_URL = os.getenv("MCP_SERVER_URL", "http://0.0.0.0:8050/sse")
PORT = int(os.getenv("PORT", "8000"))

# Logic Settings
KEEP_LAST = int(os.getenv("KEEP_LAST_MESSAGES", "20"))
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# External Services
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# --- GROQ LOAD BALANCING CONFIGURATION ---
GROQ_BASE_URL = "https://api.groq.com"

# 1. Get raw string from env (support both plural and singular env vars)
_GROQ_ENV_VAL = os.getenv("GROQ_API_KEYS", os.getenv("GROQ_API_KEY", ""))

# 2. Parse into a list
GROQ_API_KEYS = [k.strip() for k in _GROQ_ENV_VAL.split(",") if k.strip()]

# 3. Create a thread-safe infinite iterator (Round Robin)
#    This will yield key1, key2, key3, key1, key2... forever.
GROQ_KEY_CYCLE = itertools.cycle(GROQ_API_KEYS) if GROQ_API_KEYS else None

if not GROQ_API_KEYS:
    print("WARNING: No GROQ_API_KEYS found. Groq models will fail.")
else:
    print(f"INFO: Loaded {len(GROQ_API_KEYS)} Groq API keys for internal load balancing.")

# --- OPENROUTER CONFIGURATION ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
if not OPENROUTER_API_KEY:
    print("WARNING: OPENROUTER_API_KEY is not set (OpenRouter models will be unavailable).")

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

if not NVIDIA_API_KEY:
    print("WARNING: NVIDIA_API_KEY is not set.")



# Default Model
MODEL_NAME = os.getenv("MODEL", "openai/gpt-oss-120b")