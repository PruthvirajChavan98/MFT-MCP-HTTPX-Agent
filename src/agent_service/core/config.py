import os
import json
import itertools

# Server Settings
SERVER_NAME = "mock_fintech"
SERVER_URL = os.getenv("MCP_SERVER_URL", "http://0.0.0.0:8050/sse")
PORT = int(os.getenv("PORT", "8000"))

# Logic Settings
KEEP_LAST = int(os.getenv("KEEP_LAST_MESSAGES", "20"))
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# External Services
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# --- JUDGE CONFIGURATION ---
JUDGE_MODEL_NAME = os.getenv("JUDGE_MODEL_NAME", "openai/gpt-4o")
ENABLE_LLM_JUDGE = os.getenv("ENABLE_LLM_JUDGE", "true").lower() == "true"

# --- GROQ LOAD BALANCING CONFIGURATION ---
GROQ_BASE_URL = "https://api.groq.com"
_GROQ_ENV_VAL = os.getenv("GROQ_API_KEYS", os.getenv("GROQ_API_KEY", ""))
GROQ_API_KEYS = [k.strip() for k in _GROQ_ENV_VAL.split(",") if k.strip()]
GROQ_KEY_CYCLE = itertools.cycle(GROQ_API_KEYS) if GROQ_API_KEYS else None

if not GROQ_API_KEYS:
    print("WARNING: No GROQ_API_KEYS found. Groq models will fail.")
else:
    print(f"INFO: Loaded {len(GROQ_API_KEYS)} Groq API keys for internal load balancing.")

# --- OPENROUTER CONFIGURATION ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()

# Optional OpenRouter attribution headers
OPENROUTER_SITE_URL = (os.getenv("OPENROUTER_SITE_URL") or "").strip() or None
OPENROUTER_APP_TITLE = (os.getenv("OPENROUTER_APP_TITLE") or "").strip() or None

if not OPENROUTER_API_KEY:
    print("WARNING: OPENROUTER_API_KEY is not set (OpenRouter models will be unavailable).")

# Default embedding model used across router/KB/evals.
# NOTE: Your Neo4j vector index is currently created with dimensions=1536.
# openai/text-embedding-3-small is 1536-d. If you change this, update the index dimensions too.
OPENROUTER_EMBED_MODEL_DEFAULT = os.getenv("OPENROUTER_EMBED_MODEL_DEFAULT", "openai/text-embedding-3-small").strip()

# --- NVIDIA CONFIGURATION ---
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
if not NVIDIA_API_KEY:
    print("WARNING: NVIDIA_API_KEY is not set.")

# Default Model
MODEL_NAME = os.getenv("MODEL", "openai/gpt-oss-120b")

# --- NBFC ROUTER (GLM vs Embeddings) ---
NBFC_ROUTER_ENABLED = os.getenv("NBFC_ROUTER_ENABLED", "true").lower() in ("1", "true", "yes", "y")
NBFC_ROUTER_MODE = os.getenv("NBFC_ROUTER_MODE", "hybrid").strip().lower()  # embeddings|llm|hybrid|compare
NBFC_ROUTER_CHAT_MODEL = os.getenv("NBFC_ROUTER_CHAT_MODEL", "z-ai/glm-4.7").strip()
NBFC_ROUTER_EMBED_MODEL = os.getenv("NBFC_ROUTER_EMBED_MODEL", OPENROUTER_EMBED_MODEL_DEFAULT).strip()
NBFC_ROUTER_CACHE_DIR = os.getenv("NBFC_ROUTER_CACHE_DIR", ".cache_nbfc_router").strip()

# threshold knobs (tune once using your eval traces)
NBFC_ROUTER_SENTIMENT_THRESHOLD = float(os.getenv("NBFC_ROUTER_SENTIMENT_THRESHOLD", "0.26"))
NBFC_ROUTER_SENTIMENT_MARGIN = float(os.getenv("NBFC_ROUTER_SENTIMENT_MARGIN", "0.03"))
NBFC_ROUTER_REASON_UNKNOWN_GATE = float(os.getenv("NBFC_ROUTER_REASON_UNKNOWN_GATE", "0.30"))
NBFC_ROUTER_REASON_MARGIN = float(os.getenv("NBFC_ROUTER_REASON_MARGIN", "0.03"))
NBFC_ROUTER_FALLBACK_SENTIMENT_SCORE = float(os.getenv("NBFC_ROUTER_FALLBACK_SENTIMENT_SCORE", "0.33"))
NBFC_ROUTER_FALLBACK_REASON_SCORE = float(os.getenv("NBFC_ROUTER_FALLBACK_REASON_SCORE", "0.60"))

# --- PARAMETER SPECS ---
GROQ_PARAMETER_SPECS_PAYLOAD_DEFAULT = {
    "data": {
        "models": [
            {
                "name": "groq",
                "models": [
                    {"id": "openai/gpt-4o", "parameterSpecs": [{"name": "temperature", "options": None}]},
                    {"id": "allam-2-7b", "parameterSpecs": [{"name": "temperature", "options": None}, {"name": "max_tokens", "options": None}]},
                    {"id": "llama-3.3-70b-versatile", "parameterSpecs": [{"name": "temperature", "options": None}, {"name": "max_tokens", "options": None}]},
                    {"id": "openai/gpt-oss-120b", "parameterSpecs": [{"name": "temperature", "options": None}, {"name": "max_tokens", "options": None}, {"name": "reasoning_effort", "options": ["low", "medium", "high"]}]},
                ],
            }
        ]
    }
}

GROQ_PARAMETER_SPECS_PAYLOAD = GROQ_PARAMETER_SPECS_PAYLOAD_DEFAULT
_env_json = (os.getenv("GROQ_PARAMETER_SPECS_JSON") or "").strip()
if _env_json:
    try:
        GROQ_PARAMETER_SPECS_PAYLOAD = json.loads(_env_json)
    except Exception:
        pass