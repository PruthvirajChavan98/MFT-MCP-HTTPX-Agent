import os
import json

# --- SERVER SETTINGS ---
SERVER_NAME = "mock_fintech"
SERVER_URL = os.getenv("MCP_SERVER_URL", "http://0.0.0.0:8050/sse")
PORT = int(os.getenv("PORT", "8000"))
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# --- EXTERNAL SERVICES ---
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# --- LOGIC SETTINGS ---
# LangGraph history limit
KEEP_LAST = int(os.getenv("KEEP_LAST_MESSAGES", "20"))

# --- PROVIDER CONSTANTS (BASE URLS) ---
# These are architectural constants, not secrets.
GROQ_BASE_URL = "https://api.groq.com"
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# --- SERVER-SIDE KEYS (OPTIONAL FALLBACKS) ---
# In BYOK mode, these are typically None. 
# We define them here so imports in other modules do not crash.
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

# Groq support for multiple keys (Load Balancing)
_groq_env = os.getenv("GROQ_API_KEYS", os.getenv("GROQ_API_KEY", ""))
GROQ_API_KEYS = [k.strip() for k in _groq_env.split(",") if k.strip()]

# Optional OpenRouter Branding
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "")
OPENROUTER_APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "Enterprise Agent")

# --- EMBEDDINGS ---
# Default embedding model used across the platform.
# Must match the Neo4j vector index dimensions (1536).
OPENROUTER_EMBED_MODEL_DEFAULT = os.getenv(
    "OPENROUTER_EMBED_MODEL_DEFAULT", "openai/text-embedding-3-small"
).strip()

# --- MODEL DEFAULTS ---
MODEL_NAME = os.getenv("MODEL", "openai/gpt-4o")

# --- NBFC ROUTER CONFIGURATION ---
NBFC_ROUTER_ENABLED = os.getenv("NBFC_ROUTER_ENABLED", "true").lower() in ("1", "true", "yes", "y")
NBFC_ROUTER_MODE = os.getenv("NBFC_ROUTER_MODE", "hybrid").strip().lower()
NBFC_ROUTER_CHAT_MODEL = os.getenv("NBFC_ROUTER_CHAT_MODEL", "z-ai/glm-4.7").strip()
NBFC_ROUTER_EMBED_MODEL = os.getenv("NBFC_ROUTER_EMBED_MODEL", OPENROUTER_EMBED_MODEL_DEFAULT).strip()
NBFC_ROUTER_CACHE_DIR = os.getenv("NBFC_ROUTER_CACHE_DIR", ".cache_nbfc_router").strip()

# Router Thresholds (Tuned for production)
NBFC_ROUTER_SENTIMENT_THRESHOLD = float(os.getenv("NBFC_ROUTER_SENTIMENT_THRESHOLD", "0.26"))
NBFC_ROUTER_SENTIMENT_MARGIN = float(os.getenv("NBFC_ROUTER_SENTIMENT_MARGIN", "0.03"))
NBFC_ROUTER_REASON_UNKNOWN_GATE = float(os.getenv("NBFC_ROUTER_REASON_UNKNOWN_GATE", "0.30"))
NBFC_ROUTER_REASON_MARGIN = float(os.getenv("NBFC_ROUTER_REASON_MARGIN", "0.03"))
NBFC_ROUTER_FALLBACK_SENTIMENT_SCORE = float(os.getenv("NBFC_ROUTER_FALLBACK_SENTIMENT_SCORE", "0.33"))
NBFC_ROUTER_FALLBACK_REASON_SCORE = float(os.getenv("NBFC_ROUTER_FALLBACK_REASON_SCORE", "0.60"))

# --- JUDGE CONFIGURATION ---
JUDGE_MODEL_NAME = os.getenv("JUDGE_MODEL_NAME", "openai/gpt-4o")
ENABLE_LLM_JUDGE = os.getenv("ENABLE_LLM_JUDGE", "true").lower() == "true"
